import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

mg_data = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json', encoding='utf-8'))
scenes = mg_data.get("scenes", [])
for i, s in enumerate(scenes):
    s_str = json.dumps(s, ensure_ascii=False)
    if "24" in s_str:
        print(f"Found '24' in scene index {i}:")
        for line in s_str.split(","):
            if "24" in line:
                print("  ", line.strip())
    if "7.5" in s_str:
        print(f"Found '7.5' in scene index {i}:")
        for line in s_str.split(","):
            if "7.5" in line:
                print("  ", line.strip())
