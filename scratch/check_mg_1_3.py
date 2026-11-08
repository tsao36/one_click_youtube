import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

mg_data = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json', encoding='utf-8'))
scenes = mg_data.get("scenes", [])
print("Scene 1:", json.dumps(scenes[1], ensure_ascii=False, indent=2))
print("Scene 3:", json.dumps(scenes[3], ensure_ascii=False, indent=2))
