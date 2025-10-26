import pygame
import random
import sys
import math
import os
import json
import traceback
from datetime import datetime
from typing import Tuple

# Initialize pygame
pygame.init()

# Ensure proper font display
pygame.font.init()
font_path = pygame.font.match_font('simsun') or pygame.font.match_font('microsoftyahei')
if not font_path:
    # If Chinese font not found, use default font
    default_font = pygame.font.get_default_font()
    font_path = pygame.font.match_font(default_font)

# Game constants
WIDTH, HEIGHT = 800, 600
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# --- Adjustable Parameters (Constants) ---
# Hide-and-seek trigger settings
HIDE_NEAR_DISTANCE = 180            # Mouse distance below this triggers cat hiding behavior
HIDE_TRIGGER_RANDOM_CHANCE = 0.002  # Random chance per frame to trigger hiding (smaller = less hiding)
HIDE_DURATION_MIN_FRAMES = int(1.0 * FPS)   # Minimum hiding duration ~1s
HIDE_DURATION_MAX_FRAMES = int(2.0 * FPS)   # Maximum hiding duration ~2s
HIDE_COOLDOWN_FRAMES = int(3 * FPS)       # Cooldown after hiding to avoid excessive frequency
HIDE_INSET_MIN = 6                  # Minimum pixel inset from obstacle edge when hiding
HIDE_INSET_FRACTION = 0.25          # Inset amount as fraction of obstacle dimensions

# Speech bubble settings
BUBBLE_SMOOTH_ALPHA = 0.28          # Exponential smoothing coefficient for bubble position (0-1, smaller = more stable)
BUBBLE_TAIL_LEN = 14
BUBBLE_TAIL_W = 12
BUBBLE_REFRESH_MIN_FRAMES = 3 * FPS
BUBBLE_REFRESH_MAX_FRAMES = 5 * FPS
BUBBLE_STICKY_BIAS_PX = 60          # Sticky bias: current direction enjoys reduced distance weighting to avoid frequent switching
BUBBLE_MOUSE_BIAS_DISTANCE = 200     # Only enable "near player" bias when mouse distance to cat is below this

# --- Game Flow Settings ---
GAME_DURATION_FRAMES = 60 * FPS      # Total duration: 60 seconds
LOSS_GRACE_FRAMES = 30 * FPS         # No affinity=0 failure check for first 30 seconds

# Idle (unobstructed area) settings
IDLE_INTERVAL_FRAMES = 10 * FPS
IDLE_DURATION_MIN_FRAMES = int(3 * FPS)
IDLE_DURATION_MAX_FRAMES = int(4 * FPS)

# Movement speed adjustments
CAT_OPEN_SPEED_FACTOR = 0.6  # Cat movement speed in open areas (relative to Cat.speed)
CAT_SPEED_STAGE_1 = 5        # Initial stage speed
CAT_SPEED_STAGE_2 = 7        # Stage 2 speed (when affinity≥30)
CAT_SPEED_STAGE_3 = 9        # Stage 3 speed (when affinity≥60)

# Cat sprite scaling filter: recommend 'nearest'，for realistic style 'smooth'
CAT_IMAGE_FILTER = 'smooth'

# Cat walk animation: frame switch interval (frames)
CAT_WALK_ANIM_INTERVAL_FRAMES = max(1, int(0.12 * FPS))

# Obstacle sprite scaling strategy (avoid distortion)
# scale mode: 'contain' fit without distortion (may have margins)，'cover' fill (may exceed rect)，'stretch' fill with distortion
OBSTACLE_IMAGE_SCALE_MODE = 'contain'
# Scaling filter: recommend 'nearest'，for realistic style 'smooth'
OBSTACLE_IMAGE_FILTER = 'nearest'
# Alignment: 'center' centered，'bottom' bottom-aligned (e.g. tree roots on ground)
OBSTACLE_IMAGE_ALIGN = 'bottom'

# Global sprite scale multiplier (visual only, doesn't change collision rect; 1.0 = unchanged)
OBSTACLE_IMAGE_GLOBAL_SCALE = 1.25
# Optional: per-obstacle index scaling, e.g. {1:1.0, 2:1.0, 3:1.4}
OBSTACLE_IMAGE_PER_SCALE = {2: 0.8, 1: 1.2, 3: 0.9, 4: 1.2}
# Optional: per-filename scaling (when using obstacle_*.png or obstacle.png)
OBSTACLE_IMAGE_PER_FILE_SCALE = {"obstacle_2.png": 0.8}

# Item sprite scaling (visual only), by type: 'food' and 'toy'
ITEM_IMAGE_SCALE = {"food": 2.0, "toy": 1.0}

# Season transition (obstacle sprites/background Normal <-> Winter)
SEASON_AUTO_CYCLE = False                # Disable auto cycling
SEASON_HOLD_FRAMES = 8 * FPS             # Duration to hold each season
SEASON_TRANSITION_FRAMES = 1             # Transition duration (1 frame = instant switch)

# Scene switching system (Plan A: multi-scene auto switching)
SCENE_SWITCH_INTERVAL = 20 * FPS         # Scene switch interval (20 seconds)
SCENE_SWITCH_FADE_FRAMES = int(0.5 * FPS)  # Fade in/out duration (0.5 seconds)

# Font configuration (place your TTF files in ./assets/ to take effect)
# Example: assets/ui_body.ttf and assets/ui_title.ttf
FONT_BODY_FILE = "MyFont.ttf"     # Body font filename (empty string means not specified)
FONT_TITLE_FILE = "MyFont.ttf"   # Title font filename (empty string means not specified)
FONT_BODY_SIZE = 12                 # Body font size
FONT_TITLE_SIZE = 24                # Title font size

# Create log function (print to console and write to file for debugging)
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
    # Find nearest point on rect to circle center
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx*dx + dy*dy) <= (r*r)

def resolve_circle_rect_collision(cx: float, cy: float, r: float, rect: pygame.Rect, vx: float, vy: float) -> Tuple[float, float, float, float]:
    """Push circle out of rect and reflect velocity to reduce jitter/edge sticking.
    Returns new (cx, cy, vx, vy)
    """
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    nx = cx - nearest_x
    ny = cy - nearest_y
    dist2 = nx*nx + ny*ny
    if dist2 == 0:
        # Circle center exactly at nearest point, choose default normal (upward)
        nx, ny = 0.0, -1.0
        dist = 1.0
    else:
        dist = math.sqrt(dist2)
        nx /= dist
        ny /= dist
    # Push out overlap
    overlap = r - dist
    if overlap > 0:
        cx += nx * (overlap + 0.5)
        cy += ny * (overlap + 0.5)
        # Reflect velocity along normal
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

def draw_pixel_fish(size=20):
    """Draw pixel art fish (dried fish)"""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pixel = max(1, size // 10)  # Pixel block size
    
    # Define pixel pattern for fish (coordinates relative to center)
    # Fish body (orange-yellow)
    fish_body = [
        # Fish head
        (-3, -2), (-3, -1), (-3, 0), (-3, 1), (-3, 2),
        (-2, -3), (-2, -2), (-2, -1), (-2, 0), (-2, 1), (-2, 2), (-2, 3),
        (-1, -3), (-1, -2), (-1, -1), (-1, 0), (-1, 1), (-1, 2), (-1, 3),
        (0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
        # Fish tail
        (1, -1), (1, 0), (1, 1),
        (2, -2), (2, 0), (2, 2),
        (3, -3), (3, -1), (3, 1), (3, 3),
    ]
    
    # Fish eye (dark)
    fish_eye = [(-2, -1)]
    
    # Draw fish body
    center_x, center_y = size // 2, size // 2
    for px, py in fish_body:
        x = center_x + px * pixel
        y = center_y + py * pixel
        pygame.draw.rect(surf, (255, 200, 100), (x, y, pixel, pixel))  # Orange-yellow
    
    # Draw fish eye
    for px, py in fish_eye:
        x = center_x + px * pixel
        y = center_y + py * pixel
        pygame.draw.rect(surf, (80, 60, 40), (x, y, pixel, pixel))  # Dark color
    
    # Add outline
    for px, py in fish_body:
        x = center_x + px * pixel
        y = center_y + py * pixel
        pygame.draw.rect(surf, (200, 150, 80), (x, y, pixel, pixel), 1)  # Border
    
    return surf

def draw_pixel_toy(size=20):
    """Draw pixel art toy (yarn ball) - rounder version"""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pixel = max(1, size // 10)
    
    # Rounder yarn ball pattern (using circle algorithm)
    ball_pixels = [
        # Top layer (y=-4)
        (-1, -4), (0, -4), (1, -4),
        # Second layer (y=-3)
        (-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3),
        # Third layer (y=-2)
        (-3, -2), (-2, -2), (-1, -2), (0, -2), (1, -2), (2, -2), (3, -2),
        # Middle layer (y=-1)
        (-3, -1), (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1), (3, -1),
        # Center layer (y=0)
        (-4, 0), (-3, 0), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0), (4, 0),
        # Middle layer (y=1)
        (-3, 1), (-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1), (3, 1),
        # Third layer (y=2)
        (-3, 2), (-2, 2), (-1, 2), (0, 2), (1, 2), (2, 2), (3, 2),
        # Second layer (y=3)
        (-2, 3), (-1, 3), (0, 3), (1, 3), (2, 3),
        # Bottom layer (y=4)
        (-1, 4), (0, 4), (1, 4),
    ]
    
    # Thread pattern (dark)- spiral threads
    yarn_lines = [
        # Diagonal 1
        (-2, -2), (-1, -1), (0, 0), (1, 1), (2, 2),
        # Diagonal 2
        (-2, 2), (-1, 1), (1, -1), (2, -2),
        # Horizontal line
        (-2, 0), (2, 0),
    ]
    
    center_x, center_y = size // 2, size // 2
    
    # Draw sphere
    for px, py in ball_pixels:
        x = center_x + px * pixel
        y = center_y + py * pixel
        pygame.draw.rect(surf, (255, 100, 150), (x, y, pixel, pixel))  # Pink
    
    # Draw threads
    for px, py in yarn_lines:
        x = center_x + px * pixel
        y = center_y + py * pixel
        pygame.draw.rect(surf, (200, 50, 100), (x, y, pixel, pixel))  # Deep pink
    
    return surf

log("Program start: initializing display window...")

# Create game window (catch exceptions, log)
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
        # Initial attributes
        self.size = 30
        self.x = random.randint(self.size, WIDTH - self.size)
        self.y = random.randint(self.size, HEIGHT - self.size)
        self.speed = CAT_SPEED_STAGE_1
        self.dx = random.choice([-1, 1]) * self.speed
        self.dy = random.choice([-1, 1]) * self.speed
        self.color = (169, 169, 169)  # Gray
        self.hunger = 50  # Hunger 0-100
        self.playfulness = 50  # Playfulness 0-100
        self.affinity = 0  # Affinity 0-100
        self.growth_stage = 1  # Growth stage
        # Optional: stage sprites, injected by Game {1: [Surface, Surface], 2: [...], 3: [...]}
        # If only 1 frame provided, duplicated to 2 frames during loading
        self.sprite_images = None
        self._cache_key = None  # (stage, size)
        # Frame-by-frame cache (after size & stage scaling): [[frame0, frame1], flipped same for flipped]
        self._cached_scaled_frames = None
        self._cached_flipped_frames = None
        # Legacy fields (no longer used)
        self._cached_scaled = None
        self._cached_flipped = None  # Horizontal flip cache
        self.facing_right = True     # Facing direction, updated based on dx
        # Animation state
        self._anim_frame = 0
        self._anim_counter = 0
        self._last_draw_pos = (self.x, self.y)
        
    def move(self, speed_scale: float = 1.0, check_bounds: bool = True):
        # Remove jitter: no random direction change, only move in current direction at constant speed

        # First update position
        self.x += self.dx * speed_scale
        self.y += self.dy * speed_scale

        # Screen boundaries (only active when check_bounds=True)
        if check_bounds:
            min_x = self.size
            max_x = WIDTH - self.size
            min_y = 60 + self.size  # Reserve top toolbar
            max_y = HEIGHT - self.size

            # X-axis boundary bounce
            if self.x < min_x:
                self.x = min_x
                self.dx *= -1
            elif self.x > max_x:
                self.x = max_x
                self.dx *= -1

            # Y-axis boundary bounce
            if self.y < min_y:
                self.y = min_y
                self.dy *= -1
            elif self.y > max_y:
                self.y = max_y
                self.dy *= -1
        
        # Update facing (based on current horizontal velocity)
        self.facing_right = (self.dx >= 0)
            
        # Randomly change needs
        if random.random() < 0.01:
            self.hunger = min(100, self.hunger + random.randint(1, 3))
            self.playfulness = max(0, self.playfulness - random.randint(1, 2))
        if random.random() < 0.01:
            self.playfulness = min(100, self.playfulness + random.randint(1, 3))
            self.hunger = max(0, self.hunger - random.randint(1, 2))
            
    def grow(self):
        # Growth logic: speed increases on each level up
        if self.affinity >= 30 and self.growth_stage == 1:
            self.growth_stage = 2
            self.size = 45
            old_speed = self.speed
            self.speed = CAT_SPEED_STAGE_2
            # Keep direction, update velocity components
            if old_speed > 0:
                self.dx = (self.dx / old_speed) * self.speed
                self.dy = (self.dy / old_speed) * self.speed
            self.color = (130, 130, 130)  # dark gray
        elif self.affinity >= 60 and self.growth_stage == 2:
            self.growth_stage = 3
            self.size = 60
            old_speed = self.speed
            self.speed = CAT_SPEED_STAGE_3
            # Keep direction, update velocity components
            if old_speed > 0:
                self.dx = (self.dx / old_speed) * self.speed
                self.dy = (self.dy / old_speed) * self.speed
            self.color = (100, 100, 100)  # darker gray
            
    def draw(self):
        # Note: drawing uses world coordinates, caller will convert via camera
        # If sprite exists, draw sprite first (cached by stage & size scaling), with two-frame walk animation
        if self.sprite_images and isinstance(self.sprite_images, dict):
            frames = self.sprite_images.get(self.growth_stage)
            if frames is not None and len(frames) > 0:
                # Ensure at least two frames
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
                # Animation update: determine walking based on displacement
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
                # Select facing direction and current animation frame
                if self._cached_scaled_frames is not None and self._cached_flipped_frames is not None:
                    if self.facing_right:
                        chosen = self._cached_scaled_frames[self._anim_frame]
                    else:
                        chosen = self._cached_flipped_frames[self._anim_frame]
                    if chosen is not None:
                        blit_centered(screen, chosen, self.x, self.y)
                        return
        # Fallback: draw default geometric cat
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        eye_offset = self.size // 3
        pygame.draw.circle(screen, WHITE, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, WHITE, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 6)
        pygame.draw.circle(screen, BLACK, (int(self.x) - eye_offset, int(self.y) - eye_offset//2), self.size // 12)
        pygame.draw.circle(screen, BLACK, (int(self.x) + eye_offset, int(self.y) - eye_offset//2), self.size // 12)
        pygame.draw.line(screen, BLACK, (int(self.x), int(self.y)), (int(self.x), int(self.y) + self.size//4), 2)
        
    def get_current_need(self):
        # Determine current main need
        if self.hunger > self.playfulness + 20:
            return "food"  # needs food
        elif self.playfulness > self.hunger + 20:
            return "toy"   # needs toy
        else:
            return random.choice(["food", "toy"])  # balanced needs, random choice

class Player:
    def __init__(self):
        self.score = 0
        self.selected_item = "food"  # food selected by default
        self.thrown_items = []
        self.landed_items = []  # landed items
        self.consecutive_wrong = 0  # consecutive wrong hits
        # Optional: item images, loaded and injected by Game
        self.item_images = {"food": None, "toy": None}
        
    def throw_item(self, mouse_pos, cat_pos, game_ref=None):
        # Throw item
        expected_need = None
        if game_ref is not None:
            try:
                expected_need = game_ref.cat.get_current_need()
            except Exception:
                expected_need = None
        radius = 10
        # Pre-scale item sprite (if exists)
        base_img = self.item_images.get(self.selected_item)
        scaled_img = None
        
        # Prefer pixel art if available, use pixel pattern if no assets
        if base_img is None:
            # Use pixel art drawing
            if self.selected_item == "food":
                base_img = draw_pixel_fish(20)
            else:  # toy
                base_img = draw_pixel_toy(20)
        
        if base_img is not None:
            try:
                wh = max(2 * radius, 2)
                # Visual scaling by type
                item_extra = ITEM_IMAGE_SCALE.get(self.selected_item, 1.0)
                if item_extra != 1.0:
                    wh = max(1, int(round(wh * item_extra)))
                scaled_img = pygame.transform.smoothscale(base_img, (wh, wh))
            except Exception as e:
                log(f"Scale item image failed: {e}")
                scaled_img = None
        # Calculate parabolic motion parameters
        dx = cat_pos[0] - mouse_pos[0]
        dy = cat_pos[1] - mouse_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        flight_time = max(30, distance / 8)  # Flight time (frames)
        
        item = {
            "type": self.selected_item,
            "x": mouse_pos[0],
            "y": mouse_pos[1],
            "z": 0,  # Add height dimension
            "target_x": cat_pos[0],
            "target_y": cat_pos[1],
            "start_x": mouse_pos[0],
            "start_y": mouse_pos[1],
            "speed": 8,
            "vx": dx / flight_time,  # x-direction velocity
            "vy": dy / flight_time,  # y-direction velocity
            "vz": 3.0,  # Initial vertical velocity (upward)
            "gravity": 0.15,  # Gravity acceleration
            "rotation": 0,  # Rotation angle
            "rotation_speed": random.uniform(5, 15) * random.choice([-1, 1]),  # Rotation speed
            "bounce_count": 0,  # Bounce count
            "radius": radius,
            "color": GREEN if self.selected_item == "food" else YELLOW,
            "thrown": True,
            "game_ref": game_ref,
            "expected_need": expected_need,
            "image": scaled_img,
            "state": "flying",  # State: flying or landed
            "lifetime": 600,  # Lifetime (frames), disappears after ~10 seconds
        }
        self.thrown_items.append(item)
        
    def update_items(self):
        # Update thrown item positions
        for item in self.thrown_items[:]:
            if item["state"] == "landed":
                # Landed items decrease lifetime, add fade-out effect
                item["lifetime"] -= 1
                if item["lifetime"] <= 0:
                    self.thrown_items.remove(item)
                continue
            
            # Flying items - use parabolic motion
            # Update rotation angle
            item["rotation"] += item["rotation_speed"]
            
            # Update position (parabola)
            item["x"] += item["vx"]
            item["y"] += item["vy"]
            item["z"] += item["vz"]
            item["vz"] -= item["gravity"]  # Gravity effect
            
            # Check if landed (z <= 0)
            if item["z"] <= 0:
                item["z"] = 0
                item["bounce_count"] += 1
                
                # Bounce effect
                if item["bounce_count"] <= 2 and abs(item["vz"]) > 0.5:
                    # Bounce back, lose energy each time
                    item["vz"] = -item["vz"] * 0.5
                    item["vx"] *= 0.7  # Horizontal velocity decay
                    item["vy"] *= 0.7
                    item["rotation_speed"] *= 0.7
                else:
                    # Stop bouncing, mark as landed
                    item["state"] = "landed"
                    item["vx"] = 0
                    item["vy"] = 0
                    item["vz"] = 0
                    item["rotation_speed"] = 0
                    
                    # Check if reached target position (near cat)
                    dx = item["x"] - item["target_x"]
                    dy = item["y"] - item["target_y"]
                    distance = math.sqrt(dx*dx + dy*dy)
                    if distance < 30:  # Landed near target
                        return item
            
            # Check obstacle collision
            if 'game_ref' in item and item['game_ref'] is not None:
                game = item['game_ref']
                for rect in game.obstacles:
                    if rect.collidepoint(int(item["x"]), int(item["y"])) and item["z"] < 20:
                        # Hit obstacle, land immediately
                        item["state"] = "landed"
                        item["z"] = 0
                        item["vx"] = 0
                        item["vy"] = 0
                        item["vz"] = 0
                        # Mark field in return value to notify outer layer to show message
                        item_copy = dict(item)
                        item_copy['_blocked'] = True
                        return item_copy
        return None
        
    def draw_items(self):
        # Draw thrown items (with shadow, height and rotation effects)
        for item in self.thrown_items:
            x = int(item["x"])
            y = int(item["y"])
            z = item.get("z", 0)
            
            # Draw shadow (below item)
            if z > 0:
                shadow_y = y  # Shadow always on ground
                shadow_size = max(3, int(item["radius"] * (1 - z / 100)))  # Higher = smaller shadow
                shadow_alpha = int(100 * (1 - z / 150))  # Higher = lighter shadow
                if shadow_alpha > 0:
                    shadow_surf = pygame.Surface((shadow_size * 2, shadow_size), pygame.SRCALPHA)
                    pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), 
                                      (0, 0, shadow_size * 2, shadow_size))
                    screen.blit(shadow_surf, (x - shadow_size, shadow_y - shadow_size // 2))
            
            # Calculate item display position (considering height)
            display_y = int(y - z)
            
            # Draw item
            img = item.get("image")
            rotation = item.get("rotation", 0)
            
            if img is not None:
                # Rotate image
                if rotation != 0 and item["state"] == "flying":
                    rotated_img = pygame.transform.rotate(img, rotation)
                    rect = rotated_img.get_rect(center=(x, display_y))
                    screen.blit(rotated_img, rect)
                else:
                    blit_centered(screen, img, x, display_y)
            else:
                # Draw circle (if no image)
                pygame.draw.circle(screen, item["color"], (x, display_y), item["radius"])
            
    def switch_item(self):
        # Switch item
        self.selected_item = "toy" if self.selected_item == "food" else "food"

class Game:
    def __init__(self):
        # Entities
        self.cat = Cat()
        self.player = Player()
        # State
        self.running = True
        self.started = False   # Has game started (start screen)
        self.paused = False    # Is paused
        # Fonts: support custom TTF in ./assets/ (separate for body and title)
        try:
            # Parse respective font paths
            body_font_path = _resolve_font_path(FONT_BODY_FILE if FONT_BODY_FILE else None)
            title_font_path = _resolve_font_path(FONT_TITLE_FILE if FONT_TITLE_FILE else None)
            # If only one TTF provided, auto-reuse for the other
            body_exists = bool(FONT_BODY_FILE) and os.path.exists(os.path.join(ASSETS_DIR, FONT_BODY_FILE))
            title_exists = bool(FONT_TITLE_FILE) and os.path.exists(os.path.join(ASSETS_DIR, FONT_TITLE_FILE))
            if not title_exists:
                title_font_path = body_font_path
            if not body_exists:
                body_font_path = title_font_path
            # Create with different sizes: body vs title
            self.font = pygame.font.Font(body_font_path, max(1, int(FONT_BODY_SIZE)))
            self.large_font = pygame.font.Font(title_font_path, max(1, int(FONT_TITLE_SIZE)))
        except Exception:
            # Fallback: still use system font
            self.font = pygame.font.Font(font_path, 18)
            self.large_font = pygame.font.Font(font_path, 32)
        # Define obstacles (rectangles), below toolbar, distributed on large map
        self.obstacles = [
            # Top-left area
            pygame.Rect(150, 140, 120, 80),
            pygame.Rect(380, 260, 160, 90),
            pygame.Rect(620, 120, 100, 140),
            pygame.Rect(0, HEIGHT - 120, 140, 120),
            # Central area
            pygame.Rect(WIDTH + 200, 200, 140, 100),
            pygame.Rect(WIDTH + 500, 400, 120, 90),
            # Right area
            pygame.Rect(WIDTH * 2 + 100, 150, 150, 110),
            pygame.Rect(WIDTH * 2 + 400, 350, 130, 95),
            # Lower half
            pygame.Rect(200, HEIGHT + 200, 140, 85),
            pygame.Rect(WIDTH + 300, HEIGHT + 150, 160, 100),
        ]
        self.obstacle_color = (120, 120, 120)
        # Load PNG assets (fallback to default graphics if not found)
        self._load_assets()
        # Hide-and-seek state
        self.hide_target = None  # (x, y)
        self.hide_frames = 0     # Remaining hide frames (1-2 seconds)
        self.hide_waiting = False
        self.hide_cooldown = 0   # Hide cooldown timer
        # Idle (unobstructed) logic
        self.idle_cooldown = int(IDLE_INTERVAL_FRAMES)  # Enter first idle after initial interval
        self.idle_frames = 0
        # Dialog text (avoid frequent jitter, refresh randomly every 3-5 seconds)
        initial_need = self.cat.get_current_need()
        self.need_text = "I want food!" if initial_need == "food" else "I want a toy!"
        self._need_frames_left = random.randint(BUBBLE_REFRESH_MIN_FRAMES, BUBBLE_REFRESH_MAX_FRAMES)
        # Bubble position & direction (smooth following, sticky orientation)
        self._bubble_pos = None  # type: ignore
        self.bubble_side = 'top'
        # Game flow state
        self.time_left = GAME_DURATION_FRAMES
        self.loss_grace = LOSS_GRACE_FRAMES
        self.game_over = False
        self.game_result = None  # 'win' | 'lose' | 'summary'
        self.end_message = ""
        # Target for minimum "complete hide" count
        self.min_hide_goal = 3
        self.hide_completed = 0           # Completed hide count
        self.hide_session_had_wait = False  # Has this hide session entered waiting state (reached interior)
        self.force_hide_cooldown = 0      # Forced trigger cooldown, avoid consecutive forcing
        # Season: 0=normal, 1=winter; season_mix is blend coefficient
        self.season_mix = 0.0
        self._season_direction = 1  # 1 -> winter, -1 -> normal
        self._season_hold = SEASON_HOLD_FRAMES
        
        # Map switching system
        self.map_transition_timer = SCENE_SWITCH_INTERVAL  # Frames remaining until next auto-leave (20 seconds)
        self.cat_leaving = False          # Is cat leaving screen
        self.cat_leave_direction = None   # Cat leave direction: 'up', 'down', 'left', 'right'
        self.waiting_for_player = False   # Cat has left, waiting for player keypress to switch map
        
        # Direction arrow UI animation
        self.arrow_pulse = 0  # Pulse animation counter
        self.arrow_pulse_direction = 1  # Pulse direction
        
        # Crosshair/targeting effect (pixel style)
        self.target_blink = 0  # Blink counter

    def ensure_open_spot(self):
        """Move cat from obstacle interior to unobstructed position, and ensure not entering toolbar area."""
        # First constrain to screen visible area (not toolbar)
        self.cat.x = clamp(self.cat.x, self.cat.size, WIDTH - self.cat.size)
        self.cat.y = clamp(self.cat.y, 60 + self.cat.size, HEIGHT - self.cat.size)
        # If overlaps obstacle, use collision pushout several times
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

        # load scene configuration
        self.scenes = []
        self.current_scene_index = 0
        self.load_scenes_config()
        
        # If scene config loaded successfully, use scene system
        if self.scenes:
            self.use_scene_system = True
            self.load_scene(0)  # Load first scene
        else:
            # Otherwise use old background system
            self.use_scene_system = False
            self.background_list = []
            self.current_background_index = 0
            
            # Try loading multiple background images
            for i in range(1, 11):
                bg_img = load_image(f"background_{i}.png")
                if bg_img is not None:
                    try:
                        scaled_bg = pygame.transform.smoothscale(bg_img, (WIDTH, HEIGHT))
                        self.background_list.append(scaled_bg)
                    except Exception:
                        pass
            
            # If no numbered background found, load default background
            if not self.background_list:
                bg_norm = load_image("background.png")
                if bg_norm is not None:
                    try:
                        self.background_list.append(pygame.transform.smoothscale(bg_norm, (WIDTH, HEIGHT)))
                    except Exception:
                        pass
            
            # Compatible with old season system
            self.background_normal = self.background_list[0] if self.background_list else None
            self.background_winter = None
            bg_win = load_image("background_winter.png") or load_image("background_snow.png")
            if bg_win is not None:
                try:
                    self.background_winter = pygame.transform.smoothscale(bg_win, (WIDTH, HEIGHT))
                except Exception:
                    pass

    def load_scenes_config(self):
        """Load scene configuration file"""
        try:
            config_path = os.path.join("assets", "scenes.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scenes = data.get("scenes", [])
                    log(f"Successfully loaded {len(self.scenes)} scene configurations")
            else:
                log("scenes.json config file not found, using default background system")
        except Exception as e:
            log(f"Failed to load scene configuration: {e}")
            self.scenes = []
    
    def load_scene(self, scene_index):
        """Load specified scene's background and obstacles"""
        if not self.scenes or scene_index >= len(self.scenes):
            return
        
        scene = self.scenes[scene_index]
        log(f"Loading scene: {scene.get('name', f'Scene {scene_index}')}")
        
        # Load background
        bg_file = scene.get("background")
        if bg_file:
            bg_img = load_image(bg_file)
            if bg_img is not None:
                try:
                    self.background_normal = pygame.transform.smoothscale(bg_img, (WIDTH, HEIGHT))
                except Exception as e:
                    log(f"Failed to scale background: {e}")
        
        # Load obstacles
        obstacles_config = scene.get("obstacles", [])
        self.obstacles = []
        self.obstacle_images = []  # Store image for each obstacle
        
        for obs in obstacles_config:
            x = obs.get("x", 0)
            y = obs.get("y", 60)
            img_file = obs.get("image")
            
            # Load obstacle image and use original dimensions
            if img_file:
                img = load_image(img_file)
                if img is not None:
                    # Use image original dimensions
                    width = img.get_width()
                    height = img.get_height()
                    
                    # Special handling: obstacle_snow_4.png scale down 2x and move up 50px
                    if img_file == "obstacle_snow_4.png":
                        width = width // 2
                        height = height // 2
                        y = y - 50  # Move up
                        img = pygame.transform.smoothscale(img, (width, height))
                    
                    # Create obstacle rect
                    rect = pygame.Rect(x, y, width, height)
                    self.obstacles.append(rect)
                    self.obstacle_images.append(img)
                else:
                    # If image load fails, use config dimensions as fallback
                    width = obs.get("width", 100)
                    height = obs.get("height", 100)
                    rect = pygame.Rect(x, y, width, height)
                    self.obstacles.append(rect)
                    self.obstacle_images.append(None)
            else:
                # If no image specified, use config dimensions
                width = obs.get("width", 100)
                height = obs.get("height", 100)
                rect = pygame.Rect(x, y, width, height)
                self.obstacles.append(rect)
                self.obstacle_images.append(None)

    def compute_hide_spot(self, mouse_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Pick nearest obstacle to cat, generate target point on opposite side from mouse [inside obstacle], ensure occlusion."""
        if not self.obstacles:
            return (self.cat.x, max(60 + self.cat.size, self.cat.y))
        cx, cy = self.cat.x, self.cat.y
        # Find nearest obstacle
        nearest = min(self.obstacles, key=lambda r: (r.centerx - cx) ** 2 + (r.centery - cy) ** 2)
        mx, my = mouse_pos
        dx = nearest.centerx - mx
        dy = nearest.centery - my
        # On the far side of the obstacle relative to the mouse, choose a slightly inset point so the center is inside the rect and gets occluded
        inset_x = max(HIDE_INSET_MIN, min(int(nearest.width * HIDE_INSET_FRACTION), self.cat.size))
        inset_y = max(HIDE_INSET_MIN, min(int(nearest.height * HIDE_INSET_FRACTION), self.cat.size))
        if abs(dx) >= abs(dy):
            # Left/right side hide (interior), allow peeking from left/right, but not from bottom
            side_sign = 1 if dx >= 0 else -1  # Mouse on left => choose right side
            tx = nearest.centerx + side_sign * (nearest.width / 2 - inset_x)
            # y near current value, but force not exceeding obstacle bottom minus cat radius, avoid bottom peek
            ty = clamp(cy, nearest.top + inset_y, nearest.bottom - inset_y)
            safe_bottom_y = nearest.bottom - self.cat.size - 1
            if safe_bottom_y >= nearest.top + inset_y:
                ty = min(ty, safe_bottom_y)
            else:
                # Extreme case: obstacle too short, near top
                ty = nearest.top + inset_y
        else:
            # Vertical: force choose top interior (allow top/corner peek, forbid bottom peek)
            ty = nearest.top + inset_y
            tx = clamp(cx, nearest.left + inset_x, nearest.right - inset_x)
        # Final fallback constraint within screen
        tx = clamp(tx, 0 + self.cat.size, WIDTH - self.cat.size)
        ty = clamp(ty, 60 + self.cat.size, HEIGHT - self.cat.size)
        return (int(tx), int(ty))
        
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                # Start screen: press Enter/Space to start
                if not self.started:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.started = True
                        return
                # End screen: R restart / Esc quit
                if self.game_over:
                    if event.key == pygame.K_r:
                        # Restart current round
                        self.__init__()
                        return
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        return
                # In progress: Z pause/resume
                if event.key == pygame.K_z and self.started and not self.game_over:
                    self.paused = not self.paused
                    return
                # Manual season switch (disabled)
                # if event.key == pygame.K_t and self.started and not self.paused and not self.game_over:
                #     self._season_direction = -1 if self.season_mix > 0.5 else 1
                #     self._season_hold = 0
                #     return
                # Allow item switch when not paused
                if event.key == pygame.K_SPACE and self.started and not self.paused and not self.game_over:
                    self.player.switch_item()
                # WASD switch map (only active when waiting for player keypress)
                if self.started and not self.paused and not self.game_over and self.waiting_for_player:
                    if event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]:
                        self.manual_map_switch()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    # Start screen: any left click to start
                    if not self.started:
                        self.started = True
                        return
                    # No throwing during pause or end screen
                    if self.paused or self.game_over:
                        return
                    # In progress: check if clicked outside toolbar (game area)
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
        """Map switching system: cat auto-leaves screen every 20s, or player presses WASD to switch"""
        # Only update during gameplay
        if not self.started or self.paused or self.game_over:
            return
        
        # If waiting for player keypress, pause all updates
        if self.waiting_for_player:
            return
        
        # If cat is leaving screen
        if self.cat_leaving:
            self._move_cat_out()
            return
        
        # Normal state: countdown
        if self.map_transition_timer > 0:
            self.map_transition_timer -= 1
        else:
            # Time up, trigger auto-leave
            self._trigger_cat_leave()
    
    def _trigger_cat_leave(self, direction=None):
        """Trigger cat leaving screen"""
        if direction is None:
            # Random direction choice
            direction = random.choice(['up', 'down', 'left', 'right'])
        
        self.cat_leaving = True
        self.cat_leave_direction = direction
        
        # Set cat movement direction
        speed = self.cat.speed * 1.5  # Accelerate leaving
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
        
        # Clear hiding state
        self.hide_target = None
        self.hide_frames = 0
        self.hide_waiting = False
        self.idle_frames = 0
    
    def _move_cat_out(self):
        """Keep cat moving until completely off screen"""
        # Move cat
        self.cat.x += self.cat.dx
        self.cat.y += self.cat.dy
        
        # Check if completely left screen (including cat size)
        margin = self.cat.size + 10
        left_screen = (self.cat_leave_direction == 'left' and self.cat.x < -margin) or \
                      (self.cat_leave_direction == 'right' and self.cat.x > WIDTH + margin) or \
                      (self.cat_leave_direction == 'up' and self.cat.y < -margin) or \
                      (self.cat_leave_direction == 'down' and self.cat.y > HEIGHT + margin)
        
        if left_screen:
            # Cat has completely left, enter waiting for player keypress state
            self.cat_leaving = False
            self.waiting_for_player = True
    
    def _switch_map_instantly(self):
        """Instantly switch map and let cat enter from opposite side"""
        # Clear all thrown items (when switching scenes)
        self.player.thrown_items.clear()
        
        # Use scene system or background list
        if self.use_scene_system and self.scenes:
            # Switch to next scene
            self.current_scene_index = (self.current_scene_index + 1) % len(self.scenes)
            self.load_scene(self.current_scene_index)
        elif self.background_list:
            # Use old background system
            self.current_background_index = (self.current_background_index + 1) % len(self.background_list)
            self.background_normal = self.background_list[self.current_background_index]
            
            # Regenerate obstacles (old system)
            for i, rect in enumerate(self.obstacles):
                new_x = random.randint(0, WIDTH - rect.width)
                new_y = random.randint(60 + rect.height // 2, HEIGHT - rect.height // 2)
                self.obstacles[i] = pygame.Rect(new_x, new_y, rect.width, rect.height)
        
        # Enter from opposite edge
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
        
        # Reset state
        log(f"New obstacle positions: {[(r.x, r.y) for r in self.obstacles[:3]]}")
        log(f"Cat new position: ({self.cat.x}, {self.cat.y}), direction: ({self.cat.dx}, {self.cat.dy})")
        log(f"=== Map switch completed ===")
        self.cat_leaving = False
        self.waiting_for_player = False
        self.cat_leave_direction = None
        self.map_transition_timer = SCENE_SWITCH_INTERVAL  # Reset 20s timer
        
        # Don't clear thrown items, let game continue
        # self.player.thrown_items.clear()  # Commented out, keep game state
    
    def manual_map_switch(self, direction=None):
        """Player manually switches map (WASD) - only called in waiting state"""
        # Execute map switch
        if self.waiting_for_player:
            self._switch_map_instantly()
    
    def check_collision(self, item):
        # Check if item hit cat
        dx = item["x"] - self.cat.x
        dy = item["y"] - self.cat.y
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < self.cat.size:
            # Hit cat - always use cat's current needs to judge
            cat_need = self.cat.get_current_need()
            if item["type"] == cat_need:
                # Only add 1 point when throwing correct item cat needs
                self.player.score += 1
                # Can choose not to change money/affinity; here keep affinity increase, need relief
                self.cat.affinity = min(100, self.cat.affinity + 2)
                # Reset consecutive wrong count
                self.player.consecutive_wrong = 0

                if item["type"] == "food":
                    self.cat.hunger = max(0, self.cat.hunger - 15)
                else:
                    self.cat.playfulness = max(0, self.cat.playfulness - 15)
                
                # Hit correct, remove from list
                if item in self.player.thrown_items:
                    self.player.thrown_items.remove(item)
                
                return True, "Correct! +1"
            else:
                # Threw wrong item: no points, item stays on ground
                self.player.consecutive_wrong += 1
                if self.player.consecutive_wrong > 3:
                    self.cat.affinity = max(0, self.cat.affinity - 2)
                # Don't remove item, let it stay in landed state
                return True, "Not this one!"
        return False, ""

    def draw_obstacles(self):
        # If using scene system, draw obstacle images directly
        if self.use_scene_system and hasattr(self, 'obstacle_images'):
            for i, rect in enumerate(self.obstacles):
                if i < len(self.obstacle_images) and self.obstacle_images[i] is not None:
                    screen.blit(self.obstacle_images[i], rect.topleft)
                else:
                    # Draw rect when no image
                    pygame.draw.rect(screen, self.obstacle_color, rect)
            return
        
        # Old system: draw obstacles with season cross-fade
        mix = clamp(self.season_mix, 0.0, 1.0)
        for i, rect in enumerate(self.obstacles):
            entry = None
            if hasattr(self, "obstacle_surfs") and i < len(self.obstacle_surfs):
                entry = self.obstacle_surfs[i]
            # Compatible with old structure: tuple or surface
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
        # Draw rounded bubble with triangle tail near cat, showing current needs
        text = self.need_text
        if not text:
            return
        pad = 8
        surf = self.font.render(text, True, BLACK)
        bw, bh = surf.get_width() + pad * 2, surf.get_height() + pad * 2
    # Compute desired position (with sticky side and smooth animation); prefer top, else fall back to right/left/bottom if invalid
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

        # Avoid bubble covering cat: prefer bubble rect not intersecting cat
        def overlaps_cat(rect: pygame.Rect) -> bool:
            cx, cy, r = int(self.cat.x), int(self.cat.y), int(self.cat.size)
            cat_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            # Slightly expand cat hitbox, add safety margin
            cat_rect.inflate_ip(8, 8)
            return rect.colliderect(cat_rect)

        # Fallback directions: include current direction to enhance stickiness
        candidates = ['top', 'right', 'left', 'bottom']
        if self.bubble_side in candidates:
            # Ensure current direction first in list, enhance stability
            candidates.remove(self.bubble_side)
            candidates.insert(0, self.bubble_side)

    # Choose by composite score: validity + not occluded + closest to mouse + sticky preference
        mx, my = pygame.mouse.get_pos()
    # Enable 'near player side' bias only when the mouse is close to the cat
        mc_dist = math.hypot(self.cat.x - mx, self.cat.y - my)
        apply_mouse_bias = mc_dist <= BUBBLE_MOUSE_BIAS_DISTANCE
        best = None  # (score, side, rect)
        for s in candidates:
            r = calc_rect(s)
            if not valid(r):
                continue
            # Basic distance score: closer to mouse = smaller; only consider when close
            d = math.hypot((r.centerx - mx), (r.centery - my)) if apply_mouse_bias else 0.0
            # No occlusion priority: add large penalty if occluding
            overlap_penalty = 10000 if overlaps_cat(r) else 0
            # Sticky preference: current direction gets score reduction, avoid frequent switching
            sticky_bonus = -BUBBLE_STICKY_BIAS_PX if s == self.bubble_side else 0
            score = d + overlap_penalty + sticky_bonus
            if best is None or score < best[0]:
                best = (score, s, r)
        if best is None:
            # Fallback: choose any visible area
            chosen_side, chosen_rect = 'top', calc_rect('top')
        else:
            _, chosen_side, chosen_rect = best

        # Smooth bubble position movement, reduce jitter
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
        # Calculate triangle tail, avoid excessive deformation: fixed length/width, draw tail below bubble to avoid covering text
        tail_len = BUBBLE_TAIL_LEN
        tail_w = BUBBLE_TAIL_W
        cx, cy = int(self.cat.x), int(self.cat.y)
        # Choose bubble edge closest to cat as tail exit
        dx = cx - bubble_rect.centerx
        dy = cy - bubble_rect.centery
        if abs(dx) > abs(dy):
            # Left/right edge
            side = 'right' if dx > 0 else 'left'
        else:
            # Top/bottom edge
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

        # Draw tail (triangle) first, then rounded rect, so tail and text don't overlap
        pygame.draw.polygon(screen, WHITE, [base_left, base_right, tip])
        pygame.draw.lines(screen, BLACK, False, [base_left, tip, base_right], 2)

        # Draw rounded rect (above tail)
        pygame.draw.rect(screen, WHITE, bubble_rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, bubble_rect, width=2, border_radius=8)

        # Draw text (last)
        screen.blit(surf, (bx + pad, by + pad))
    
    def draw_direction_arrows(self):
        """Draw pixel-style direction arrow UI hints - only show direction cat left"""
        if not self.waiting_for_player or not self.cat_leave_direction:
            return
        
        # Update pulse animation
        self.arrow_pulse += self.arrow_pulse_direction * 2
        if self.arrow_pulse >= 60:
            self.arrow_pulse_direction = -1
        elif self.arrow_pulse <= 0:
            self.arrow_pulse_direction = 1
        
        # Calculate alpha and offset (breathing effect)
        alpha = int(120 + 100 * (self.arrow_pulse / 60))
        offset = int(10 * (self.arrow_pulse / 60))
        
        arrow_color = (255, 255, 100)  # Yellow
        
        # Show only one arrow pointing in direction cat left
        arrow_config = {
            'up': (WIDTH // 2, 80 - offset, 'up'),
            'down': (WIDTH // 2, HEIGHT - 40 + offset, 'down'),
            'left': (40 - offset, HEIGHT // 2, 'left'),
            'right': (WIDTH - 40 + offset, HEIGHT // 2, 'right')
        }
        
        if self.cat_leave_direction not in arrow_config:
            return
        
        x, y, direction = arrow_config[self.cat_leave_direction]
        
        # Pixel art arrow: composed of blocks
        # Arrow design:
        #     □         (Tip)
        #    □□□
        #   □□□□□
        #    □□□
        #    □□□
        pixel_size = 4
        
        # Define arrow shape (relative coords, pointing up)
        arrow_pattern = [
            # Tip
            (0, -12),
            # Second row
            (-4, -8), (0, -8), (4, -8),
            # Third row (widest)
            (-8, -4), (-4, -4), (0, -4), (4, -4), (8, -4),
            # Arrow shaft
            (-4, 0), (0, 0), (4, 0),
            (-4, 4), (0, 4), (4, 4),
            (-4, 8), (0, 8), (4, 8),
        ]
        
        # Rotate pixels based on direction
        if direction == 'down':
            arrow_pattern = [(px, -py) for px, py in arrow_pattern]
        elif direction == 'left':
            arrow_pattern = [(py, px) for px, py in arrow_pattern]
        elif direction == 'right':
            arrow_pattern = [(-py, px) for px, py in arrow_pattern]
        
        # Create surface with alpha
        arrow_surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        
        # Draw each pixel block
        for px, py in arrow_pattern:
            rect_x = 40 + px - pixel_size // 2
            rect_y = 40 + py - pixel_size // 2
            pygame.draw.rect(arrow_surf, (*arrow_color, alpha), 
                           (rect_x, rect_y, pixel_size, pixel_size))
        
        # Draw to screen
        rect = arrow_surf.get_rect(center=(x, y))
        screen.blit(arrow_surf, rect)
        
    def draw_targeting(self):
        """Draw pixel-style targeting effect"""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        # Calculate cat collision rect
        cat_left = self.cat.x - self.cat.size
        cat_top = self.cat.y - self.cat.size
        cat_width = self.cat.size * 2
        cat_height = self.cat.size * 2
        
        # Detect if mouse hovering over cat
        margin = 5
        is_hovering = (cat_left + margin <= mouse_x <= cat_left + cat_width - margin and
                      cat_top + margin <= mouse_y <= cat_top + cat_height - margin)
        
        # Pixel art crosshair - composed of small blocks
        pixel_size = 3  # Size of each pixel block
        if is_hovering:
            crosshair_color = (255, 80, 80)  # Red
            gap = 8  # Center gap
            arm_length = 12  # Crosshair arm length
        else:
            crosshair_color = (255, 255, 255)  # White
            gap = 6
            arm_length = 10
        
        # Draw crosshair four directions (with pixel blocks)
        # Up
        for i in range(gap, gap + arm_length, pixel_size):
            pygame.draw.rect(screen, crosshair_color, 
                           (mouse_x - pixel_size//2, mouse_y - i, pixel_size, pixel_size))
        # Down
        for i in range(gap, gap + arm_length, pixel_size):
            pygame.draw.rect(screen, crosshair_color, 
                           (mouse_x - pixel_size//2, mouse_y + i, pixel_size, pixel_size))
        # Left
        for i in range(gap, gap + arm_length, pixel_size):
            pygame.draw.rect(screen, crosshair_color, 
                           (mouse_x - i, mouse_y - pixel_size//2, pixel_size, pixel_size))
        # Right
        for i in range(gap, gap + arm_length, pixel_size):
            pygame.draw.rect(screen, crosshair_color, 
                           (mouse_x + i, mouse_y - pixel_size//2, pixel_size, pixel_size))
        
        # Center point
        pygame.draw.rect(screen, crosshair_color, 
                        (mouse_x - pixel_size//2, mouse_y - pixel_size//2, pixel_size, pixel_size))
        
        # If hovering over cat, draw pixel art blinking blocks
        if is_hovering:
            self.target_blink += 1
            if self.target_blink >= 30:
                self.target_blink = 0
            
            # Blink effect (switch every 15 frames)
            if self.target_blink < 15:
                # Draw pixel blocks at cat's four corners
                corner_size = 6
                offset = int(self.cat.size) + 5
                corners = [
                    (int(self.cat.x) - offset, int(self.cat.y) - offset),  # LeftUp
                    (int(self.cat.x) + offset - corner_size, int(self.cat.y) - offset),  # RightUp
                    (int(self.cat.x) - offset, int(self.cat.y) + offset - corner_size),  # LeftDown
                    (int(self.cat.x) + offset - corner_size, int(self.cat.y) + offset - corner_size),  # RightDown
                ]
                
                for cx, cy in corners:
                    pygame.draw.rect(screen, (255, 255, 0), (cx, cy, corner_size, corner_size))
    
    def draw_ui(self):
        # Draw toolbar background
        pygame.draw.rect(screen, (200, 200, 200), (0, 0, WIDTH, 60))

        # Two-row layout, avoid overlap
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

        # Needs hint (red text) removed per user request, no longer displayed
        
    def run(self):
        log("Game loop entering...")
        ticks = 0
        while self.running:
            # Update season transition (if needed)
            self._update_season()
            # Update map switching
            self._update_map_transition()
            
            # Clear screen
            screen.fill(WHITE)
            
            # Background: support season transition (normal -> winter)
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
            
            # Handle events
            self.handle_events()
            
            # Start screen: show start prompt, don't update game state before start
            if not self.started:
                # Semi-transparent overlay and title
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                screen.blit(overlay, (0, 0))
                title = "FEED YOUR CAT"
                sub = "Press Enter or Click to Start"
                # Control instructions one operation per line, centered row by row
                ctrl_lines = [
                    "Left Click = Throw",
                    "Space = Switch Item",
                    "Z = Pause/Resume"
                ]
                t_surf = self.large_font.render(title, True, WHITE)
                s_surf = self.font.render(sub, True, WHITE)
                ctrl_surfs = [self.font.render(line, True, WHITE) for line in ctrl_lines]
                # Vertically centered layout within safe area, avoid edge occlusion
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
                # Title
                screen.blit(t_surf, (cx - t_surf.get_width() // 2, y))
                y += t_surf.get_height() + spacing
                # Subtitle
                screen.blit(s_surf, (cx - s_surf.get_width() // 2, y))
                y += s_surf.get_height() + spacing
                # Control instructions (one operation per line)
                for cs in ctrl_surfs:
                    screen.blit(cs, (cx - cs.get_width() // 2, y))
                    y += cs.get_height() + spacing
                pygame.display.flip()
                clock.tick(FPS)
                continue
            # Game over state: only show result panel and UI, wait for R/ESC
            if self.game_over:
                # Background can still draw basic elements, for simplicity draw UI and end panel
                self.draw_ui()
                # Semi-transparent overlay
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 120))
                screen.blit(overlay, (0, 0))
                # Text
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
            # Paused state: show current screen + pause prompt, don't update state/timer
            if self.paused:
                # Draw current scene
                self.cat.draw()
                self.player.draw_items()
                self.draw_obstacles()
                self.draw_speech_bubble()
                self.draw_ui()
                # Overlay pause prompt
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
            
            # Update game state
            mouse_pos = pygame.mouse.get_pos()
            
            # If cat is leaving screen, skip normal game logic
            # Game continues running in waiting for player state (just don't show cat)
            if not self.cat_leaving and not self.waiting_for_player:
                # Normal game logic
                # Every 10s let cat idle in open area for 3-4s (if not currently hiding)
                if self.idle_frames <= 0:
                    if self.idle_cooldown > 0:
                        self.idle_cooldown -= 1
                    elif self.hide_frames <= 0 and not self.hide_waiting and mouse_pos[1] > 60:
                        # Enter idle: first ensure current position unobstructed, then time 3-4 seconds
                        self.ensure_open_spot()
                        self.idle_frames = random.randint(int(3 * FPS), int(4 * FPS))
                        # Reset interval
                        self.idle_cooldown = int(10 * FPS)

                # Trigger hide-and-seek behavior: prioritize when mouse is near; otherwise low random chance with cooldown; don't trigger while stationary
                if self.hide_frames <= 0 and self.idle_frames <= 0 and self.hide_cooldown <= 0 and mouse_pos[1] > 60:
                    # Mouse-cat distance
                    mdx = mouse_pos[0] - self.cat.x
                    mdy = mouse_pos[1] - self.cat.y
                    mdist = math.hypot(mdx, mdy)
                    if mdist <= HIDE_NEAR_DISTANCE or random.random() < HIDE_TRIGGER_RANDOM_CHANCE:
                        self.hide_target = self.compute_hide_spot(mouse_pos)
                        self.hide_frames = random.randint(HIDE_DURATION_MIN_FRAMES, HIDE_DURATION_MAX_FRAMES)

                if self.idle_frames > 0:
                    # During idle: don't move
                    self.idle_frames -= 1
                    # Ensure don't accidentally enter toolbar
                    self.cat.y = max(60 + self.cat.size, self.cat.y)
                elif self.hide_frames > 0 and self.hide_target is not None:
                    # Move toward hiding spot; on arrival, wait until timer ends to ensure 1–2 seconds of fully hidden state
                    hx, hy = self.hide_target
                    dx = hx - self.cat.x
                    dy = hy - self.cat.y
                    dist = math.hypot(dx, dy) or 1.0
                    step = self.cat.speed
                    if dist > step:
                        # Calculate new position
                        new_x = self.cat.x + (dx / dist) * step
                        new_y = self.cat.y + (dy / dist) * step
                        
                        # Constrain within screen bounds (can't exceed)
                        min_x = self.cat.size
                        max_x = WIDTH - self.cat.size
                        min_y = 60 + self.cat.size
                        max_y = HEIGHT - self.cat.size
                        
                        self.cat.x = max(min_x, min(max_x, new_x))
                        self.cat.y = max(min_y, min(max_y, new_y))
                        
                        # Update facing based on target direction, so mirroring is correct during hiding
                        if abs(dx) > 1e-3:
                            self.cat.facing_right = (dx >= 0)
                    else:
                        # Reached target, fix at target point and wait remaining time
                        self.cat.x, self.cat.y = hx, hy
                        self.hide_waiting = True
                        self.hide_session_had_wait = True
                    self.hide_frames -= 1
                    if self.hide_frames <= 0:
                        # End one hide session, if successfully reached interior, count toward completion
                        if self.hide_session_had_wait:
                            self.hide_completed += 1
                        self.hide_session_had_wait = False
                        self.hide_target = None
                        self.hide_waiting = False
                        self.hide_cooldown = HIDE_COOLDOWN_FRAMES
                else:
                    # Regular movement: slow down in open areas
                    self.cat.move(CAT_OPEN_SPEED_FACTOR)
                # Cat-obstacle collision handling (circle-rect): use normal reflection, reduce jitter
                # While hiding, allow the cat to enter obstacles (be occluded), so skip collision push-out
                if not (self.hide_frames > 0 or self.hide_waiting):
                    for rect in self.obstacles:
                        if circle_rect_overlap(self.cat.x, self.cat.y, self.cat.size, rect):
                            nx, ny, vx, vy = resolve_circle_rect_collision(self.cat.x, self.cat.y, self.cat.size, rect, self.cat.dx, self.cat.dy)
                            self.cat.x, self.cat.y = nx, ny
                            self.cat.dx, self.cat.dy = vx, vy
                            break
                self.cat.grow()
                hit_item = self.player.update_items()
            
                # Check collision
                message = ""
                if hit_item:
                    if isinstance(hit_item, dict) and hit_item.get('_blocked'):
                        message = "Blocked by obstacle!"
                    else:
                        hit, message = self.check_collision(hit_item)
            elif self.waiting_for_player:
                # Waiting for player keypress state: update thrown items but don't collide with cat
                hit_item = self.player.update_items()
                message = ""
            else:
                # Cat is leaving, don't process game logic
                message = ""
            
            # Draw game elements (don't draw cat when waiting for player)
            if not self.waiting_for_player:
                self.cat.draw()
            self.player.draw_items()
            # Obstacles drawn last, used to occlude cat and items
            self.draw_obstacles()
            # Draw the speech bubble above obstacles to keep it visible
            self.draw_speech_bubble()
            self.draw_ui()
            # Direction arrow hint (show when waiting for player)
            self.draw_direction_arrows()
            # Targeting effect (don't show during waiting for player state)
            if not self.waiting_for_player:
                self.draw_targeting()
            
            # Show messages
            if message:
                msg_surface = self.font.render(message, True, BLUE)
                screen.blit(msg_surface, (WIDTH // 2 - msg_surface.get_width() // 2, 70))
            
            # Refresh screen
            pygame.display.flip()
            clock.tick(FPS)
            # Print a heartbeat roughly once per second to confirm the loop is running
            ticks += 1
            if ticks % FPS == 0:
                log(f"Heartbeat: running, score={self.player.score}, affinity={self.cat.affinity}, stage={self.cat.growth_stage}, wrong_streak={self.player.consecutive_wrong}")
            # Cooldowns tick down
            if self.hide_cooldown > 0:
                self.hide_cooldown -= 1
            if self.force_hide_cooldown > 0:
                self.force_hide_cooldown -= 1
            # Periodically refresh speech text (random every 3–5 seconds)
            if hasattr(self, "_need_frames_left"):
                self._need_frames_left -= 1
                if self._need_frames_left <= 0:
                    need = self.cat.get_current_need()
                    self.need_text = "I want food!" if need == "food" else "I want a toy!"
                    self._need_frames_left = random.randint(BUBBLE_REFRESH_MIN_FRAMES, BUBBLE_REFRESH_MAX_FRAMES)
            # Timer and win/lose conditions
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

            # Guarantee: complete at least three fully hidden events
            # If not hiding/stationary/on cooldown and the count is insufficient, force one hide and ensure enough time to reach the target plus ≥1s wait
            if (not self.game_over and self.started and not self.paused 
                and self.hide_frames <= 0 and not self.hide_waiting 
                and self.idle_frames <= 0 and self.hide_cooldown <= 0 
                and self.force_hide_cooldown <= 0 and self.hide_completed < self.min_hide_goal):
                mx, my = pygame.mouse.get_pos()
                if my > 60:
                    target = self.compute_hide_spot((mx, my))
                    self.hide_target = target
                    # Compute distance to target; allocate travel frames plus at least 1.2 seconds of lingering
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

# Start the game
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