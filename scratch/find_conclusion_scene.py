import json

mg = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json', encoding='utf-8'))
for i, s in enumerate(mg.get('scenes', [])):
    s_str = json.dumps(s, ensure_ascii=False)
    if '更流暢的智慧眼鏡體驗' in s_str or '智慧眼鏡體驗' in s_str:
        print(f"Found in index {i}, scene_id {s.get('scene_id')}, sceneType {s.get('sceneType')}:")
        print(json.dumps(s, ensure_ascii=False, indent=2))
