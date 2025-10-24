import pygame
import random
import sys
import math
import os
import json
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
CAT_SPEED_STAGE_1 = 5        # 初始阶段速度
CAT_SPEED_STAGE_2 = 7        # 阶段2速度（亲密度≥30时）
CAT_SPEED_STAGE_3 = 9        # 阶段3速度（亲密度≥60时）

# 猫贴图缩放滤镜：像素风建议 'nearest'，写实风建议 'smooth'
CAT_IMAGE_FILTER = 'smooth'

# 猫走路动画：两帧切换的时间间隔（帧）
CAT_WALK_ANIM_INTERVAL_FRAMES = max(1, int(0.12 * FPS))

# 障碍物贴图缩放策略（避免变形）
# scale mode: 'contain' 适配不变形（留边），'cover' 充满（可能超出矩形），'stretch' 拉伸填满（可能变形）
OBSTACLE_IMAGE_SCALE_MODE = 'contain'
# 缩放滤镜：像素风建议 'nearest'，写实风建议 'smooth'
OBSTACLE_IMAGE_FILTER = 'nearest'
# 对齐：'center' 居中，'bottom' 贴底（比如树根贴地更自然）
OBSTACLE_IMAGE_ALIGN = 'bottom'

# 贴图全局放大系数（不改变碰撞矩形，仅视觉变大；1.0为不变）
OBSTACLE_IMAGE_GLOBAL_SCALE = 1.25
# 可选：按障碍索引单独放大，形如 {1:1.0, 2:1.0, 3:1.4}
OBSTACLE_IMAGE_PER_SCALE = {2: 0.8, 1: 1.2, 3: 0.9, 4: 1.2}
# 可选：按文件名单独缩放（当使用 obstacle_*.png 或 obstacle.png 时匹配）
OBSTACLE_IMAGE_PER_FILE_SCALE = {"obstacle_2.png": 0.8}

# 物品贴图缩放（仅视觉），按类型：'food' 和 'toy'
ITEM_IMAGE_SCALE = {"food": 1.0, "toy": 1.0}

# 季节过渡（障碍贴图/背景 Normal <-> Winter）
SEASON_AUTO_CYCLE = False                # 禁用自动循环
SEASON_HOLD_FRAMES = 8 * FPS             # 在每个季节停留时长
SEASON_TRANSITION_FRAMES = 1             # 过渡时长（1帧=立即切换）

# 场景切换系统（方案A：多场景自动切换）
SCENE_SWITCH_INTERVAL = 20 * FPS         # 场景切换间隔（20秒）
SCENE_SWITCH_FADE_FRAMES = int(0.5 * FPS)  # 切换淡入淡出时间（0.5秒）

# 字体配置（把你的 TTF 放到 ./assets/ 目录即可生效）
# 例如：assets/ui_body.ttf 和 assets/ui_title.ttf
FONT_BODY_FILE = "MyFont.ttf"     # 正文字体文件名（可为空字符串表示不指定）
FONT_TITLE_FILE = "MyFont.ttf"   # 标题字体文件名（可为空字符串表示不指定）
FONT_BODY_SIZE = 12                 # 正文字号
FONT_TITLE_SIZE = 24                # 标题字号

# 创建日志函数（打印到控制台并写入文件，方便排查）
LOG_FILE = os.path.join(os.path.dirname(__file__), "game_debug.log")

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except Exception:
        pass
    # Also append to a log file (best-effort; ignore failures)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# Assets helpers
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

def load_image(filename: str):
    """Load PNG from ./assets; return None if missing or failed."""
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path):
        try:
            log(f"Asset not found: {filename}")
        except Exception:
            pass
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception as e:
        log(f"Failed to load {filename}: {e}")
        return None

def blit_centered(surf: pygame.Surface, tex: pygame.Surface, x: float, y: float):
    rect = tex.get_rect(center=(int(x), int(y)))
    surf.blit(tex, rect)

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

def _resolve_font_path(preferred_filename: str | None) -> str:
    """Return an absolute font path to use.
    If a preferred TTF filename exists in assets, use it; otherwise fall back to the
    detected system font (font_path defined above).
    """
    try:
        if preferred_filename:
            p = os.path.join(ASSETS_DIR, preferred_filename)
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return font_path

log("Program start: initializing display window...")

# 创建游戏窗口（捕获异常，记录日志）
try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("FEED YOUR CAT")
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
        self.speed = CAT_SPEED_STAGE_1
        self.dx = random.choice([-1, 1]) * self.speed
        self.dy = random.choice([-1, 1]) * self.speed
        self.color = (169, 169, 169)  # 灰色
        self.hunger = 50  # 饥饿值 0-100
        self.playfulness = 50  # 玩耍欲 0-100
        self.affinity = 0  # 亲密度 0-100
        self.growth_stage = 1  # 成长阶段
        # 可选：阶段精灵图，由 Game 注入 {1: [Surface, Surface], 2: [...], 3: [...]}
        # 若只提供1帧，会在加载阶段进行复制成2帧
        self.sprite_images = None
        self._cache_key = None  # (stage, size)
        # 逐帧缓存（按 size 与阶段缩放后）：[[frame0, frame1], flipped 同理]
        self._cached_scaled_frames = None
        self._cached_flipped_frames = None
        # 兼容旧字段（不再使用）
        self._cached_scaled = None
        self._cached_flipped = None  # 水平镜像缓存
        self.facing_right = True     # 朝向，基于 dx 更新
        # 动画状态
        self._anim_frame = 0
        self._anim_counter = 0
        self._last_draw_pos = (self.x, self.y)
        
    def move(self, speed_scale: float = 1.0, check_bounds: bool = True):
        # 去掉抖动：不再随机改变方向，仅按当前方向匀速移动

        # 先更新位置
        self.x += self.dx * speed_scale
        self.y += self.dy * speed_scale

        # 屏幕边界（仅在check_bounds=True时生效）
        if check_bounds:
            min_x = self.size
            max_x = WIDTH - self.size
            min_y = 60 + self.size  # 顶部预留工具栏
            max_y = HEIGHT - self.size

            # X轴边界反弹
            if self.x < min_x:
                self.x = min_x
                self.dx *= -1
            elif self.x > max_x:
                self.x = max_x
                self.dx *= -1

            # Y轴边界反弹
            if self.y < min_y:
                self.y = min_y
                self.dy *= -1
            elif self.y > max_y:
                self.y = max_y
                self.dy *= -1
        
        # 更新朝向（基于当前水平速度方向）
        self.facing_right = (self.dx >= 0)
            
        # 随机改变需求
        if random.random() < 0.01:
            self.hunger = min(100, self.hunger + random.randint(1, 3))
            self.playfulness = max(0, self.playfulness - random.randint(1, 2))
        if random.random() < 0.01:
            self.playfulness = min(100, self.playfulness + random.randint(1, 3))
            self.hunger = max(0, self.hunger - random.randint(1, 2))
            
    def grow(self):
        # 成长逻辑：每次升级时速度会增加
        if self.affinity >= 30 and self.growth_stage == 1:
            self.growth_stage = 2
            self.size = 45
            old_speed = self.speed
            self.speed = CAT_SPEED_STAGE_2
            # 保持方向，更新速度分量
            if old_speed > 0:
                self.dx = (self.dx / old_speed) * self.speed
                self.dy = (self.dy / old_speed) * self.speed
            self.color = (130, 130, 130)  # 深灰色
        elif self.affinity >= 60 and self.growth_stage == 2:
            self.growth_stage = 3
            self.size = 60
            old_speed = self.speed
            self.speed = CAT_SPEED_STAGE_3
            # 保持方向，更新速度分量
            if old_speed > 0:
                self.dx = (self.dx / old_speed) * self.speed
                self.dy = (self.dy / old_speed) * self.speed
            self.color = (100, 100, 100)  # 更深的灰色
            
    def draw(self):
        # 注意：绘制使用世界坐标，调用方会通过摄像机转换
        # 若有精灵，优先绘制精灵（按阶段与 size 缩放缓存），并进行两帧走路动画
        if self.sprite_images and isinstance(self.sprite_images, dict):
            frames = self.sprite_images.get(self.growth_stage)
            if frames is not None and len(frames) > 0:
                # 确保至少两帧
                if len(frames) == 1:
                    frames = [frames[0], frames[0]]
                key = (self.growth_stage, self.size)
                if key != self._cache_key or self._cached_scaled_frames is None or self._cached_flipped_frames is None:
                    wh = max(2 * int(self.size), 2)
                    try:
                        scaler = pygame.transform.smoothscale if CAT_IMAGE_FILTER == 'smooth' else pygame.transform.scale
                        scaled = [scaler(fr, (wh, wh)) for fr in frames[:2]]
                        flipped = [pygame.transform.flip(sf, True, False) for sf in scaled]
                        self._cached_scaled_frames = scaled
                        self._cached_flipped_frames = flipped
                    except Exception:
                        self._cached_scaled_frames = None
                        self._cached_flipped_frames = None
                    self._cache_key = key
                # 动画更新：根据位移判断是否行走
                moved_dist = math.hypot(self.x - self._last_draw_pos[0], self.y - self._last_draw_pos[1])
                is_moving = moved_dist > 0.2
                if is_moving:
                    self._anim_counter += 1
                    if self._anim_counter >= CAT_WALK_ANIM_INTERVAL_FRAMES:
                        self._anim_counter = 0
                        self._anim_frame = 1 - self._anim_frame
                else:
                    self._anim_counter = 0
                    self._anim_frame = 0
                self._last_draw_pos = (self.x, self.y)
                # 选择朝向与当前动画帧
                if self._cached_scaled_frames is not None and self._cached_flipped_frames is not None:
                    if self.facing_right:
                        chosen = self._cached_scaled_frames[self._anim_frame]
                    else:
                        chosen = self._cached_flipped_frames[self._anim_frame]
                    if chosen is not None:
                        blit_centered(screen, chosen, self.x, self.y)
                        return
        # 回退：绘制默认几何猫
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        eye_offset = self.size // 3
        pygame.draw.circle(screen, WHITE, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, WHITE, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, BLACK, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 12)
        pygame.draw.circle(screen, BLACK, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 12)
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
        # 可选：物品图像，由 Game 加载注入
        self.item_images = {"food": None, "toy": None}
        
    def throw_item(self, mouse_pos, cat_pos, game_ref=None):
        # 投掷物品
        expected_need = None
        if game_ref is not None:
            try:
                expected_need = game_ref.cat.get_current_need()
            except Exception:
                expected_need = None
        radius = 10
        # 预缩放物品贴图（若存在）
        base_img = self.item_images.get(self.selected_item)
        scaled_img = None
        if base_img is not None:
            try:
                wh = max(2 * radius, 2)
                # 按类型的视觉缩放
                item_extra = ITEM_IMAGE_SCALE.get(self.selected_item, 1.0)
                if item_extra != 1.0:
                    wh = max(1, int(round(wh * item_extra)))
                scaled_img = pygame.transform.smoothscale(base_img, (wh, wh))
            except Exception as e:
                log(f"Scale item image failed: {e}")
                scaled_img = None
        item = {
            "type": self.selected_item,
            "x": mouse_pos[0],
            "y": mouse_pos[1],
            "target_x": cat_pos[0],
            "target_y": cat_pos[1],
            "speed": 8,
            "radius": radius,
            "color": GREEN if self.selected_item == "food" else YELLOW,
            "thrown": True,
            "game_ref": game_ref,
            "expected_need": expected_need,
            "image": scaled_img,
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
        # 绘制投掷中的物品（优先使用贴图）
        for item in self.thrown_items:
            img = item.get("image")
            if img is not None:
                blit_centered(screen, img, item["x"], item["y"])
            else:
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
        self.started = False   # 是否已经开始（开始界面）
        self.paused = False    # 是否处于暂停
        # 字体：支持在 ./assets/ 下放置自定义 TTF（分别用于正文与标题）
        try:
            # 解析各自的字体路径
            body_font_path = _resolve_font_path(FONT_BODY_FILE if FONT_BODY_FILE else None)
            title_font_path = _resolve_font_path(FONT_TITLE_FILE if FONT_TITLE_FILE else None)
            # 若只提供了一个 TTF，则另一处自动复用该文件
            body_exists = bool(FONT_BODY_FILE) and os.path.exists(os.path.join(ASSETS_DIR, FONT_BODY_FILE))
            title_exists = bool(FONT_TITLE_FILE) and os.path.exists(os.path.join(ASSETS_DIR, FONT_TITLE_FILE))
            if not title_exists:
                title_font_path = body_font_path
            if not body_exists:
                body_font_path = title_font_path
            # 分别按不同字号创建：正文 vs 标题
            self.font = pygame.font.Font(body_font_path, max(1, int(FONT_BODY_SIZE)))
            self.large_font = pygame.font.Font(title_font_path, max(1, int(FONT_TITLE_SIZE)))
        except Exception:
            # 兜底：仍使用系统字体
            self.font = pygame.font.Font(font_path, 18)
            self.large_font = pygame.font.Font(font_path, 32)
        # 定义障碍物（矩形），位于工具栏下方区域，分布在大地图上
        self.obstacles = [
            # 左上区域
            pygame.Rect(150, 140, 120, 80),
            pygame.Rect(380, 260, 160, 90),
            pygame.Rect(620, 120, 100, 140),
            pygame.Rect(0, HEIGHT - 120, 140, 120),
            # 中部区域
            pygame.Rect(WIDTH + 200, 200, 140, 100),
            pygame.Rect(WIDTH + 500, 400, 120, 90),
            # 右侧区域
            pygame.Rect(WIDTH * 2 + 100, 150, 150, 110),
            pygame.Rect(WIDTH * 2 + 400, 350, 130, 95),
            # 下半部分
            pygame.Rect(200, HEIGHT + 200, 140, 85),
            pygame.Rect(WIDTH + 300, HEIGHT + 150, 160, 100),
        ]
        self.obstacle_color = (120, 120, 120)
        # 载入 PNG 素材（不存在会回退到默认图形）
        self._load_assets()
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
        self.need_text = "I want food!" if initial_need == "food" else "I want a toy!"
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
        # 至少完成的“完全躲藏”次数目标
        self.min_hide_goal = 3
        self.hide_completed = 0           # 已完成的完全躲藏次数
        self.hide_session_had_wait = False  # 本次躲藏是否进入过等待状态（即已到达内部）
        self.force_hide_cooldown = 0      # 强制触发的冷却，避免连续强制
        # 季节：0=normal, 1=winter；season_mix 为混合系数
        self.season_mix = 0.0
        self._season_direction = 1  # 1 -> winter, -1 -> normal
        self._season_hold = SEASON_HOLD_FRAMES
        
        # 地图切换系统
        self.map_transition_timer = SCENE_SWITCH_INTERVAL  # 距离下次自动离开的剩余帧数（20秒）
        self.cat_leaving = False          # 猫是否正在离开屏幕
        self.cat_leave_direction = None   # 猫离开的方向：'up', 'down', 'left', 'right'
        self.waiting_for_player = False   # 猫已离开，等待玩家按键切换地图

    def ensure_open_spot(self):
        """把猫从障碍物里挪到无遮挡位置，并确保不进入工具栏区域。"""
        # 先约束在屏幕可见区域（不进入工具栏）
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

    def _load_assets(self):
        """Load PNG assets and inject into Cat/Player/obstacle drawing with fallbacks."""
        # Cat sprites per growth stage with optional 2-frame animation
        def load_stage_frames(stage_n: int):
            f1 = load_image(f"cat_stage{stage_n}_1.png")
            f2 = load_image(f"cat_stage{stage_n}_2.png")
            if not f1 and not f2:
                base = load_image(f"cat_stage{stage_n}.png")
                if base:
                    return [base, base]
                return None
            # ensure two frames using fallback duplication
            return [f1 or f2, f2 or f1]

        st1 = load_stage_frames(1)
        st2 = load_stage_frames(2)
        st3 = load_stage_frames(3)
        if any([st1, st2, st3]):
            # Graceful fallback if some stages missing
            st1 = st1 or st2 or st3
            st2 = st2 or st1 or st3
            st3 = st3 or st2 or st1
            self.cat.sprite_images = {1: st1, 2: st2, 3: st3}
        # Item images (optional)
        self.player.item_images["food"] = load_image("food.png")
        self.player.item_images["toy"] = load_image("toy.png")
        # Helper for obstacle scaling and alignment
        def prepare_scaled(tex: pygame.Surface, r: pygame.Rect, idx: int, src_name: str):
            tw, th = tex.get_width(), tex.get_height()
            if tw <= 0 or th <= 0:
                return None
            if OBSTACLE_IMAGE_SCALE_MODE == 'stretch':
                new_w, new_h = r.width, r.height
            else:
                sx = r.width / tw
                sy = r.height / th
                scale = min(sx, sy) if OBSTACLE_IMAGE_SCALE_MODE == 'contain' else max(sx, sy)
                new_w = max(1, int(round(tw * scale)))
                new_h = max(1, int(round(th * scale)))
            extra = (
                OBSTACLE_IMAGE_GLOBAL_SCALE
                * OBSTACLE_IMAGE_PER_SCALE.get(idx + 1, 1.0)
                * OBSTACLE_IMAGE_PER_FILE_SCALE.get(src_name, 1.0)
            )
            if extra != 1.0:
                new_w = max(1, int(round(new_w * extra)))
                new_h = max(1, int(round(new_h * extra)))
            scaler = pygame.transform.smoothscale if OBSTACLE_IMAGE_FILTER == 'smooth' else pygame.transform.scale
            try:
                scaled = scaler(tex, (new_w, new_h))
            except Exception:
                return None
            if OBSTACLE_IMAGE_ALIGN == 'bottom':
                dx = (r.width - new_w) // 2
                dy = (r.height - new_h)
            else:
                dx = (r.width - new_w) // 2
                dy = (r.height - new_h) // 2
            return (scaled, dx, dy)

        # Obstacle textures: support normal and winter variants per obstacle, with shared fallbacks
        self.obstacle_surfs = []
        shared_norm = load_image("obstacle.png")
        shared_win = load_image("obstacle_winter.png") or load_image("obstacle_snow.png")
        for i, r in enumerate(self.obstacles):
            # normal
            name_norm = f"obstacle_{i+1}.png"
            tex_norm = load_image(name_norm) or shared_norm
            entry = None
            if tex_norm:
                entry = {"normal": prepare_scaled(tex_norm, r, i, name_norm if load_image(name_norm) else "obstacle.png"), "winter": None}
            # winter
            name_win_a = f"obstacle_{i+1}_winter.png"
            name_win_b = f"obstacle_{i+1}_snow.png"
            tex_win = load_image(name_win_a) or load_image(name_win_b) or shared_win
            if tex_win:
                if entry is None:
                    entry = {"normal": None, "winter": None}
                win_src = (
                    name_win_a if load_image(name_win_a) else (
                        name_win_b if load_image(name_win_b) else (
                            "obstacle_winter.png" if load_image("obstacle_winter.png") else "obstacle_snow.png"
                        )
                    )
                )
                entry["winter"] = prepare_scaled(tex_win, r, i, win_src)
            # If neither exists, keep None to draw rect; if only one exists, still store dict
            self.obstacle_surfs.append(entry)

        # 加载场景配置
        self.scenes = []
        self.current_scene_index = 0
        self.load_scenes_config()
        
        # 如果成功加载场景配置，使用场景系统
        if self.scenes:
            self.use_scene_system = True
            self.load_scene(0)  # 加载第一个场景
        else:
            # 否则使用旧的背景系统
            self.use_scene_system = False
            self.background_list = []
            self.current_background_index = 0
            
            # 尝试加载多张背景图
            for i in range(1, 11):
                bg_img = load_image(f"background_{i}.png")
                if bg_img is not None:
                    try:
                        scaled_bg = pygame.transform.smoothscale(bg_img, (WIDTH, HEIGHT))
                        self.background_list.append(scaled_bg)
                    except Exception:
                        pass
            
            # 如果没有找到编号的背景，加载默认背景
            if not self.background_list:
                bg_norm = load_image("background.png")
                if bg_norm is not None:
                    try:
                        self.background_list.append(pygame.transform.smoothscale(bg_norm, (WIDTH, HEIGHT)))
                    except Exception:
                        pass
            
            # 兼容旧的季节系统
            self.background_normal = self.background_list[0] if self.background_list else None
            self.background_winter = None
            bg_win = load_image("background_winter.png") or load_image("background_snow.png")
            if bg_win is not None:
                try:
                    self.background_winter = pygame.transform.smoothscale(bg_win, (WIDTH, HEIGHT))
                except Exception:
                    pass

    def load_scenes_config(self):
        """加载场景配置文件"""
        try:
            config_path = os.path.join("assets", "scenes.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scenes = data.get("scenes", [])
                    log(f"成功加载 {len(self.scenes)} 个场景配置")
            else:
                log("未找到 scenes.json 配置文件，使用默认背景系统")
        except Exception as e:
            log(f"加载场景配置失败: {e}")
            self.scenes = []
    
    def load_scene(self, scene_index):
        """加载指定场景的背景和障碍物"""
        if not self.scenes or scene_index >= len(self.scenes):
            return
        
        scene = self.scenes[scene_index]
        log(f"加载场景: {scene.get('name', f'Scene {scene_index}')}")
        
        # 加载背景
        bg_file = scene.get("background")
        if bg_file:
            bg_img = load_image(bg_file)
            if bg_img is not None:
                try:
                    self.background_normal = pygame.transform.smoothscale(bg_img, (WIDTH, HEIGHT))
                except Exception as e:
                    log(f"缩放背景失败: {e}")
        
        # 加载障碍物
        obstacles_config = scene.get("obstacles", [])
        self.obstacles = []
        self.obstacle_images = []  # 存储每个障碍物的图片
        
        for obs in obstacles_config:
            x = obs.get("x", 0)
            y = obs.get("y", 60)
            img_file = obs.get("image")
            
            # 加载障碍物图片并使用原始尺寸
            if img_file:
                img = load_image(img_file)
                if img is not None:
                    # 使用图片原始尺寸
                    width = img.get_width()
                    height = img.get_height()
                    
                    # 创建障碍物矩形
                    rect = pygame.Rect(x, y, width, height)
                    self.obstacles.append(rect)
                    self.obstacle_images.append(img)
                else:
                    # 如果图片加载失败，使用配置中的尺寸作为后备
                    width = obs.get("width", 100)
                    height = obs.get("height", 100)
                    rect = pygame.Rect(x, y, width, height)
                    self.obstacles.append(rect)
                    self.obstacle_images.append(None)
            else:
                # 如果没有指定图片，使用配置中的尺寸
                width = obs.get("width", 100)
                height = obs.get("height", 100)
                rect = pygame.Rect(x, y, width, height)
                self.obstacles.append(rect)
                self.obstacle_images.append(None)

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
            # 左/右侧隐藏（内部），允许从左/右露出，但不允许从底部露出
            side_sign = 1 if dx >= 0 else -1  # 鼠标在左 => 选右侧
            tx = nearest.centerx + side_sign * (nearest.width / 2 - inset_x)
            # y靠近当前值，但强制不超过障碍底边减去猫半径，避免从底部露出
            ty = clamp(cy, nearest.top + inset_y, nearest.bottom - inset_y)
            safe_bottom_y = nearest.bottom - self.cat.size - 1
            if safe_bottom_y >= nearest.top + inset_y:
                ty = min(ty, safe_bottom_y)
            else:
                # 极端情况下障碍太矮，靠近顶部
                ty = nearest.top + inset_y
        else:
            # 垂直方向：强制选择顶部内部（允许从上方或上角露出，禁止自底部露出）
            ty = nearest.top + inset_y
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
                # 开始界面：按 Enter / Space 开始
                if not self.started:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.started = True
                        return
                # 结算界面：R 重开 / Esc 退出
                if self.game_over:
                    if event.key == pygame.K_r:
                        # 重新开始本局
                        self.__init__()
                        return
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        return
                # 进行中：Z 暂停/继续
                if event.key == pygame.K_z and self.started and not self.game_over:
                    self.paused = not self.paused
                    return
                # 手动切换季节（已禁用）
                # if event.key == pygame.K_t and self.started and not self.paused and not self.game_over:
                #     self._season_direction = -1 if self.season_mix > 0.5 else 1
                #     self._season_hold = 0
                #     return
                # 非暂停时允许切换物品
                if event.key == pygame.K_SPACE and self.started and not self.paused and not self.game_over:
                    self.player.switch_item()
                # WASD切换地图（仅在等待玩家按键时生效）
                if self.started and not self.paused and not self.game_over and self.waiting_for_player:
                    if event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                        self.manual_map_switch()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    # 开始界面：任意左键开始
                    if not self.started:
                        self.started = True
                        return
                    # 暂停与结算期间不响应投掷
                    if self.paused or self.game_over:
                        return
                    # 进行中：检查是否点击工具栏外（游戏区域）
                    if event.pos[1] > 60:
                        self.player.throw_item(event.pos, (self.cat.x, self.cat.y), self)
    
    def _update_season(self):
        """Advance seasonal transition each frame.
        - Honors pause/start/game_over (no updates during those states)
        - Uses SEASON_TRANSITION_FRAMES for speed
        - Holds at ends for SEASON_HOLD_FRAMES
        - If SEASON_AUTO_CYCLE is True, bounces back and forth automatically
          otherwise stops direction at the end until manually toggled (T)
        """
        # Do not animate seasons when not started, paused, or after game over
        if not getattr(self, 'started', False) or getattr(self, 'paused', False) or getattr(self, 'game_over', False):
            return
        # Nothing to do if transition would be instantaneous or invalid
        if SEASON_TRANSITION_FRAMES <= 0:
            return
        # Respect hold timer when at ends
        if self._season_hold > 0:
            self._season_hold -= 1
            return
        # Progress mix in current direction
        step = 1.0 / float(SEASON_TRANSITION_FRAMES)
        self.season_mix += step * (1 if self._season_direction >= 0 else -1)
        # Clamp and handle endpoints
        if self.season_mix >= 1.0:
            self.season_mix = 1.0
            self._season_hold = SEASON_HOLD_FRAMES
            if SEASON_AUTO_CYCLE:
                self._season_direction = -1
            else:
                # Stop at end when not auto-cycling
                self._season_direction = 0
        elif self.season_mix <= 0.0:
            self.season_mix = 0.0
            self._season_hold = SEASON_HOLD_FRAMES
            if SEASON_AUTO_CYCLE:
                self._season_direction = 1
            else:
                # Stop at end when not auto-cycling
                self._season_direction = 0
        
    def _update_map_transition(self):
        """地图切换系统：猫每20秒自动走出屏幕，或玩家按WASD切换"""
        # 只在游戏进行时更新
        if not self.started or self.paused or self.game_over:
            return
        
        # 如果正在等待玩家按键，暂停所有更新
        if self.waiting_for_player:
            return
        
        # 如果猫正在离开屏幕
        if self.cat_leaving:
            self._move_cat_out()
            return
        
        # 正常状态：倒计时
        if self.map_transition_timer > 0:
            self.map_transition_timer -= 1
        else:
            # 时间到，触发自动离开
            self._trigger_cat_leave()
    
    def _trigger_cat_leave(self, direction=None):
        """触发猫离开屏幕"""
        if direction is None:
            # 随机选择方向
            direction = random.choice(['up', 'down', 'left', 'right'])
        
        self.cat_leaving = True
        self.cat_leave_direction = direction
        
        # 设置猫的移动方向
        speed = self.cat.speed * 1.5  # 加速离开
        if direction == 'up':
            self.cat.dx = 0
            self.cat.dy = -speed
        elif direction == 'down':
            self.cat.dx = 0
            self.cat.dy = speed
        elif direction == 'left':
            self.cat.dx = -speed
            self.cat.dy = 0
        else:  # right
            self.cat.dx = speed
            self.cat.dy = 0
        
        # 清除躲藏状态
        self.hide_target = None
        self.hide_frames = 0
        self.hide_waiting = False
        self.idle_frames = 0
    
    def _move_cat_out(self):
        """让猫持续移动直到完全离开屏幕"""
        # 移动猫
        self.cat.x += self.cat.dx
        self.cat.y += self.cat.dy
        
        # 检查是否完全离开屏幕（包括猫的大小）
        margin = self.cat.size + 10
        left_screen = (self.cat_leave_direction == 'left' and self.cat.x < -margin) or \
                      (self.cat_leave_direction == 'right' and self.cat.x > WIDTH + margin) or \
                      (self.cat_leave_direction == 'up' and self.cat.y < -margin) or \
                      (self.cat_leave_direction == 'down' and self.cat.y > HEIGHT + margin)
        
        if left_screen:
            # 猫已完全离开，进入等待玩家按键状态
            self.cat_leaving = False
            self.waiting_for_player = True
    
    def _switch_map_instantly(self):
        """立即切换地图并让猫从对面进入"""
        # 使用场景系统或背景列表
        if self.use_scene_system and self.scenes:
            # 切换到下一个场景
            self.current_scene_index = (self.current_scene_index + 1) % len(self.scenes)
            self.load_scene(self.current_scene_index)
        elif self.background_list:
            # 使用旧的背景系统
            self.current_background_index = (self.current_background_index + 1) % len(self.background_list)
            self.background_normal = self.background_list[self.current_background_index]
            
            # 重新生成障碍物（旧系统）
            for i, rect in enumerate(self.obstacles):
                new_x = random.randint(0, WIDTH - rect.width)
                new_y = random.randint(60 + rect.height // 2, HEIGHT - rect.height // 2)
                self.obstacles[i] = pygame.Rect(new_x, new_y, rect.width, rect.height)
        
        # 从对面边缘进入
        margin = self.cat.size
        if self.cat_leave_direction == 'left':
            self.cat.x = WIDTH + margin
            self.cat.y = random.randint(60 + margin, HEIGHT - margin)
            self.cat.dx = -self.cat.speed
            self.cat.dy = random.choice([-1, 1]) * self.cat.speed * 0.5
        elif self.cat_leave_direction == 'right':
            self.cat.x = -margin
            self.cat.y = random.randint(60 + margin, HEIGHT - margin)
            self.cat.dx = self.cat.speed
            self.cat.dy = random.choice([-1, 1]) * self.cat.speed * 0.5
        elif self.cat_leave_direction == 'up':
            self.cat.x = random.randint(margin, WIDTH - margin)
            self.cat.y = HEIGHT + margin
            self.cat.dx = random.choice([-1, 1]) * self.cat.speed * 0.5
            self.cat.dy = -self.cat.speed
        else:  # down
            self.cat.x = random.randint(margin, WIDTH - margin)
            self.cat.y = -margin
            self.cat.dx = random.choice([-1, 1]) * self.cat.speed * 0.5
            self.cat.dy = self.cat.speed
        
        # 重置状态
        log(f"新障碍物位置: {[(r.x, r.y) for r in self.obstacles[:3]]}")
        log(f"猫新位置: ({self.cat.x}, {self.cat.y}), 方向: ({self.cat.dx}, {self.cat.dy})")
        log(f"=== 地图切换完成 ===")
        self.cat_leaving = False
        self.waiting_for_player = False
        self.cat_leave_direction = None
        self.map_transition_timer = SCENE_SWITCH_INTERVAL  # 重置20秒计时
        
        # 不清除投掷物，让游戏继续
        # self.player.thrown_items.clear()  # 注释掉，保持游戏状态
    
    def manual_map_switch(self, direction=None):
        """玩家手动切换地图（WASD）- 只在等待状态时调用"""
        # 执行地图切换
        if self.waiting_for_player:
            self._switch_map_instantly()
    
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
                return True, "Correct! +1"
            else:
                # 投错了物品：不加分
                self.player.consecutive_wrong += 1
                if self.player.consecutive_wrong > 3:
                    self.cat.affinity = max(0, self.cat.affinity - 2)
                return True, "Not this one!"
        return False, ""

    def draw_obstacles(self):
        # 如果使用场景系统，直接绘制障碍物图片
        if self.use_scene_system and hasattr(self, 'obstacle_images'):
            for i, rect in enumerate(self.obstacles):
                if i < len(self.obstacle_images) and self.obstacle_images[i] is not None:
                    screen.blit(self.obstacle_images[i], rect.topleft)
                else:
                    # 没有图片时绘制矩形
                    pygame.draw.rect(screen, self.obstacle_color, rect)
            return
        
        # 旧系统：绘制障碍物with季节交叉淡入
        mix = clamp(self.season_mix, 0.0, 1.0)
        for i, rect in enumerate(self.obstacles):
            entry = None
            if hasattr(self, "obstacle_surfs") and i < len(self.obstacle_surfs):
                entry = self.obstacle_surfs[i]
            # 兼容旧结构：tuple 或 surface
            if isinstance(entry, tuple) and len(entry) == 3 and entry[0] is not None:
                tex, dx, dy = entry
                screen.blit(tex, (rect.left + dx, rect.top + dy))
                continue
            if entry is not None and hasattr(entry, 'get_width'):
                screen.blit(entry, rect.topleft)
                continue
            if not isinstance(entry, dict):
                pygame.draw.rect(screen, self.obstacle_color, rect)
                continue
            base = entry.get("normal")
            win = entry.get("winter")
            if base is None and win is None:
                pygame.draw.rect(screen, self.obstacle_color, rect)
                continue
            if base is not None and win is not None and 0.0 < mix < 1.0:
                btex, bdx, bdy = base
                wtex, wdx, wdy = win
                prev_ba = btex.get_alpha()
                prev_wa = wtex.get_alpha()
                alpha_b = int(255 * (1.0 - mix))
                alpha_w = int(255 * mix)
                if alpha_b > 0:
                    btex.set_alpha(alpha_b)
                    screen.blit(btex, (rect.left + bdx, rect.top + bdy))
                if alpha_w > 0:
                    wtex.set_alpha(alpha_w)
                    screen.blit(wtex, (rect.left + wdx, rect.top + wdy))
                btex.set_alpha(prev_ba)
                wtex.set_alpha(prev_wa)
            else:
                if mix >= 1.0 and win is not None:
                    wtex, wdx, wdy = win
                    screen.blit(wtex, (rect.left + wdx, rect.top + wdy))
                elif base is not None:
                    btex, bdx, bdy = base
                    screen.blit(btex, (rect.left + bdx, rect.top + bdy))
                else:
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
        # 绘制工具栏背景
        pygame.draw.rect(screen, (200, 200, 200), (0, 0, WIDTH, 60))

        # 两行布局，避免重叠
        gap = 12
        left_x = 12
        right_x = WIDTH - 12
        row1_y = 8
        row2_y = 32

        # Row1-Left: Selected
        selected_text = f"Selected: {'Food' if self.player.selected_item == 'food' else 'Toy'}"
        sel_surf = self.font.render(selected_text, True, BLACK)
        screen.blit(sel_surf, (left_x, row1_y))

        # Row1-Right: Stage
        stage_text = f"Stage: {self.cat.growth_stage}"
        stage_surf = self.font.render(stage_text, True, BLACK)
        screen.blit(stage_surf, (right_x - stage_surf.get_width(), row1_y))

        # Row1-Center: Timer (centered)
        if hasattr(self, 'time_left'):
            secs = max(0, int(self.time_left // FPS))
            timer_text = f"Time Left: {secs:02d}s"
            timer_surf = self.font.render(timer_text, True, BLACK)
            screen.blit(timer_surf, (WIDTH//2 - timer_surf.get_width()//2, row1_y))

        # Row2-Left: Score + Wrong
        score_text = f"Score: {self.player.score}"
        score_surf = self.font.render(score_text, True, BLACK)
        screen.blit(score_surf, (left_x, row2_y))

        wrong = self.player.consecutive_wrong if hasattr(self.player, 'consecutive_wrong') else 0
        wrong_color = RED if wrong > 3 else BLACK
        wrong_text = f"Wrong: {wrong}"
        wrong_surf = self.font.render(wrong_text, True, wrong_color)
        screen.blit(wrong_surf, (left_x + score_surf.get_width() + gap, row2_y))

        # Row2-Right: Affinity
        affinity_text = f"Affinity: {int(self.cat.affinity)}%"
        affinity_surf = self.font.render(affinity_text, True, BLACK)
        screen.blit(affinity_surf, (right_x - affinity_surf.get_width(), row2_y))

        # 需求提示（红字）已按用户要求移除，不再显示
        
    def run(self):
        log("Game loop entering...")
        ticks = 0
        while self.running:
            # 更新季节过渡（若需要）
            self._update_season()
            # 更新地图切换
            self._update_map_transition()
            
            # 清屏
            screen.fill(WHITE)
            
            # 背景：支持季节过渡（normal -> winter）
            if hasattr(self, "background_normal") or hasattr(self, "background_winter"):
                mix = clamp(self.season_mix, 0.0, 1.0)
                bn = getattr(self, 'background_normal', None)
                bw = getattr(self, 'background_winter', None)
                if bn is not None and bw is not None and 0.0 < mix < 1.0:
                    prev_bn_alpha = bn.get_alpha()
                    prev_bw_alpha = bw.get_alpha()
                    alpha_bn = int(255 * (1.0 - mix))
                    alpha_bw = int(255 * mix)
                    if alpha_bn > 0:
                        bn.set_alpha(alpha_bn)
                        screen.blit(bn, (0, 0))
                    if alpha_bw > 0:
                        bw.set_alpha(alpha_bw)
                        screen.blit(bw, (0, 0))
                    bn.set_alpha(prev_bn_alpha)
                    bw.set_alpha(prev_bw_alpha)
                else:
                    if mix >= 1.0 and bw is not None:
                        screen.blit(bw, (0, 0))
                    elif bn is not None:
                        screen.blit(bn, (0, 0))
            
            # 处理事件
            self.handle_events()
            
            # 开始界面：显示开始提示，未开始不更新游戏状态
            if not self.started:
                # 半透明遮罩与标题
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                screen.blit(overlay, (0, 0))
                title = "FEED YOUR CAT"
                sub = "Press Enter or Click to Start"
                # 控制说明每个操作一行，逐行居中
                ctrl_lines = [
                    "Left Click = Throw",
                    "Space = Switch Item",
                    "Z = Pause/Resume"
                ]
                t_surf = self.large_font.render(title, True, WHITE)
                s_surf = self.font.render(sub, True, WHITE)
                ctrl_surfs = [self.font.render(line, True, WHITE) for line in ctrl_lines]
                # 在安全区域内垂直居中布局，避免被边缘遮挡
                safe_top = 70
                safe_bottom = HEIGHT - 20
                spacing = 12
                block_h = (
                    t_surf.get_height()
                    + spacing + s_surf.get_height()
                    + spacing * len(ctrl_surfs) + sum(cs.get_height() for cs in ctrl_surfs)
                )
                y = max(safe_top, min((HEIGHT - block_h) // 2, safe_bottom - block_h))
                cx = WIDTH // 2
                # 标题
                screen.blit(t_surf, (cx - t_surf.get_width() // 2, y))
                y += t_surf.get_height() + spacing
                # 子标题
                screen.blit(s_surf, (cx - s_surf.get_width() // 2, y))
                y += s_surf.get_height() + spacing
                # 控制说明（每个操作一行）
                for cs in ctrl_surfs:
                    screen.blit(cs, (cx - cs.get_width() // 2, y))
                    y += cs.get_height() + spacing
                pygame.display.flip()
                clock.tick(FPS)
                continue
            # 游戏结束态：只显示结算面板与UI，等待R/ESC
            if self.game_over:
                # 背景可依然绘制基本元素，简单起见绘制UI与结束面板
                self.draw_ui()
                # 半透明遮罩
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                screen.blit(overlay, (0, 0))
                # 文本
                title = "Victory!" if self.game_result == 'win' else ("Defeat" if self.game_result == 'lose' else "Time's Up")
                t_surf = self.large_font.render(title, True, WHITE)
                msg_surf = self.font.render(self.end_message, True, WHITE)
                hint_surf = self.font.render("Press R to restart / Esc to exit", True, WHITE)
                cx = WIDTH//2
                screen.blit(t_surf, (cx - t_surf.get_width()//2, HEIGHT//2 - 70))
                screen.blit(msg_surf, (cx - msg_surf.get_width()//2, HEIGHT//2 - 20))
                screen.blit(hint_surf, (cx - hint_surf.get_width()//2, HEIGHT//2 + 30))
                pygame.display.flip()
                clock.tick(FPS)
                continue
            # 暂停态：显示当前画面 + 暂停提示，不更新状态/计时
            if self.paused:
                # 绘制当前场景
                self.cat.draw()
                self.player.draw_items()
                self.draw_obstacles()
                self.draw_speech_bubble()
                self.draw_ui()
                # 覆盖暂停提示
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 100))
                screen.blit(overlay, (0, 0))
                p_surf = self.large_font.render("Paused", True, WHITE)
                hint_surf = self.font.render("Press Z to resume", True, WHITE)
                cx = WIDTH//2
                screen.blit(p_surf, (cx - p_surf.get_width()//2, HEIGHT//2 - 20))
                screen.blit(hint_surf, (cx - hint_surf.get_width()//2, HEIGHT//2 + 24))
                pygame.display.flip()
                clock.tick(FPS)
                continue
            
            # 更新游戏状态
            mouse_pos = pygame.mouse.get_pos()
            
            # 如果猫正在离开屏幕，跳过正常游戏逻辑
            # 等待玩家状态下游戏继续运行（只是不显示猫）
            if not self.cat_leaving and not self.waiting_for_player:
                # 正常游戏逻辑
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
                        # 计算新位置
                        new_x = self.cat.x + (dx / dist) * step
                        new_y = self.cat.y + (dy / dist) * step
                        
                        # 限制在屏幕边界内（不能超出）
                        min_x = self.cat.size
                        max_x = WIDTH - self.cat.size
                        min_y = 60 + self.cat.size
                        max_y = HEIGHT - self.cat.size
                        
                        self.cat.x = max(min_x, min(max_x, new_x))
                        self.cat.y = max(min_y, min(max_y, new_y))
                        
                        # 根据目标方向更新朝向，以便隐藏过程中也镜像正确
                        if abs(dx) > 1e-3:
                            self.cat.facing_right = (dx >= 0)
                    else:
                        # 到达目标，固定在目标点等待剩余时间
                        self.cat.x, self.cat.y = hx, hy
                        self.hide_waiting = True
                        self.hide_session_had_wait = True
                    self.hide_frames -= 1
                    if self.hide_frames <= 0:
                        # 结束一次躲藏会话，若曾成功到达内部，则计入完成次数
                        if self.hide_session_had_wait:
                            self.hide_completed += 1
                        self.hide_session_had_wait = False
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
                        message = "Blocked by obstacle!"
                    else:
                        hit, message = self.check_collision(hit_item)
            elif self.waiting_for_player:
                # 等待玩家按键状态：更新投掷物但不与猫碰撞
                hit_item = self.player.update_items()
                message = ""
            else:
                # 猫正在离开，不处理游戏逻辑
                message = ""
            
            # 绘制游戏元素（等待玩家时不绘制猫）
            if not self.waiting_for_player:
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
            if self.force_hide_cooldown > 0:
                self.force_hide_cooldown -= 1
            # 定期（每3-5秒随机）刷新对话文本
            if hasattr(self, "_need_frames_left"):
                self._need_frames_left -= 1
                if self._need_frames_left <= 0:
                    need = self.cat.get_current_need()
                    self.need_text = "I want food!" if need == "food" else "I want a toy!"
                    self._need_frames_left = random.randint(BUBBLE_REFRESH_MIN_FRAMES, BUBBLE_REFRESH_MAX_FRAMES)
            # 计时与胜负判定
            if self.time_left > 0:
                self.time_left -= 1
            if self.loss_grace > 0:
                self.loss_grace -= 1
            if self.loss_grace <= 0 and self.cat.affinity <= 0 and not self.game_over:
                self.game_over = True
                self.game_result = 'lose'
                self.end_message = "Affinity dropped to 0. The cat ran away..."
            if self.time_left <= 0 and not self.game_over:
                if self.cat.affinity >= 80 or self.cat.growth_stage >= 3:
                    self.game_over = True
                    self.game_result = 'win'
                    self.end_message = f"Congrats! Final Score {self.player.score}; Affinity {int(self.cat.affinity)}%"
                else:
                    self.game_over = True
                    self.game_result = 'summary'
                    self.end_message = f"Time's up. Score {self.player.score}; Affinity {int(self.cat.affinity)}%, Stage {self.cat.growth_stage}"

            # 保障：至少完成3次“完全躲藏”
            # 在不处于躲藏/停驻/冷却时，若完成次数不足则强制触发一次，并保证有足够时间走到目标后再等待≥1s
            if (not self.game_over and self.started and not self.paused 
                and self.hide_frames <= 0 and not self.hide_waiting 
                and self.idle_frames <= 0 and self.hide_cooldown <= 0 
                and self.force_hide_cooldown <= 0 and self.hide_completed < self.min_hide_goal):
                mx, my = pygame.mouse.get_pos()
                if my > 60:
                    target = self.compute_hide_spot((mx, my))
                    self.hide_target = target
                    # 计算到目标距离，给足行进帧数 + 至少1.2秒的停留
                    dx = target[0] - self.cat.x
                    dy = target[1] - self.cat.y
                    dist = math.hypot(dx, dy)
                    travel_frames = int(math.ceil((dist / max(1e-6, self.cat.speed))))
                    wait_frames = int(1.2 * FPS)
                    self.hide_frames = max(HIDE_DURATION_MIN_FRAMES, travel_frames + wait_frames)
                    self.force_hide_cooldown = int(5 * FPS)

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