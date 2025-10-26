import re

# Read the file
with open(r'd:\coding2\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace specific lines
for i in range(len(lines)):
    if '在鼠标相对障碍的"远侧"选择一个离边缘略微内缩的位置，保证中心进入矩形内部从而被遮挡' in lines[i]:
        lines[i] = lines[i].replace('在鼠标相对障碍的"远侧"选择一个离边缘略微内缩的位置，保证中心进入矩形内部从而被遮挡',
                                     'On the "far side" of mouse relative to obstacle, select a position slightly inset from edge, ensuring center enters rect interior for occlusion')
        print(f"Replaced line {i+1}")
    
    if '计算期望位置（带"粘性"方向与平滑动画），优先 top，若不合法按 right/left/bottom 备选' in lines[i]:
        lines[i] = lines[i].replace('计算期望位置（带"粘性"方向与平滑动画），优先 top，若不合法按 right/left/bottom 备选',
                                     'Calculate desired position (with "sticky" direction and smooth animation), prefer top, fallback to right/left/bottom if invalid')
        print(f"Replaced line {i+1}")
    
    if '根据"合法性 + 不遮挡 + 距离鼠标最近 + 粘性偏好"综合评分选择' in lines[i]:
        lines[i] = lines[i].replace('根据"合法性 + 不遮挡 + 距离鼠标最近 + 粘性偏好"综合评分选择',
                                     'Select based on comprehensive scoring: validity + no occlusion + closest to mouse + sticky preference')
        print(f"Replaced line {i+1}")
    
    if '仅在鼠标靠近猫时才启用"贴近玩家一侧"的偏好' in lines[i]:
        lines[i] = lines[i].replace('仅在鼠标靠近猫时才启用"贴近玩家一侧"的偏好',
                                     'Only enable "near player side" preference when mouse is close to cat')
        print(f"Replaced line {i+1}")

# Write back
with open(r'd:\coding2\main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Translation complete!")
