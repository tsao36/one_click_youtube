import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('agents/scene_planner.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(295, 395):
    print(f"{i+1}: {lines[i].strip()}")
