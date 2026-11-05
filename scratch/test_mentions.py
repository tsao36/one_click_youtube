import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from core.project_manager import Project
from core.character_detector import match_scenes_for_character

p = Project('project_5')
chars = p.read_json('research/characters.json', [])
lion_char = next((c for c in chars if '獅子丸' in c.get('name', '')), None)
print("Hero character:", lion_char)

# Update lion_char search_keywords to be comprehensive
hero_kws = ["快傑獅子丸", "獅子丸", "快傑ライオン丸", "風雲ライオン丸", "ライオン丸", "風雲獅子丸", "潮哲也", "白獅", "白毛狂獅"]
for k in hero_kws:
    if k not in lion_char.setdefault("search_keywords", []):
        lion_char["search_keywords"].append(k)

matched = match_scenes_for_character(lion_char, p.scenes)
print(f"Matched scene IDs ({len(matched)}):", matched)
for sid in matched:
    s = next(s for s in p.scenes if s.scene_id == sid)
    print(f"  Scene {sid:02d}: narration='{s.narration[:40]}...' | vtype={s.visual_type} | msrc={s.media_source}")
