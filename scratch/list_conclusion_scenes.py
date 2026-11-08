import json

mg_path = "projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json"
mg = json.load(open(mg_path, "r", encoding="utf-8"))

for i, s in enumerate(mg.get("scenes", [])):
    props = s.get("props", {})
    badge = props.get("badge", "")
    subtext = props.get("subtext", "")
    if "conclusion" in badge.lower() or "conclusion" in subtext.lower():
        print(f"Scene index {i} (scene_id {s.get('scene_id')}): badge='{badge}', subtext='{subtext}'")
