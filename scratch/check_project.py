import json

for pid in ['project_2', 'ai_3', 'project']:
    try:
        with open(f'projects/{pid}/project.json', 'r', encoding='utf-8') as f:
            d = json.load(f)
            print(f'=== {pid} ===')
            print('mode:', d.get('mode'))
            print('default_avatar:', d.get('settings', {}).get('default_avatar'))
            print('avatar_profile in settings:', d.get('settings', {}).get('avatar_profile'))
            scenes = d.get('scenes', [])
            for s in scenes:
                if s.get('is_presenter'):
                    sid = s.get("scene_id")
                    av = s.get("avatar_profile")
                    meta = s.get("animation", {}).get("meta")
                    err = s.get("animation", {}).get("error")
                    print(f'Scene {sid}: is_presenter=True, avatar_profile={av}, meta={meta}, error={err}')
    except Exception as e:
        print(f'{pid} error: {e}')
