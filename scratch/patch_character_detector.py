# encoding: utf-8
with open("core/character_detector.py", "rb") as f:
    content = f.read().decode("utf-8")

old_kw = 'expanded_kws.add(p_clean[:2])'
new_kw = '''expanded_kws.add(p_clean[:2])
                    expanded_kws.add(p_clean[2:])
                    if len(p_clean) >= 5:
                        expanded_kws.add(p_clean[-3:])'''
assert old_kw in content, "old_kw not in content"
content = content.replace(old_kw, new_kw, 1)

old_comb = 'combined = (narration + " " + prompt).lower()'
new_comb = '''visual_desc = getattr(s, "visual_description", "") or (s.get("visual_description", "") if isinstance(s, dict) else "")
        search_kw = getattr(s, "search_keyword", "") or (s.get("search_keyword", "") if isinstance(s, dict) else "")
        combined = f"{narration} {prompt} {visual_desc} {search_kw}".lower()'''
assert old_comb in content, "old_comb not in content"
content = content.replace(old_comb, new_comb, 1)

old_boost = 'def bulk_boost_character_media('
helper_code = '''def get_main_character(project: Project) -> Optional[dict[str, Any]]:
    """Identify the primary protagonist / hero character for this project."""
    chars = project.read_json("research/characters.json", [])
    if not chars:
        return None

    # 1. Topic keyword match against character name or original_name
    topic = (getattr(project.data, "topic", "") or project.id or "").lower()
    topic_keywords = [t.strip().lower() for t in re.split(r"[/（\(\)）\s·・]+", topic) if len(t.strip()) >= 2]
    for c in chars:
        name = (c.get("name") or "").lower()
        orig = (c.get("original_name") or "").lower()
        if any(tk in name or tk in orig for tk in topic_keywords):
            return c

    # 2. Hero or protagonist flag/role
    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            if "飾演" not in role and "actor" not in role:
                return c

    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            return c

    # 3. Default to first character
    return chars[0]


def enforce_main_character_real_image_ratio(
    project: Project,
    ratio: float = 0.9,
    clip_ratio: float = 0.7,
    extra_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Ensure that at least `ratio` (default 0.9 / 90%) of scenes mentioning
    the main character use authentic real images/clips rather than AI-generated images.
    """
    main_char = get_main_character(project)
    if not main_char:
        return {"status": "no_character", "updated_scenes": [], "real_percentage": 0.0}

    # Ensure main_char has images and clips
    if not main_char.get("images") or not main_char.get("clips"):
        fresh = fetch_online_media_for_character(main_char, extra_queries=extra_queries)
        main_char["images"] = fresh["images"]
        main_char["clips"] = fresh["clips"]

    scenes = project.scenes or []
    if not scenes:
        return {"status": "no_scenes", "updated_scenes": [], "real_percentage": 100.0}

    # Match all scenes where the main character is mentioned
    matched_ids = match_scenes_for_character(main_char, scenes)
    if not matched_ids:
        name_kws = [main_char.get("name"), main_char.get("original_name")] + (extra_queries or [])
        matched_ids = [
            s.scene_id for s in scenes
            if any(k and k in ((s.narration or "") + " " + (s.visual_description or "")) for k in name_kws)
        ]

    if not matched_ids:
        return {"status": "no_mentioned_scenes", "updated_scenes": [], "real_percentage": 100.0}

    scenes_map = {s.scene_id: s for s in scenes}

    # Classify current mentioned scenes: which are real vs generated
    real_scene_ids = []
    generated_scene_ids = []

    for sid in matched_ids:
        s = scenes_map.get(sid)
        if not s:
            continue
        is_real = (
            getattr(s, "media_source", "ai") in ("youtube_snippet", "stock_portrait", "authentic_portrait", "celebrity_portrait", "wikimedia", "historical_footage")
            or getattr(s, "visual_type", "") in ("historical_footage", "authentic_portrait", "talking_actor")
            or project.path("animation", f"{s.tag}.mp4").exists()
        )
        if is_real:
            real_scene_ids.append(sid)
        else:
            generated_scene_ids.append(sid)

    total_mentioned = len(matched_ids)
    target_real_count = math.ceil(total_mentioned * ratio)
    needed_boost_count = max(0, target_real_count - len(real_scene_ids))

    log.info(
        "Main character '%s' mentioned in %d scenes. Current real: %d (%.1f%%). Target: %d (%.0f%%). Needed: %d",
        main_char.get("name"),
        total_mentioned,
        len(real_scene_ids),
        (len(real_scene_ids) / total_mentioned) * 100 if total_mentioned else 0,
        target_real_count,
        ratio * 100,
        needed_boost_count,
    )

    updated_ids = []
    scenes_to_convert = generated_scene_ids[:max(needed_boost_count, len(generated_scene_ids))] if needed_boost_count > 0 else []

    clips_pool = main_char.get("clips", [])
    images_pool = main_char.get("images", [])

    for idx, sid in enumerate(scenes_to_convert):
        s = scenes_map.get(sid)
        if not s:
            continue

        use_clip = (idx / max(1, len(scenes_to_convert))) < clip_ratio and bool(clips_pool)
        img_out = project.path("images", f"{s.tag}.png")
        clip_out = project.path("animation", f"{s.tag}.mp4")

        scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
        clip_dur = min(max(7.0, scene_len), 15.0)

        if use_clip:
            chosen_clip = clips_pool[idx % len(clips_pool)]
            s.media_source = "youtube_snippet"
            s.search_keyword = chosen_clip.get("url")
            s.visual_type = "historical_footage"
            try:
                extract_youtube_snippet(
                    chosen_clip["url"],
                    output_video_path=clip_out,
                    output_image_path=img_out,
                    duration_sec=clip_dur,
                    as_clip=True,
                )
                updated_ids.append(sid)
                real_scene_ids.append(sid)
            except Exception as e:
                log.warning("Clip extraction failed for scene %s: %s", sid, e)
        elif images_pool:
            chosen_img = images_pool[idx % len(images_pool)]
            s.media_source = "stock_portrait"
            s.search_keyword = chosen_img.get("title") or main_char.get("name")
            s.visual_type = "authentic_portrait"
            img_url = chosen_img.get("url")
            try:
                if "youtube.com" in img_url or "ytimg.com" in img_url:
                    vid_m = re.search(r"vi/([a-zA-Z0-9_-]{11})", img_url)
                    if vid_m:
                        download_youtube_thumbnail(vid_m.group(1), img_out)
                    else:
                        download_media_file(img_url, img_out)
                        format_stock_image(img_out, 1920, 1080)
                else:
                    download_media_file(img_url, img_out)
                    format_stock_image(img_out, 1920, 1080)
                if clip_out.exists():
                    clip_out.unlink(missing_ok=True)
                updated_ids.append(sid)
                real_scene_ids.append(sid)
            except Exception as e:
                log.warning("Image apply failed for scene %s: %s", sid, e)

    final_real_count = len(set(real_scene_ids))
    final_ratio = (final_real_count / total_mentioned) if total_mentioned > 0 else 1.0

    if updated_ids:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()

    return {
        "status": "success",
        "character": main_char.get("name"),
        "total_mentioned_scenes": total_mentioned,
        "real_scenes_count": final_real_count,
        "real_percentage": round(final_ratio * 100, 1),
        "target_percentage": round(ratio * 100, 1),
        "updated_scenes": updated_ids,
        "all_real_scenes": list(set(real_scene_ids)),
        "all_mentioned_scenes": matched_ids,
    }


def bulk_boost_character_media('''
assert old_boost in content, "old_boost not in content"
content = content.replace(old_boost, helper_code, 1)

with open("core/character_detector.py", "wb") as f:
    f.write(content.encode("utf-8"))

print("core/character_detector.py successfully patched!")
