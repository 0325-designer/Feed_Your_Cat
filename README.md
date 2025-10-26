# Feed Your Cat - Pixel Art Cat Care Game

A pixel-art interactive cat care game built with Python and Pygame. Feed your cat with food and toys to meet their needs and increase affinity!

## 🎮 Game Features

- **Pixel Art Style**: Authentic pixel art graphics including pixel crosshair and directional arrows
- **Multi-Scene System**: Three different scenes (Grassland, Snow, Beach) with unique obstacle layouts
- **Physics Engine**: Thrown items feature realistic parabolic motion, rotation, shadows, and bounce effects
- **Smart Cat AI**: The cat moves randomly with hunger and playfulness values that need attention
- **Hide and Seek**: The cat hides behind obstacles, especially when the mouse gets close
- **Growth System**: Increase affinity to help your cat grow (3 stages), with increasing speed
- **Targeting System**: Pixel-art crosshair and flashing squares appear when hovering over the cat
- **Direction Hints**: Pixel-art arrows guide you to switch maps when the cat leaves the screen

## 📋 Requirements

- Python 3.13+ (or 3.7+)
- Pygame 2.6+

## 🚀 Installation

1. Ensure Python is installed
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Run the game:

   ```powershell
   python main.py
   ```

## 🎯 Controls

### Basic Controls
- **Left Mouse Button**: Throw the selected item toward the mouse position
- **1 Key**: Select Food
- **2 Key**: Select Toy
- **ESC Key**: Quit game

### Map Switching
When the cat leaves the screen, a yellow pixel arrow will appear:
- **W Key**: Switch to upper map
- **A Key**: Switch to left map
- **S Key**: Switch to lower map
- **D Key**: Switch to right map

## 🎲 Gameplay

### Objective
Feed the cat the correct items based on their needs to increase affinity and help them grow!

### Cat Needs
- **Hungry**: Needs food
- **Playful**: Needs toys

### Throwing Tips
1. **Aim**: Move mouse over the cat - crosshair turns red with yellow flashing squares at corners
2. **Predict**: The cat moves, so predict their position
3. **Physics**: Items fly in parabolic arcs, rotate, and bounce (max 2 times)
4. **Obstacles**: Items are blocked by obstacles, throw around them

### Game Mechanics
- **Correct Feed**: +1 score, +2 affinity
- **Wrong Feed**: -1 score, -2 affinity, consecutive wrongs make the cat angry
- **Growth Stages**:
  - Stage 1 (Gray): Affinity 0-29, slow speed
  - Stage 2 (Dark Gray): Affinity 30-59, medium speed
  - Stage 3 (Darker Gray): Affinity 60+, fast speed
- **Hide and Seek**: Cat randomly hides behind obstacles, more likely when mouse is close
- **Item Lifetime**: Failed throws remain on screen for ~10 seconds before disappearing

### Scene Features
1. **Grassland**: Obstacles at four corners
2. **Snow**: Obstacles on left and right sides
3. **Beach**: Obstacles concentrated in center-right area

## 📁 File Structure

```
d:\coding2\
├── main.py              # Main game code
├── README.md            # Game documentation
├── requirements.txt     # Dependencies
└── assets/              # Assets folder
    ├── scenes.json      # Scene configuration
    ├── food.png         # Food image (optional)
    ├── toy.png          # Toy image (optional)
    ├── background_1.png # Grassland background
    ├── background_2.png # Snow background
    ├── background_3.png # Beach background
    ├── obstacle_grass_1~4.png  # Grassland obstacles
    ├── obstacle_snow_1~4.png   # Snow obstacles
    └── obstacle_beach_1~4.png  # Beach obstacles
```

## 🎨 Custom Assets

### Item Assets
Place in `assets/` folder:
- `food.png` - Food image
- `toy.png` - Toy image

PNG format with transparent background recommended, 32x32 to 64x64 pixels.

If asset files are missing, the game uses built-in pixel art (fish and yarn ball).

### Adjust Size
Edit line 88 in `main.py`:
```python
ITEM_IMAGE_SCALE = {"food": 2.0, "toy": 1.0}
```
Higher values = larger display (current: food 2x, toy 1x).

## 🎯 UI Guide

### Top Toolbar
- **Selected**: Current item (Food/Toy)
- **Score**: Current score
- **Affinity**: Affinity level (0-100)
- **Stage**: Cat growth stage (1-3)
- **Wrong Streak**: Consecutive wrong feeds
- **Cat needs**: Current need (top-right, green box)

### Speech Bubble
Shows the cat's current mood and need text above their head.

### Pixel Art Effects
- **Crosshair**: White cross, turns red when hovering over cat
- **Target Hint**: Yellow flashing squares at cat's corners when hovering
- **Direction Arrow**: Yellow pixel arrow with breathing transparency effect

## 🐛 Known Behaviors

- After the cat leaves the screen, press WASD to switch maps to continue
- Consecutive wrong feeds decrease affinity, may cause growth regression
- Items may get stuck at obstacle edges when bouncing
- Scene switching clears all thrown items

## 📝 Changelog

### Latest Version
- ✅ Added pixel-art crosshair and targeting effects
- ✅ Added pixel-art directional arrow hints
- ✅ Enhanced item physics (parabolic motion, rotation, bounce)
- ✅ Implemented three-scene system with unique layouts
- ✅ Fixed collision detection to use real-time needs
- ✅ Added item lifetime and scene-switch cleanup
- ✅ Support for custom item assets

## 💡 Tips

1. Observe the cat's movement direction and predict throw position
2. Use gaps between obstacles to throw
3. Hovering over the cat shows clear targeting hints
4. Consecutive correct feeds quickly increase affinity
5. Avoid consecutive wrongs or the cat will get angry (affinity drops significantly)

Enjoy the game! 🐱