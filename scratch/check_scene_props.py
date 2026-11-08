import json

scenes = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/scenes.json', encoding='utf-8'))
for i in [1, 3]:
    s = scenes[i]
    print(f"--- Scene {i} ---")
    print("Narration:", s.get("narration"))
    print("Motion graphic:", json.dumps(s.get("motion_graphic"), ensure_ascii=False, indent=2))
