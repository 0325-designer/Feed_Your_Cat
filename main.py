import pygame
import random
import sys
import math
import os
import traceback
from datetime import datetime
from typing import Tuple

# 初始化pygame
pygame.init()

# 确保中文显示正常
pygame.font.init()
font_path = pygame.font.match_font('simsun') or pygame.font.match_font('microsoftyahei')
if not font_path:
    # 如果找不到中文字体，使用默认字体
    default_font = pygame.font.get_default_font()
    font_path = pygame.font.match_font(default_font)

# 游戏常量
WIDTH, HEIGHT = 800, 600
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# --- 可调参数（常量） ---
# 躲猫猫触发相关
HIDE_NEAR_DISTANCE = 180            # 鼠标接近猫小于该距离，优先触发躲藏
HIDE_TRIGGER_RANDOM_CHANCE = 0.002  # 平时每帧小概率触发（更小 => 更少躲藏）
HIDE_DURATION_MIN_FRAMES = int(1.0 * FPS)   # 隐藏最短时长 ~1s
HIDE_DURATION_MAX_FRAMES = int(2.0 * FPS)   # 隐藏最长时长 ~2s
HIDE_COOLDOWN_FRAMES = int(3 * FPS)       # 躲藏结束后的冷却时间，避免过于频繁
HIDE_INSET_MIN = 6                  # 藏在障碍内部时，距离边缘的最小内缩像素
HIDE_INSET_FRACTION = 0.25          # 内缩量按障碍宽高比例

# 对话框相关
BUBBLE_SMOOTH_ALPHA = 0.28          # 气泡位置的指数平滑系数（0-1 越小越稳）
BUBBLE_TAIL_LEN = 14
BUBBLE_TAIL_W = 12
BUBBLE_REFRESH_MIN_FRAMES = 3 * FPS
BUBBLE_REFRESH_MAX_FRAMES = 5 * FPS
BUBBLE_STICKY_BIAS_PX = 60          # 粘性偏好：当前方向享受等价于减少该像素距离的加权，避免频繁切换
BUBBLE_MOUSE_BIAS_DISTANCE = 200     # 仅当鼠标距离猫小于该值时，才启用“贴近玩家一侧”的偏好

# --- 游戏流程相关 ---
GAME_DURATION_FRAMES = 60 * FPS      # 总时长：60秒
LOSS_GRACE_FRAMES = 30 * FPS         # 开始后30秒内不判定亲密度=0失败

# 停驻（无遮挡）相关
IDLE_INTERVAL_FRAMES = 10 * FPS
IDLE_DURATION_MIN_FRAMES = int(3 * FPS)
IDLE_DURATION_MAX_FRAMES = int(4 * FPS)

# 移动速度调整
CAT_OPEN_SPEED_FACTOR = 0.6  # 猫在无遮挡区域的移动速度比例（相对 Cat.speed）

# 创建日志函数（打印到控制台并写入文件，方便排查）
LOG_FILE = os.path.join(os.path.dirname(__file__), "game_debug.log")

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except Exception:
        pass

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def circle_rect_overlap(cx: float, cy: float, r: float, rect: pygame.Rect) -> bool:
    # 找到距离圆心最近的矩形点
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx*dx + dy*dy) <= (r*r)

def resolve_circle_rect_collision(cx: float, cy: float, r: float, rect: pygame.Rect, vx: float, vy: float) -> Tuple[float, float, float, float]:
    """将圆从矩形中推出并对速度做反射，减少抖动/卡边。
    返回新 (cx, cy, vx, vy)
    """
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    nx = cx - nearest_x
    ny = cy - nearest_y
    dist2 = nx*nx + ny*ny
    if dist2 == 0:
        # 圆心刚好在最近点上，选择一个默认法线（向上）
        nx, ny = 0.0, -1.0
        dist = 1.0
    else:
        dist = math.sqrt(dist2)
        nx /= dist
        ny /= dist
    # 推出重叠
    overlap = r - dist
    if overlap > 0:
        cx += nx * (overlap + 0.5)
        cy += ny * (overlap + 0.5)
        # 速度沿法线反射
        dot = vx*nx + vy*ny
        vx = vx - 2*dot*nx
        vy = vy - 2*dot*ny
    return cx, cy, vx, vy
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

log("Program start: initializing display window...")

# 创建游戏窗口（捕获异常，记录日志）
try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("抓小猫投喂游戏")
    log("Display window created successfully.")
except Exception as e:
    log(f"Failed to create display window: {e}")
    log(traceback.format_exc())
    raise

clock = pygame.time.Clock()

class Cat:
    def __init__(self):
        # 初始属性
        self.size = 30
        self.x = random.randint(self.size, WIDTH - self.size)
        self.y = random.randint(self.size, HEIGHT - self.size)
        self.speed = 5
        self.dx = random.choice([-1, 1]) * self.speed
        self.dy = random.choice([-1, 1]) * self.speed
        self.color = (169, 169, 169)  # 灰色
        self.hunger = 50  # 饥饿值 0-100
        self.playfulness = 50  # 玩耍欲 0-100
        self.affinity = 0  # 亲密度 0-100
        self.growth_stage = 1  # 成长阶段
        
    def move(self, speed_scale: float = 1.0):
        # 去掉抖动：不再随机改变方向，仅按当前方向匀速移动

        # 先更新位置
        self.x += self.dx * speed_scale
        self.y += self.dy * speed_scale

        # 游戏区域边界（顶部预留工具栏高度60px）
        min_x = self.size
        max_x = WIDTH - self.size
        min_y = 60 + self.size
        max_y = HEIGHT - self.size

        # X轴边界反弹
        if self.x < min_x:
            self.x = min_x
            self.dx *= -1
        elif self.x > max_x:
            self.x = max_x
            self.dx *= -1

        # Y轴边界反弹（避免进入工具栏区域）
        if self.y < min_y:
            self.y = min_y
            self.dy *= -1
        elif self.y > max_y:
            self.y = max_y
            self.dy *= -1
            
        # 随机改变需求
        if random.random() < 0.01:
            self.hunger = min(100, self.hunger + random.randint(1, 3))
            self.playfulness = max(0, self.playfulness - random.randint(1, 2))
        if random.random() < 0.01:
            self.playfulness = min(100, self.playfulness + random.randint(1, 3))
            self.hunger = max(0, self.hunger - random.randint(1, 2))
            
    def grow(self):
        # 成长逻辑
        if self.affinity >= 30 and self.growth_stage == 1:
            self.growth_stage = 2
            self.size = 45
            self.speed = 6
            self.color = (130, 130, 130)  # 深灰色
        elif self.affinity >= 60 and self.growth_stage == 2:
            self.growth_stage = 3
            self.size = 60
            self.speed = 7
            self.color = (100, 100, 100)  # 更深的灰色
            
    def draw(self):
        # 绘制猫咪
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        # 绘制眼睛
        eye_offset = self.size // 3
        pygame.draw.circle(screen, WHITE, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, WHITE, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, BLACK, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 12)
        pygame.draw.circle(screen, BLACK, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 12)
        # 绘制嘴巴
        pygame.draw.line(screen, BLACK, (int(self.x), int(self.y)), (int(self.x), int(self.y) + self.size//4), 2)
        
    def get_current_need(self):
        # 判断当前主要需求
        if self.hunger > self.playfulness + 20:
            return "food"  # 需要食物
        elif self.playfulness > self.hunger + 20:
            return "toy"   # 需要玩具
        else:
            return random.choice(["food", "toy"])  # 需求均衡，随机一种

class Player:
    def __init__(self):
        self.score = 0
        self.selected_item = "food"  # 默认选中食物
        self.thrown_items = []
        self.consecutive_wrong = 0  # 连续错误命中次数
        
    def throw_item(self, mouse_pos, cat_pos, game_ref=None):
        # 投掷物品
        expected_need = None
        if game_ref is not None:
            try:
                expected_need = game_ref.cat.get_current_need()
            except Exception:
                expected_need = None
        item = {
            "type": self.selected_item,
            "x": mouse_pos[0],
            "y": mouse_pos[1],
            "target_x": cat_pos[0],
            "target_y": cat_pos[1],
            "speed": 8,
            "radius": 10,
            "color": GREEN if self.selected_item == "food" else YELLOW,
            "thrown": True,
            "game_ref": game_ref,
            "expected_need": expected_need,
        }
        self.thrown_items.append(item)
        
    def update_items(self):
        # 更新投掷物品的位置
        for item in self.thrown_items[:]:
            # 计算到目标的方向
            dx = item["target_x"] - item["x"]
            dy = item["target_y"] - item["y"]
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < item["speed"]:
                item["x"] = item["target_x"]
                item["y"] = item["target_y"]
                self.thrown_items.remove(item)
                return item  # 返回到达目标的物品
            else:
                # 移动物品
                step_x = (dx / distance) * item["speed"]
                step_y = (dy / distance) * item["speed"]
                new_x = item["x"] + step_x
                new_y = item["y"] + step_y
                # 简单阻挡：若新位置进入障碍物，则该物品被挡住并消失
                if 'game_ref' in item and item['game_ref'] is not None:
                    game = item['game_ref']
                    for rect in game.obstacles:
                        if rect.collidepoint(int(new_x), int(new_y)):
                            # 被障碍挡住，移除
                            self.thrown_items.remove(item)
                            # 通过在返回值里标记一个字段，通知外层显示消息
                            item_copy = dict(item)
                            item_copy['_blocked'] = True
                            return item_copy
                item["x"], item["y"] = new_x, new_y
        return None
        
    def draw_items(self):
        # 绘制投掷中的物品
        for item in self.thrown_items:
            pygame.draw.circle(screen, item["color"], (int(item["x"]), int(item["y"])), item["radius"])
            
    def switch_item(self):
        # 切换物品
        self.selected_item = "toy" if self.selected_item == "food" else "food"

class Game:
    def __init__(self):
        # 实体
        self.cat = Cat()
        self.player = Player()
        # 状态
        self.running = True
        # 字体
        self.font = pygame.font.Font(font_path, 24)
        self.large_font = pygame.font.Font(font_path, 36)
        # 定义障碍物（矩形），位于工具栏下方区域
        self.obstacles = [
            pygame.Rect(150, 140, 120, 80),
            pygame.Rect(380, 260, 160, 90),
            pygame.Rect(620, 120, 100, 140),
            # 左下角，紧贴边缘的障碍物
            pygame.Rect(0, HEIGHT - 120, 140, 120),
        ]
        self.obstacle_color = (120, 120, 120)
        # 躲猫猫状态
        self.hide_target = None  # (x, y)
        self.hide_frames = 0     # 剩余躲藏帧数（保持在1-2秒）
        self.hide_waiting = False
        self.hide_cooldown = 0   # 躲藏冷却计时
        # 停驻（无遮挡）逻辑
        self.idle_cooldown = int(IDLE_INTERVAL_FRAMES)  # 初始间隔后进入第一次停驻
        self.idle_frames = 0
        # 对话框文本（避免频繁抖动，改为每3-5秒随机刷新）
        initial_need = self.cat.get_current_need()
        self.need_text = "我想吃东西！" if initial_need == "food" else "我想玩玩具！"
        self._need_frames_left = random.randint(BUBBLE_REFRESH_MIN_FRAMES, BUBBLE_REFRESH_MAX_FRAMES)
        # 气泡位置与方向（平滑跟随、粘性朝向）
        self._bubble_pos = None  # type: ignore
        self.bubble_side = 'top'
        # 游戏流程状态
        self.time_left = GAME_DURATION_FRAMES
        self.loss_grace = LOSS_GRACE_FRAMES
        self.game_over = False
        self.game_result = None  # 'win' | 'lose' | 'summary'
        self.end_message = ""

    def ensure_open_spot(self):
        """把猫从障碍物里挪到无遮挡位置，并确保不进入工具栏区域。"""
        # 先约束在可见区域（不进入工具栏）
        self.cat.x = clamp(self.cat.x, self.cat.size, WIDTH - self.cat.size)
        self.cat.y = clamp(self.cat.y, 60 + self.cat.size, HEIGHT - self.cat.size)
        # 若与障碍物重叠，使用碰撞推出若干次
        for _ in range(4):
            moved = False
            for rect in self.obstacles:
                if circle_rect_overlap(self.cat.x, self.cat.y, self.cat.size, rect):
                    nx, ny, vx, vy = resolve_circle_rect_collision(self.cat.x, self.cat.y, self.cat.size, rect, self.cat.dx, self.cat.dy)
                    self.cat.x, self.cat.y = nx, ny
                    self.cat.dx, self.cat.dy = vx, vy
                    moved = True
            if not moved:
                break

    def compute_hide_spot(self, mouse_pos: Tuple[int, int]) -> Tuple[int, int]:
        """挑选距离猫最近的障碍物，并在相对鼠标的背面【障碍物内部】生成目标点，保证被遮挡。"""
        if not self.obstacles:
            return (self.cat.x, max(60 + self.cat.size, self.cat.y))
        cx, cy = self.cat.x, self.cat.y
        # 找最近障碍
        nearest = min(self.obstacles, key=lambda r: (r.centerx - cx) ** 2 + (r.centery - cy) ** 2)
        mx, my = mouse_pos
        dx = nearest.centerx - mx
        dy = nearest.centery - my
        # 在鼠标相对障碍的“远侧”选择一个离边缘略微内缩的位置，保证中心进入矩形内部从而被遮挡
        inset_x = max(HIDE_INSET_MIN, min(int(nearest.width * HIDE_INSET_FRACTION), self.cat.size))
        inset_y = max(HIDE_INSET_MIN, min(int(nearest.height * HIDE_INSET_FRACTION), self.cat.size))
        if abs(dx) >= abs(dy):
            # 左/右侧隐藏（内部）
            side_sign = 1 if dx >= 0 else -1  # 鼠标在左 => 选右侧
            tx = nearest.centerx + side_sign * (nearest.width / 2 - inset_x)
            # 尽量保持和猫当前y接近，同时限制在矩形内部
            ty = clamp(cy, nearest.top + inset_y, nearest.bottom - inset_y)
        else:
            # 上/下侧隐藏（内部）
            side_sign = 1 if dy >= 0 else -1  # 鼠标在上 => 选下侧
            ty = nearest.centery + side_sign * (nearest.height / 2 - inset_y)
            tx = clamp(cx, nearest.left + inset_x, nearest.right - inset_x)
        # 最后兜底约束在屏幕内
        tx = clamp(tx, 0 + self.cat.size, WIDTH - self.cat.size)
        ty = clamp(ty, 60 + self.cat.size, HEIGHT - self.cat.size)
        return (int(tx), int(ty))
        
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.game_over:
                    if event.key == pygame.K_r:
                        # 重新开始本局
                        self.__init__()
                        return
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        return
                if event.key == pygame.K_SPACE:
                    self.player.switch_item()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    # 检查是否点击工具栏外（游戏区域）
                    if event.pos[1] > 60:
                        self.player.throw_item(event.pos, (self.cat.x, self.cat.y), self)
        
    def check_collision(self, item):
        # 检查物品是否击中猫咪
        dx = item["x"] - self.cat.x
        dy = item["y"] - self.cat.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < self.cat.size:
            # 击中猫咪
            cat_need = item.get("expected_need") or self.cat.get_current_need()
            if item["type"] == cat_need:
                # 只在投中猫咪需要的物品时加1分
                self.player.score += 1
                # 可以选择不改动金钱/亲密度；这里保持亲密度提升、需求缓解
                self.cat.affinity = min(100, self.cat.affinity + 2)
                # 重置连续错误计数
                self.player.consecutive_wrong = 0

                if item["type"] == "food":
                    self.cat.hunger = max(0, self.cat.hunger - 15)
                else:
                    self.cat.playfulness = max(0, self.cat.playfulness - 15)
                return True, "正确! +1分"
            else:
                # 投错了物品：不加分
                self.player.consecutive_wrong += 1
                if self.player.consecutive_wrong > 3:
                    self.cat.affinity = max(0, self.cat.affinity - 2)
                return True, "不是这个!"
        return False, ""

    def draw_obstacles(self):
        # 绘制障碍物（用于遮挡猫咪/投掷物）
        for rect in self.obstacles:
            pygame.draw.rect(screen, self.obstacle_color, rect)

    def draw_speech_bubble(self):
        # 在猫附近绘制一个带圆角和三角尾巴的对话框，显示当前需求
        text = self.need_text
        if not text:
            return
        pad = 8
        surf = self.font.render(text, True, BLACK)
        bw, bh = surf.get_width() + pad * 2, surf.get_height() + pad * 2
        # 计算期望位置（带“粘性”方向与平滑动画），优先 top，若不合法按 right/left/bottom 备选
        margin = 8
        def calc_rect(side: str):
            if side == 'top':
                bx0 = int(self.cat.x - bw / 2)
                by0 = int(self.cat.y - self.cat.size - bh - 10)
            elif side == 'bottom':
                bx0 = int(self.cat.x - bw / 2)
                by0 = int(self.cat.y + self.cat.size + 10)
            elif side == 'left':
                bx0 = int(self.cat.x - self.cat.size - bw - 12)
                by0 = int(self.cat.y - bh / 2)
            else:  # right
                bx0 = int(self.cat.x + self.cat.size + 12)
                by0 = int(self.cat.y - bh / 2)
            bx0 = int(clamp(bx0, 5, WIDTH - bw - 5))
            by0 = int(clamp(by0, 65, HEIGHT - bh - 5))
            return pygame.Rect(bx0, by0, bw, bh)

        def valid(rect: pygame.Rect):
            return rect.left >= 5 and rect.right <= WIDTH - 5 and rect.top >= 65 and rect.bottom <= HEIGHT - 5

        # 避免对话框遮住猫：优先选择与猫不相交的气泡矩形
        def overlaps_cat(rect: pygame.Rect) -> bool:
            cx, cy, r = int(self.cat.x), int(self.cat.y), int(self.cat.size)
            cat_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            # 适当扩大猫的判定框，给出一点安全边距
            cat_rect.inflate_ip(8, 8)
            return rect.colliderect(cat_rect)

        # 备选方向：包含当前方向以增强粘性
        candidates = ['top', 'right', 'left', 'bottom']
        if self.bubble_side in candidates:
            # 确保当前方向在列表首位，增强稳定性
            candidates.remove(self.bubble_side)
            candidates.insert(0, self.bubble_side)

        # 根据“合法性 + 不遮挡 + 距离鼠标最近 + 粘性偏好”综合评分选择
        mx, my = pygame.mouse.get_pos()
        # 仅在鼠标靠近猫时才启用“贴近玩家一侧”的偏好
        mc_dist = math.hypot(self.cat.x - mx, self.cat.y - my)
        apply_mouse_bias = mc_dist <= BUBBLE_MOUSE_BIAS_DISTANCE
        best = None  # (score, side, rect)
        for s in candidates:
            r = calc_rect(s)
            if not valid(r):
                continue
            # 基本距离评分：越靠近鼠标越小；仅在接近时才考虑该项
            d = math.hypot((r.centerx - mx), (r.centery - my)) if apply_mouse_bias else 0.0
            # 不遮挡优先：遮挡的话加一个大罚分
            overlap_penalty = 10000 if overlaps_cat(r) else 0
            # 粘性偏好：当前方向享受减分，避免频繁切换
            sticky_bonus = -BUBBLE_STICKY_BIAS_PX if s == self.bubble_side else 0
            score = d + overlap_penalty + sticky_bonus
            if best is None or score < best[0]:
                best = (score, s, r)
        if best is None:
            # 兜底：随便选一个可见区域
            chosen_side, chosen_rect = 'top', calc_rect('top')
        else:
            _, chosen_side, chosen_rect = best

        # 平滑移动气泡位置，减少抖动
        bx_des, by_des = chosen_rect.left, chosen_rect.top
        if self._bubble_pos is None:
            self._bubble_pos = [float(bx_des), float(by_des)]
        else:
            alpha = BUBBLE_SMOOTH_ALPHA
            self._bubble_pos[0] += (bx_des - self._bubble_pos[0]) * alpha
            self._bubble_pos[1] += (by_des - self._bubble_pos[1]) * alpha
        bx = int(round(self._bubble_pos[0]))
        by = int(round(self._bubble_pos[1]))
        bubble_rect = pygame.Rect(bx, by, bw, bh)
        self.bubble_side = chosen_side
        # 计算三角尾巴，避免过度变形：固定长度/宽度，并将尾巴画在气泡下层，避免覆盖文字
        tail_len = BUBBLE_TAIL_LEN
        tail_w = BUBBLE_TAIL_W
        cx, cy = int(self.cat.x), int(self.cat.y)
        # 选择最接近猫的气泡边作为尾巴出口
        dx = cx - bubble_rect.centerx
        dy = cy - bubble_rect.centery
        if abs(dx) > abs(dy):
            # 左/右边
            side = 'right' if dx > 0 else 'left'
        else:
            # 上/下边
            side = 'bottom' if dy > 0 else 'top'

        if side == 'top':
            base_cx = int(clamp(cx, bubble_rect.left + 10, bubble_rect.right - 10))
            base_cy = bubble_rect.top
            base_left = (base_cx - tail_w // 2, base_cy)
            base_right = (base_cx + tail_w // 2, base_cy)
            tip = (base_cx, base_cy - tail_len)
        elif side == 'bottom':
            base_cx = int(clamp(cx, bubble_rect.left + 10, bubble_rect.right - 10))
            base_cy = bubble_rect.bottom
            base_left = (base_cx - tail_w // 2, base_cy)
            base_right = (base_cx + tail_w // 2, base_cy)
            tip = (base_cx, base_cy + tail_len)
        elif side == 'left':
            base_cx = bubble_rect.left
            base_cy = int(clamp(cy, bubble_rect.top + 10, bubble_rect.bottom - 10))
            base_left = (base_cx, base_cy - tail_w // 2)
            base_right = (base_cx, base_cy + tail_w // 2)
            tip = (base_cx - tail_len, base_cy)
        else:  # right
            base_cx = bubble_rect.right
            base_cy = int(clamp(cy, bubble_rect.top + 10, bubble_rect.bottom - 10))
            base_left = (base_cx, base_cy - tail_w // 2)
            base_right = (base_cx, base_cy + tail_w // 2)
            tip = (base_cx + tail_len, base_cy)

        # 先绘制尾巴（三角形），再绘制圆角矩形，这样尾巴与文字不会互相覆盖
        pygame.draw.polygon(screen, WHITE, [base_left, base_right, tip])
        pygame.draw.lines(screen, BLACK, False, [base_left, tip, base_right], 2)

        # 绘制圆角矩形（在尾巴之上）
        pygame.draw.rect(screen, WHITE, bubble_rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, bubble_rect, width=2, border_radius=8)

        # 绘制文字（最后）
        screen.blit(surf, (bx + pad, by + pad))
        
    def draw_ui(self):
        # 绘制工具栏
        pygame.draw.rect(screen, (200, 200, 200), (0, 0, WIDTH, 60))
        
        # 绘制选中的物品
        selected_text = f"当前选中: {'猫粮' if self.player.selected_item == 'food' else '玩具'}"
        text_surface = self.font.render(selected_text, True, BLACK)
        screen.blit(text_surface, (20, 20))
        
        # 绘制分数与连错次数
        score_text = f"分数: {self.player.score}"
        screen.blit(self.font.render(score_text, True, BLACK), (300, 20))
        wrong = self.player.consecutive_wrong if hasattr(self.player, 'consecutive_wrong') else 0
        wrong_color = RED if wrong > 3 else BLACK
        wrong_text = f"连错: {wrong}"
        screen.blit(self.font.render(wrong_text, True, wrong_color), (420, 20))
        
        # 绘制猫咪状态
        affinity_text = f"亲密度: {int(self.cat.affinity)}%"
        stage_text = f"成长阶段: {self.cat.growth_stage}"
        screen.blit(self.font.render(affinity_text, True, BLACK), (WIDTH - 200, 20))
        screen.blit(self.font.render(stage_text, True, BLACK), (WIDTH - 350, 20))
        # 计时器
        if hasattr(self, 'time_left'):
            secs = max(0, int(self.time_left // FPS))
            timer_text = f"剩余: {secs:02d}s"
            screen.blit(self.font.render(timer_text, True, BLACK), (WIDTH//2 - 40, 20))
        # 需求提示（红字）已按用户要求移除，不再显示
        
    def run(self):
        log("Game loop entering...")
        ticks = 0
        while self.running:
            screen.fill(WHITE)
            
            # 处理事件
            self.handle_events()
            # 游戏结束态：只显示结算面板与UI，等待R/ESC
            if self.game_over:
                # 背景可依然绘制基本元素，简单起见绘制UI与结束面板
                self.draw_ui()
                # 半透明遮罩
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                screen.blit(overlay, (0, 0))
                # 文本
                title = "胜利!" if self.game_result == 'win' else ("失败" if self.game_result == 'lose' else "时间到")
                t_surf = self.large_font.render(title, True, WHITE)
                msg_surf = self.font.render(self.end_message, True, WHITE)
                hint_surf = self.font.render("按 R 重开 / Esc 退出", True, WHITE)
                cx = WIDTH//2
                screen.blit(t_surf, (cx - t_surf.get_width()//2, HEIGHT//2 - 70))
                screen.blit(msg_surf, (cx - msg_surf.get_width()//2, HEIGHT//2 - 20))
                screen.blit(hint_surf, (cx - hint_surf.get_width()//2, HEIGHT//2 + 30))
                pygame.display.flip()
                clock.tick(FPS)
                continue
            
            # 更新游戏状态
            mouse_pos = pygame.mouse.get_pos()
            # 每隔10s让猫在无遮挡处停驻3-4s（若当前不在躲藏）
            if self.idle_frames <= 0:
                if self.idle_cooldown > 0:
                    self.idle_cooldown -= 1
                elif self.hide_frames <= 0 and not self.hide_waiting and mouse_pos[1] > 60:
                    # 进入停驻：先确保当前位置无遮挡，然后计时3-4秒
                    self.ensure_open_spot()
                    self.idle_frames = random.randint(int(3 * FPS), int(4 * FPS))
                    # 重新计间隔
                    self.idle_cooldown = int(10 * FPS)

            # 触发“躲猫猫”行为：鼠标靠近时优先触发，平时也有小概率触发，并考虑冷却；停驻时不触发
            if self.hide_frames <= 0 and self.idle_frames <= 0 and self.hide_cooldown <= 0 and mouse_pos[1] > 60:
                # 鼠标与猫的距离
                mdx = mouse_pos[0] - self.cat.x
                mdy = mouse_pos[1] - self.cat.y
                mdist = math.hypot(mdx, mdy)
                if mdist <= HIDE_NEAR_DISTANCE or random.random() < HIDE_TRIGGER_RANDOM_CHANCE:
                    self.hide_target = self.compute_hide_spot(mouse_pos)
                    self.hide_frames = random.randint(HIDE_DURATION_MIN_FRAMES, HIDE_DURATION_MAX_FRAMES)

            if self.idle_frames > 0:
                # 停驻中：不移动
                self.idle_frames -= 1
                # 再确保不意外进入工具栏
                self.cat.y = max(60 + self.cat.size, self.cat.y)
            elif self.hide_frames > 0 and self.hide_target is not None:
                # 朝躲藏点移动；到达后停留直到计时结束，确保“彻底躲藏”1-2秒
                hx, hy = self.hide_target
                dx = hx - self.cat.x
                dy = hy - self.cat.y
                dist = math.hypot(dx, dy) or 1.0
                step = self.cat.speed
                if dist > step:
                    self.cat.x += (dx / dist) * step
                    self.cat.y += (dy / dist) * step
                else:
                    # 到达目标，固定在目标点等待剩余时间
                    self.cat.x, self.cat.y = hx, hy
                    self.hide_waiting = True
                self.hide_frames -= 1
                if self.hide_frames <= 0:
                    self.hide_target = None
                    self.hide_waiting = False
                    self.hide_cooldown = HIDE_COOLDOWN_FRAMES
            else:
                # 常规移动：在无遮挡区域放慢速度
                self.cat.move(CAT_OPEN_SPEED_FACTOR)
            # 猫与障碍物的碰撞处理（圆-矩形）：使用法线反射，减少抖动
            # 正在“躲藏”期间允许猫进入障碍物内部（被遮挡），因此跳过碰撞推出
            if not (self.hide_frames > 0 or self.hide_waiting):
                for rect in self.obstacles:
                    if circle_rect_overlap(self.cat.x, self.cat.y, self.cat.size, rect):
                        nx, ny, vx, vy = resolve_circle_rect_collision(self.cat.x, self.cat.y, self.cat.size, rect, self.cat.dx, self.cat.dy)
                        self.cat.x, self.cat.y = nx, ny
                        self.cat.dx, self.cat.dy = vx, vy
                        break
            self.cat.grow()
            hit_item = self.player.update_items()
            
            # 检查碰撞
            message = ""
            if hit_item:
                if isinstance(hit_item, dict) and hit_item.get('_blocked'):
                    message = "被障碍挡住！"
                else:
                    hit, message = self.check_collision(hit_item)
            
            # 绘制游戏元素
            self.cat.draw()
            self.player.draw_items()
            # 障碍物最后绘制，用于遮挡猫和物品
            self.draw_obstacles()
            # 对话框绘制在障碍物之上，确保可见
            self.draw_speech_bubble()
            self.draw_ui()
            
            # 显示消息
            if message:
                msg_surface = self.font.render(message, True, BLUE)
                screen.blit(msg_surface, (WIDTH // 2 - msg_surface.get_width() // 2, 70))
            
            # 刷新屏幕
            pygame.display.flip()
            clock.tick(FPS)
            # 约每秒打印一次心跳日志，确认循环在运行
            ticks += 1
            if ticks % FPS == 0:
                log(f"Heartbeat: running, score={self.player.score}, affinity={self.cat.affinity}, stage={self.cat.growth_stage}, wrong_streak={self.player.consecutive_wrong}")
            # 冷却递减
            if self.hide_cooldown > 0:
                self.hide_cooldown -= 1
            # 定期（每3-5秒随机）刷新对话文本
            if hasattr(self, "_need_frames_left"):
                self._need_frames_left -= 1
                if self._need_frames_left <= 0:
                    need = self.cat.get_current_need()
                    self.need_text = "我想吃东西！" if need == "food" else "我想玩玩具！"
                    self._need_frames_left = random.randint(BUBBLE_REFRESH_MIN_FRAMES, BUBBLE_REFRESH_MAX_FRAMES)
            # 计时与胜负判定
            if self.time_left > 0:
                self.time_left -= 1
            if self.loss_grace > 0:
                self.loss_grace -= 1
            if self.loss_grace <= 0 and self.cat.affinity <= 0 and not self.game_over:
                self.game_over = True
                self.game_result = 'lose'
                self.end_message = "亲密度降为 0，猫咪溜走了……"
            if self.time_left <= 0 and not self.game_over:
                if self.cat.affinity >= 80 or self.cat.growth_stage >= 3:
                    self.game_over = True
                    self.game_result = 'win'
                    self.end_message = f"恭喜！最终分数 {self.player.score}；亲密度 {int(self.cat.affinity)}%"
                else:
                    self.game_over = True
                    self.game_result = 'summary'
                    self.end_message = f"时间到。分数 {self.player.score}；亲密度 {int(self.cat.affinity)}%，阶段 {self.cat.growth_stage}"

        log("Game loop exiting. Cleaning up...")
        pygame.quit()
        log("Pygame quit done. Exiting process.")
        sys.exit()

# 启动游戏
if __name__ == "__main__":
    try:
        log("__main__ entry reached. Starting Game()...")
        game = Game()
        log("Game instance created. Running game loop...")
        game.run()
    except Exception as e:
        log(f"Unhandled exception: {e}")
        log(traceback.format_exc())
        raise