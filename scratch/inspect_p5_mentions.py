import sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from core.project_manager import Project

p = Project('project_5')
chars = p.read_json('research/characters.json', [])
lion_char = next((c for c in chars if c.get('name') == '快傑獅子丸'), None)
print("Lion char found:", lion_char.get('name') if lion_char else None)

# Main character keywords
keywords = ["獅子丸", "ライオン丸", "快傑", "潮哲也", "風雲ライオン丸", "白鬃", "獅子丸變身"]
scenes_mentioning = []
for s in p.scenes:
    text = (s.narration or "") + " " + (s.visual_description or "")
    matched_kws = [k for k in keywords if k in text]
    anim_exists = p.path("animation", f"{s.tag}.mp4").exists()
    img_exists = p.path("images", f"{s.tag}.png").exists()
    if matched_kws:
        scenes_mentioning.append((s.scene_id, matched_kws, s.visual_type, s.media_source, anim_exists, img_exists))

print(f"\nTotal scenes: {len(p.scenes)}")
print(f"Scenes mentioning main character ({len(scenes_mentioning)}):")
real_count = 0
for sid, kws, vtype, msrc, has_anim, has_img in scenes_mentioning:
    is_real = (msrc in ["youtube_snippet", "stock_portrait", "authentic_portrait", "historical_footage"]) or has_anim
    if is_real: real_count += 1
    print(f"  Scene {sid:02d}: real={is_real} (msrc={msrc}, vtype={vtype}, has_anim={has_anim}) | kws={kws}")

print(f"\nReal assets ratio: {real_count}/{len(scenes_mentioning)} = {real_count / len(scenes_mentioning) * 100:.1f}%")
