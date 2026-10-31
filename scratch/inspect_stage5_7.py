import json
from pathlib import Path

p = Path('projects/ai_3')
scenes = json.load(open(p / 'scenes' / 'scenes.json', encoding='utf-8'))
for s in scenes:
    sid = s.get('scene_id')
    spk = s.get('speaker')
    cid = s.get('character_id')
    img_p = s.get('image', {}).get('path')
    anim_p = s.get('animation', {}).get('path')
    anim_meta = s.get('animation', {}).get('meta')
    print(f"=== Scene {sid} ({spk}, char_id={cid}) ===")
    print(f"  image.path: {img_p}")
    print(f"  anim.path: {anim_p}")
    print(f"  anim.meta: {anim_meta}")

print("\n--- Characters folder files ---")
if (p / 'characters').exists():
    for f in (p / 'characters').glob('*'):
        if f.is_file():
            print(f"  {f.name} ({f.stat().st_size} bytes)")

print("\n--- Images folder files ---")
if (p / 'images').exists():
    for f in (p / 'images').glob('*'):
        if f.is_file():
            print(f"  {f.name} ({f.stat().st_size} bytes)")
