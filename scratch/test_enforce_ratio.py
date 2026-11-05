import sys, os, json, math, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from core.project_manager import Project
from core.character_detector import (
    match_scenes_for_character,
    fetch_online_media_for_character,
    extract_youtube_snippet,
    download_youtube_thumbnail,
    download_media_file,
    format_stock_image
)

p = Project('project_5')

def get_main_character(project):
    chars = project.read_json("research/characters.json", [])
    if not chars:
        return None
    topic = (getattr(project.data, "topic", "") or project.id or "").lower()
    topic_keywords = [t.strip().lower() for t in re.split(r"[/（\(\)）\s·・]+", topic) if len(t.strip()) >= 2]
    for c in chars:
        name = (c.get("name") or "").lower()
        orig = (c.get("original_name") or "").lower()
        if any(tk in name or tk in orig for tk in topic_keywords):
            return c
    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            if "飾演" not in role and "actor" not in role:
                return c
    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            return c
    return chars[0]

mc = get_main_character(p)
print("MC:", mc.get("name"))

# Update match_scenes_for_character simulation
def match_scenes_enhanced(char, scenes):
    matched_ids = []
    keywords = [char.get("name"), char.get("original_name")] + char.get("search_keywords", [])
    expanded_kws = set()
    for k in keywords:
        if not k or not isinstance(k, str):
            continue
        parts = re.split(r"[/（\(\)）\s·・]+", k)
        for p_clean in parts:
            p_clean = p_clean.strip().lower()
            if len(p_clean) >= 2:
                expanded_kws.add(p_clean)
                if len(p_clean) >= 4 and re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", p_clean):
                    expanded_kws.add(p_clean[:2])
                    expanded_kws.add(p_clean[2:])
                    if len(p_clean) >= 5:
                        expanded_kws.add(p_clean[-3:])
    for s in scenes:
        narration = getattr(s, "narration", "") or (s.get("narration", "") if isinstance(s, dict) else "")
        prompt = getattr(s, "prompt", "") or (s.get("prompt", "") if isinstance(s, dict) else "")
        visual_desc = getattr(s, "visual_description", "") or (s.get("visual_description", "") if isinstance(s, dict) else "")
        search_kw = getattr(s, "search_keyword", "") or (s.get("search_keyword", "") if isinstance(s, dict) else "")
        combined = f"{narration} {prompt} {visual_desc} {search_kw}".lower()
        sid = getattr(s, "scene_id", None) or (s.get("scene_id") if isinstance(s, dict) else None)
        if sid is None: continue
        if any(kw in combined for kw in expanded_kws):
            matched_ids.append(int(sid))
    return matched_ids

matched_ids = match_scenes_enhanced(mc, p.scenes)
print(f"Matched {len(matched_ids)} scenes:", matched_ids)

# Check real vs generated
real_ids = []
gen_ids = []
scenes_map = {s.scene_id: s for s in p.scenes}
for sid in matched_ids:
    s = scenes_map[sid]
    is_real = (
        getattr(s, "media_source", "ai") in ("youtube_snippet", "stock_portrait", "authentic_portrait", "celebrity_portrait", "wikimedia", "historical_footage")
        or getattr(s, "visual_type", "") in ("historical_footage", "authentic_portrait", "talking_actor")
        or p.path("animation", f"{s.tag}.mp4").exists()
    )
    if is_real: real_ids.append(sid)
    else: gen_ids.append(sid)

print("Current real:", real_ids, f"({len(real_ids)}/{len(matched_ids)} = {len(real_ids)/len(matched_ids)*100:.1f}%)")
print("Current generated:", gen_ids)
