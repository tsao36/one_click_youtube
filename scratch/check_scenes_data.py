import json

scenes = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/scenes.json', encoding='utf-8'))
for s in scenes[:8]:
    nar = s.get("narration", "")
    print(f"Scene {s.get('id')} ({s.get('section')}): {nar}")
    # Also check visual text or motion graphic specs
    mg = s.get("motion_graphic")
    if mg:
        print(f"   MG Component: {mg.get('component')}, Headline: {mg.get('props', {}).get('headline')}")
