# Pixel Shooter Game

A minimal pixel-style vertical shooter game built with Python and Pygame.

## Features

- Pixel art style with low-res rendering scaled up for crisp visuals
- Player ship movement (WASD or arrow keys)
- Shooting bullets (Spacebar)
- Enemy spawning and collision detection
- Score tracking
- Game over and restart (R key)
- New: Obstacles that occlude the cat and thrown items; the cat occasionally hides behind them

## Requirements

- Python 3.7+
- Pygame 2.6+

## Setup

1. Ensure Python is installed on your system.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

## Running the Game

Run the game using Python:

```powershell
python main.py
```

## Controls

- **Movement**: WASD or Arrow Keys
- **Shoot**: Spacebar
- **Restart**: R (when game over)
- **Quit**: Escape

## Game Mechanics

- Avoid enemy ships; collision ends the game.
- Shoot enemies to increase your score.
- Enemies spawn from the top and move downward at varying speeds.

Enjoy the game!

## How to play (quick)

- Goal: Throw the correct item (Food or Toy) to the cat when it needs it.
- Left Click (in game area): Throw the currently selected item to the cat.
- Space: Switch selected item between Food and Toy.
- H: Toggle in-game help overlay.
- Enter: Start the game from the start screen.
- Esc: Quit the game.

New mechanics:
- Obstacles: Gray rectangles in the play area; they visually block the cat and your throws.
- Hide-and-seek: The cat occasionally dashes to hide on the far side of an obstacle relative to your mouse cursor.

Top toolbar shows Selected / Score / Money / Affinity / Stage. Top-right shows the cat's current need.