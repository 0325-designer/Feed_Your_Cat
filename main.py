import math
import random
import sys

import pygame


# ---------------------------
# Config (pixel look & feel)
# ---------------------------
# We render to a low-res surface and scale it up using nearest-neighbor
# to achieve crisp pixel art even with primitive rectangles.
VIRTUAL_W, VIRTUAL_H = 160, 144  # Game Boy-like resolution
SCALE = 4  # Window size = VIRTUAL_* * SCALE
WINDOW_W, WINDOW_H = VIRTUAL_W * SCALE, VIRTUAL_H * SCALE
FPS = 60

PLAYER_SPEED = 80  # pixels/sec on virtual surface
BULLET_SPEED = 200
ENEMY_SPEED_MIN = 20
ENEMY_SPEED_MAX = 45
ENEMY_SPAWN_EVERY = 0.6  # seconds
MAX_ENEMIES = 30

# Colors (RGB)
BLACK = (15, 12, 20)
WHITE = (255, 255, 255)
BG_DARK = (24, 20, 37)
PLAYER_GREEN = (80, 240, 140)
BULLET_YELLOW = (255, 232, 99)
ENEMY_RED = (235, 64, 52)
STAR_DIM = (90, 90, 120)


def clamp(v, lo, hi):
	return max(lo, min(hi, v))


class Player:
	def __init__(self):
		self.w, self.h = 10, 8
		self.x = VIRTUAL_W // 2 - self.w // 2
		self.y = VIRTUAL_H - self.h - 10
		self.cooldown = 0.0
		self.cooldown_time = 0.18

	def rect(self):
		return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

	def update(self, dt, keys):
		dx = dy = 0.0
		if keys[pygame.K_LEFT] or keys[pygame.K_a]:
			dx -= 1
		if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
			dx += 1
		if keys[pygame.K_UP] or keys[pygame.K_w]:
			dy -= 1
		if keys[pygame.K_DOWN] or keys[pygame.K_s]:
			dy += 1

		if dx and dy:
			inv = 1 / math.sqrt(2)
			dx *= inv
			dy *= inv

		self.x += dx * PLAYER_SPEED * dt
		self.y += dy * PLAYER_SPEED * dt
		self.x = clamp(self.x, 2, VIRTUAL_W - self.w - 2)
		self.y = clamp(self.y, 2, VIRTUAL_H - self.h - 2)

		if self.cooldown > 0:
			self.cooldown -= dt

	def can_shoot(self):
		return self.cooldown <= 0

	def shoot(self):
		self.cooldown = self.cooldown_time
		# bullet spawns from center top of player
		bx = self.x + self.w // 2 - 1
		by = self.y - 2
		return Bullet(bx, by)

	def draw(self, surf):
		# simple pixel ship: a trapezoid-ish rectangle with a nose
		r = self.rect()
		pygame.draw.rect(surf, PLAYER_GREEN, r)
		# nose
		pygame.draw.rect(surf, WHITE, (r.centerx - 1, r.y - 2, 2, 2))


class Bullet:
	def __init__(self, x, y):
		self.w, self.h = 2, 4
		self.x, self.y = x, y
		self.dead = False

	def rect(self):
		return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

	def update(self, dt):
		self.y -= BULLET_SPEED * dt
		if self.y < -self.h:
			self.dead = True

	def draw(self, surf):
		pygame.draw.rect(surf, BULLET_YELLOW, self.rect())


class Enemy:
	def __init__(self):
		self.w, self.h = 10, 8
		self.x = random.randint(2, VIRTUAL_W - self.w - 2)
		self.y = -self.h - 2
		self.speed = random.uniform(ENEMY_SPEED_MIN, ENEMY_SPEED_MAX)
		self.dead = False

	def rect(self):
		return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

	def update(self, dt):
		self.y += self.speed * dt
		if self.y > VIRTUAL_H + self.h:
			self.dead = True

	def draw(self, surf):
		pygame.draw.rect(surf, ENEMY_RED, self.rect())
		# small eye pixel for character
		r = self.rect()
		pygame.draw.rect(surf, WHITE, (r.x + 2, r.y + 2, 1, 1))


class Starfield:
	def __init__(self, count=40):
		self.stars = [
			[random.randint(0, VIRTUAL_W - 1), random.randint(0, VIRTUAL_H - 1), random.uniform(10, 30)]
			for _ in range(count)
		]

	def update(self, dt):
		for star in self.stars:
			star[1] += star[2] * dt
			if star[1] >= VIRTUAL_H:
				star[0] = random.randint(0, VIRTUAL_W - 1)
				star[1] = 0
				star[2] = random.uniform(10, 30)

	def draw(self, surf):
		for x, y, speed in self.stars:
			surf.set_at((int(x), int(y)), STAR_DIM)


def draw_text(surf, text, x, y, color=WHITE):
	# tiny 5x7 pixel font via pygame's default font scaled down is blurry,
	# so use pygame's font but keep it small; still fine for prototype.
	font = pygame.font.SysFont("Consolas", 8)
	img = font.render(text, True, color)
	surf.blit(img, (x, y))


def main():
	pygame.init()
	pygame.display.set_caption("Pixel Shooter")

	# Create window (scaled) and virtual surface
	window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
	virtual = pygame.Surface((VIRTUAL_W, VIRTUAL_H))

	clock = pygame.time.Clock()
	running = True
	game_over = False

	player = Player()
	bullets = []
	enemies = []
	starfield = Starfield()

	spawn_timer = 0.0
	score = 0

	while running:
		dt = clock.tick(FPS) / 1000.0

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					running = False
				if game_over and event.key == pygame.K_r:
					# reset game
					player = Player()
					bullets = []
					enemies = []
					score = 0
					game_over = False

		keys = pygame.key.get_pressed()

		if not game_over:
			# Update
			player.update(dt, keys)
			if keys[pygame.K_SPACE] and player.can_shoot():
				bullets.append(player.shoot())

			for b in bullets:
				b.update(dt)
			bullets = [b for b in bullets if not b.dead]

			spawn_timer += dt
			if spawn_timer >= ENEMY_SPAWN_EVERY:
				spawn_timer = 0
				if len(enemies) < MAX_ENEMIES:
					enemies.append(Enemy())

			for e in enemies:
				e.update(dt)
			enemies = [e for e in enemies if not e.dead]

			# Collisions
			pr = player.rect()
			for e in enemies:
				if pr.colliderect(e.rect()):
					game_over = True
					break

			if not game_over:
				for b in bullets:
					br = b.rect()
					for e in enemies:
						if br.colliderect(e.rect()):
							b.dead = True
							e.dead = True
							score += 1
							break

			starfield.update(dt)

		# Draw
		virtual.fill(BG_DARK)
		starfield.draw(virtual)

		for b in bullets:
			b.draw(virtual)
		for e in enemies:
			e.draw(virtual)
		player.draw(virtual)

		draw_text(virtual, f"Score: {score}", 4, 4)
		draw_text(virtual, "Move: WASD/Arrows  Shoot: Space", 4, VIRTUAL_H - 18)
		draw_text(virtual, "Quit: Esc  Restart: R", 4, VIRTUAL_H - 9)

		if game_over:
			draw_text(virtual, "GAME OVER", VIRTUAL_W // 2 - 32, VIRTUAL_H // 2 - 8, WHITE)
			draw_text(virtual, "Press R to restart", VIRTUAL_W // 2 - 48, VIRTUAL_H // 2 + 4, WHITE)

		# Scale up to window using nearest-neighbor
		pygame.transform.scale(virtual, (WINDOW_W, WINDOW_H), window)
		pygame.display.flip()

	pygame.quit()
	return 0


if __name__ == "__main__":
	sys.exit(main())

