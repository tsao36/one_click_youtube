with open("core/character_detector.py", "r", encoding="utf-8") as f:
    text = f.read()

common_stopwords_block = '''COMMON_CHARACTER_STOPWORDS = {
    "of", "in", "the", "on", "at", "to", "for", "with", "by", "from", "and", "or",
    "a", "an", "is", "are", "was", "were", "it", "as", "be", "this", "that", "these",
    "those", "into", "over", "after", "before", "between", "under", "above", "out",
    "history", "story", "father", "mother", "founder", "pioneer", "inventor", "standard",
    "committee", "chairman", "expert", "review", "clip", "full", "speech", "talk",
    "about", "what", "why", "how", "when", "where", "who", "whom", "whose", "which",
    "demo", "video", "photo", "image", "portrait", "interview", "documentary", "audio",
    "sound", "music", "bgm", "scene", "scenes", "prompt", "text", "footage", "shot",
    "之父", "之母", "歷史", "標準", "委員會", "創始人", "發明人", "專家", "介紹", "故事",
    "訪談", "影片", "照片", "演講", "片段", "紀錄片"
}


def is_descriptive_character_keyword(phrase: str) -> bool:
    """Returns True if keyword is a descriptive query phrase rather than a proper character name/alias."""
    p_lower = phrase.lower()
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff\u3040-\u30ff]+", p_lower)
    for w in words:
        if w in COMMON_CHARACTER_STOPWORDS:
            return True
    return False

'''

target_match_func = '''def match_scenes_for_character(char: dict[str, Any], scenes: list[Any]) -> list[int]:
    """Identify which scene IDs in the project relate to this character."""
    matched_ids = []
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
        if sid is None:
            continue
        if any(kw in combined for kw in expanded_kws):
            matched_ids.append(int(sid))
    return matched_ids'''

replacement_match_func = common_stopwords_block + '''def match_scenes_for_character(char: dict[str, Any], scenes: list[Any], topic: str = "") -> list[int]:
    """Identify which scene IDs in the project relate to this character.
    Uses strict name/alias token matching and ignores generic stopwords or video topic keywords.
    """
    matched_ids = []

    # 1. Clean topic tokens to prevent matching the video's primary topic (e.g. 'wi-fi') as a character
    topic_clean = re.sub(r"[^\w\s\u4e00-\u9fff\u3040-\u30ff]", " ", (topic or "").lower())
    topic_tokens = {w.strip() for w in re.split(r"\s+", topic_clean) if len(w.strip()) >= 2}

    # 2. Extract authentic character match tokens (names + authentic aliases only)
    candidate_names = [char.get("name"), char.get("original_name")] + (char.get("aliases") or [])
    for sk in char.get("search_keywords", []):
        if sk and isinstance(sk, str) and not is_descriptive_character_keyword(sk):
            candidate_names.append(sk)

    match_patterns: list[tuple[str, bool]] = []
    seen_patterns = set()

    def _add_pat(pat: str, is_word: bool):
        p_clean = pat.strip().lower()
        if not p_clean or p_clean in seen_patterns:
            return
        if p_clean in COMMON_CHARACTER_STOPWORDS or p_clean in topic_tokens:
            return
        seen_patterns.add(p_clean)
        match_patterns.append((p_clean, is_word))

    for raw in candidate_names:
        if not raw or not isinstance(raw, str):
            continue
        sub_names = re.split(r"[/|｜（\(\)）]+", raw.strip())
        for sname in sub_names:
            sname = sname.strip()
            if not sname:
                continue
            is_cjk = bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", sname))
            if is_cjk:
                clean_cjk = re.sub(r"[·・\s]+", "", sname)
                if len(clean_cjk) >= 2:
                    _add_pat(clean_cjk, False)
                if len(clean_cjk) >= 4:
                    _add_pat(clean_cjk[:2], False)
                    _add_pat(clean_cjk[2:], False)
                    if len(clean_cjk) >= 5:
                        _add_pat(clean_cjk[-3:], False)
            else:
                clean_lat = sname.strip().lower()
                if " " in clean_lat:
                    _add_pat(clean_lat, True)
                    for part in clean_lat.split():
                        part = part.strip()
                        if len(part) >= 3:
                            _add_pat(part, True)
                else:
                    if len(clean_lat) >= 3:
                        _add_pat(clean_lat, True)

    if not match_patterns:
        return []

    for s in scenes:
        narration = getattr(s, "narration", "") or (s.get("narration", "") if isinstance(s, dict) else "")
        visual_desc = getattr(s, "visual_description", "") or (s.get("visual_description", "") if isinstance(s, dict) else "")
        target_text = f"{narration} {visual_desc}"
        sid = getattr(s, "scene_id", None) or (s.get("scene_id") if isinstance(s, dict) else None)
        if sid is None:
            continue

        matched = False
        for pat, is_word in match_patterns:
            if is_word:
                if re.search(rf"\b{re.escape(pat)}\b", target_text, re.IGNORECASE):
                    matched = True
                    break
            else:
                if pat in target_text.lower():
                    matched = True
                    break

        if matched:
            matched_ids.append(int(sid))

    return matched_ids'''

assert target_match_func in text, "target_match_func not found"
text = text.replace(target_match_func, replacement_match_func)

# Also update caller in scan_and_populate_project_characters:
old_populate_call = 'char["target_scenes"] = match_scenes_for_character(char, scenes)'
new_populate_call = 'char["target_scenes"] = match_scenes_for_character(char, scenes, topic=getattr(project.data, "topic", "") or "")'
assert old_populate_call in text, "old_populate_call not found"
text = text.replace(old_populate_call, new_populate_call)

# Also update caller in enforce_main_character_real_image_ratio:
old_enforce_call = 'matched_ids = match_scenes_for_character(main_char, scenes)'
new_enforce_call = '''auto_stock = project.data.settings.get("images", {}).get("auto_stock_mode") or project.settings.get("auto_stock_mode", "balanced")
    if auto_stock in ("disabled", "off"):
        return {"status": "disabled_by_settings", "updated_scenes": [], "real_percentage": 100.0}

    matched_ids = match_scenes_for_character(main_char, scenes, topic=getattr(project.data, "topic", "") or "")'''
assert old_enforce_call in text, "old_enforce_call not found"
text = text.replace(old_enforce_call, new_enforce_call)

# Also update caller in bulk_boost_character_media:
old_bulk_call = 'target_scene_ids = match_scenes_for_character(target_char, project.scenes)'
new_bulk_call = 'target_scene_ids = match_scenes_for_character(target_char, project.scenes, topic=getattr(project.data, "topic", "") or "")'
assert old_bulk_call in text, "old_bulk_call not found"
text = text.replace(old_bulk_call, new_bulk_call)

with open("core/character_detector.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Successfully patched core/character_detector.py")
