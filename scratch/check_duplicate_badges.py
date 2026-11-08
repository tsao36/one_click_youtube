import json

mg = json.load(open('projects/bluetooth_7_0_high_data_2/scenes/motion_graphics.json', encoding='utf-8'))
for i, s in enumerate(mg.get('scenes', [])):
    props = s.get('props', {})
    badge = props.get('badge')
    subtext = props.get('subtext')
    if badge or subtext:
        if badge and subtext and badge.lower() == subtext.lower():
            print(f"Scene idx {i} (id {s.get('scene_id')}): badge='{badge}' == subtext='{subtext}' (Component: {s.get('sceneType')})")
        elif badge in ("Conclusion", "Hook", "Introduction", "Main") or subtext in ("Conclusion", "Hook", "Introduction", "Main"):
            print(f"Scene idx {i} (id {s.get('scene_id')}): badge='{badge}', subtext='{subtext}'")
