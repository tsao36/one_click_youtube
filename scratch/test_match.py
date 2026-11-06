import json
import re

with open("projects/wi_fi/research/characters.json", "r", encoding="utf-8") as f:
    chars = json.load(f)

with open("projects/wi_fi/scenes/scenes.json", "r", encoding="utf-8") as f:
    scenes = json.load(f)

char = chars[0]
print("Character:", char.get("name"), char.get("original_name"))
print("Search keywords:", char.get("search_keywords"))

keywords = [char.get("name"), char.get("original_name")] + char.get("search_keywords", [])
expanded_kws = set()
for k in keywords:
    if not k or not isinstance(k, str):
        continue
    parts = re.split(r"[/（\(\)）\s·・]+", k)
    for p in parts:
        p_clean = p.strip().lower()
        if len(p_clean) >= 2:
            expanded_kws.add(p_clean)

print("Expanded keywords:", expanded_kws)

matched = []
for s in scenes:
    narration = s.get("narration", "") or ""
    prompt = s.get("prompt", "") or ""
    visual_desc = s.get("visual_description", "") or ""
    search_kw = s.get("search_keyword", "") or ""
    combined = f"{narration} {prompt} {visual_desc} {search_kw}".lower()
    sid = s.get("scene_id")
    for kw in expanded_kws:
        if kw in combined:
            matched.append((sid, kw))
            break

print(f"Total matched scenes: {len(matched)} / {len(scenes)}")
print("First 10 matches (sid, matched_keyword):", matched[:10])
