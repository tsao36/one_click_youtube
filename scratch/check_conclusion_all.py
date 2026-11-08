import json

mg_path = "projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json"
mg = json.load(open(mg_path, "r", encoding="utf-8"))

for idx in [34, 35, 36, 37, 38]:
    s = mg["scenes"][idx]
    print(f"Index {idx} (scene_id {s['scene_id']}):")
    print("  Text:", s["props"].get("text"))
    print("  Badge:", s["props"].get("badge"))
    print("  Subtext:", s["props"].get("subtext"))
