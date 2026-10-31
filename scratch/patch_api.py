from pathlib import Path

api_p = Path("api_server.py")
content = api_p.read_text(encoding="utf-8")

target = '    res = generate_character_portrait_ai(char_id, req.prompt, req.aspect_ratio or "1:1")\n    return res'
c_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')

replacement = '''    res = generate_character_portrait_ai(char_id, req.prompt, req.aspect_ratio or "1:1")
    return res


# ---------------- Action & Gesture Registry API ----------------
@app.get("/api/actions/gestures")
def get_action_gestures():
    """List available dramatic action postures and gesture specifications."""
    from core.action_registry import list_all_gestures
    return list_all_gestures()


class SceneActionAssignRequest(BaseModel):
    gesture_tag: str


@app.post("/api/projects/{project_id}/scenes/{scene_id}/gesture")
def assign_scene_gesture(project_id: str, scene_id: int, req: SceneActionAssignRequest):
    """Assign or override specific gesture tag to a scene."""
    from core.action_registry import get_gesture_by_tag
    p = Project(project_id)
    p.reload()
    s = p.get_scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    g = get_gesture_by_tag(req.gesture_tag)
    if not g:
        raise HTTPException(status_code=400, detail=f"Gesture {req.gesture_tag} not found")
    s.action_gesture = g.tag
    s.action = f"[gesture: {g.tag}]"
    s.action_prompt = g.visual_prompt
    s.motion_prompt = g.motion_prompt
    p.save_scenes()
    return {"status": "ok", "scene_id": scene_id, "gesture": g}


class SceneVideoGenerateRequest(BaseModel):
    engine: Optional[str] = "minimax"
    motion_prompt: Optional[str] = None


@app.post("/api/projects/{project_id}/scenes/{scene_id}/generate_video")
def generate_scene_video_endpoint(project_id: str, scene_id: int, req: SceneVideoGenerateRequest):
    """Generate dynamic video clip for a scene using MiniMax Video-01 or Hedra."""
    p = Project(project_id)
    p.reload()
    s = p.get_scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    img_cand = p.abs(s.image.path) if s.image and s.image.path else p.path("images", f"{s.tag}.png")
    if not img_cand or not img_cand.exists():
        raise HTTPException(status_code=400, detail="Scene does not have an image yet. Run Stage 5 first.")

    aud_cand = p.abs(s.audio.path) if s.audio and s.audio.path else p.path("audio", f"{s.tag}.wav")
    out_clip = p.path("animation", f"{s.tag}.mp4")

    engine = (req.engine or "minimax").lower()
    if engine in ("minimax", "video-01", "hailuo"):
        from generators.minimax_client import generate_minimax_character_video
        m_prompt = req.motion_prompt or s.motion_prompt or (s.action_prompt and f"{s.action_prompt}, expressive facial acting and head turn") or "Natural expressive eye contact and hand gestures, vertical 9:16 video"
        meta = generate_minimax_character_video(portrait_path=img_cand, prompt=m_prompt, output_mp4=out_clip, audio_path=aud_cand)
        s.animation.status = Status.COMPLETED
        s.animation.path = p.rel(out_clip)
        s.animation.meta = meta
        p.save_scenes()
        return {"status": "ok", "provider": "minimax", "clip_url": f"/media/{project_id}/{s.animation.path}", "scene": s.model_dump(mode="json")}
    elif engine == "hedra":
        from generators.hedra_client import generate_hedra_character_video, get_hedra_key
        h_key = get_hedra_key()
        if not h_key:
            raise HTTPException(status_code=400, detail="HEDRA_API_KEY is not configured")
        meta = generate_hedra_character_video(img_cand, aud_cand, out_clip, h_key, text_prompt=s.narration)
        s.animation.status = Status.COMPLETED
        s.animation.path = p.rel(out_clip)
        s.animation.meta = meta
        p.save_scenes()
        return {"status": "ok", "provider": "hedra", "clip_url": f"/media/{project_id}/{s.animation.path}", "scene": s.model_dump(mode="json")}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported video engine: {engine}")'''

assert target_norm in c_norm, 'target not found in c_norm'
c_norm = c_norm.replace(target_norm, replacement, 1)
content = c_norm.replace('\n', '\r\n')
api_p.write_text(content, encoding='utf-8')
print('api_server.py updated successfully!')
