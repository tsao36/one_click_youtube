# encoding: utf-8
with open("api_server.py", "rb") as f:
    content = f.read().decode("utf-8")

old_code = '''    from core.character_detector import bulk_boost_character_media
    res = bulk_boost_character_media(
        p,
        character_name=character_name,
        target_scene_ids=target_scene_ids,
        clip_ratio=clip_ratio,
        extra_queries=extra_queries,
    )
    return res'''

new_code = '''    from core.character_detector import bulk_boost_character_media
    res = bulk_boost_character_media(
        p,
        character_name=character_name,
        target_scene_ids=target_scene_ids,
        clip_ratio=clip_ratio,
        extra_queries=extra_queries,
    )
    return res


@app.post("/api/projects/{project_id}/characters/enforce_real_ratio")
def enforce_character_real_ratio_endpoint(project_id: str, payload: dict[str, Any]):
    """Ensure at least ratio (default 90%) of scenes mentioning the main character use authentic real visuals."""
    p = get_project(project_id)
    ratio = float(payload.get("ratio", 0.9))
    clip_ratio = float(payload.get("clip_ratio", 0.7))
    extra_queries = payload.get("extra_queries", [])
    from core.character_detector import enforce_main_character_real_image_ratio
    res = enforce_main_character_real_image_ratio(
        p,
        ratio=ratio,
        clip_ratio=clip_ratio,
        extra_queries=extra_queries,
    )
    return res'''

if old_code in content:
    content = content.replace(old_code, new_code, 1)
else:
    old_crlf = old_code.replace("\n", "\r\n")
    assert old_crlf in content, "old_crlf not found in api_server.py"
    content = content.replace(old_crlf, new_code.replace("\n", "\r\n"), 1)

with open("api_server.py", "wb") as f:
    f.write(content.encode("utf-8"))

print("api_server.py successfully patched!")
