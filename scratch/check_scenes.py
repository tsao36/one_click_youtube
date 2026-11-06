import json

with open("projects/wi_fi/scenes/scenes.json", "r", encoding="utf-8") as f:
    scenes = json.load(f)

print(f"Total scenes: {len(scenes)}")
for s in scenes:
    img = s.get("image", {})
    img_meta = img.get("meta", {})
    print(f"Scene {s.get('scene_id'):03d}: visual_type={s.get('visual_type')}, media_src={s.get('media_source')}, search_kw={s.get('search_keyword')}")
    print(f"   image_path={img.get('path')}, provider={img_meta.get('provider')}, title={img_meta.get('title')}, source={img_meta.get('source')}, is_stock={img_meta.get('is_stock')}, url={img_meta.get('media_url') or img_meta.get('url')}")
