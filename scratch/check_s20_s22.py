import sys, json
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('projects/project_5/scenes/scenes.json', encoding='utf-8'))
for sc in d:
    if sc['scene_id'] in (19, 20, 21, 22, 23):
        print(f"=== Scene {sc['scene_id']} ===")
        print("Narration:", sc['narration'])
        print("Search keyword:", sc.get('search_keyword'))
        print("Media source:", sc.get('media_source'))
        img_meta = sc.get('image', {}).get('meta', {})
        print("Image meta:", json.dumps({k: img_meta.get(k) for k in ('provider', 'source', 'title', 'media_url', 'video_id', 'url')}, ensure_ascii=False))
