import json

mg_data = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json', encoding='utf-8'))
scenes = mg_data.get("scenes", [])
print(f"Total MG scenes: {len(scenes)}")
for s in scenes[:5]:
    idx = s.get("scene_index")
    comp = s.get("component")
    props = s.get("props", {})
    print(f"Scene idx {idx}: comp={comp}, headline={props.get('headline')}, badge={props.get('badge')}")
    # print all text in props
    print("   Props text:", [v for k, v in props.items() if isinstance(v, str)])
