# Script to update core/drama_pipeline.py with Action & Gesture Registry, Consistent Face Reference, and MiniMax Video-01
from pathlib import Path

drama_p = Path("core/drama_pipeline.py")
content = drama_p.read_text(encoding="utf-8")

# 1. Update Stage 4 prompts generation
old_prompts_loop = """            spk = s.speaker or shot.get("speaker", "主角")

            c_info = next((c for c in roster if c.get("name") == spk or c.get("id") == spk or spk in c.get("name", "")), {})

            app = c_info.get("appearance") or c_info.get("appearance_prompt") or f"{spk}"

            act = shot.get("action") or s.action or "面對鏡頭強烈情緒爆發，神態鮮明"

            emo = shot.get("dramatic_beat") or "intense dramatic expression"

            shot_size = shot.get("shot_size") or "medium_close_up"

            cam = shot.get("camera_motion") or s.camera_motion or "push_in"



            prompt_str = f"Cinematic {shot_size} vertical portrait (9:16) of {app}, {act}, {emo}, emotional intensity, high dynamic range cinematic dramatic lighting, 8k resolution, highly detailed photorealistic"

            s.prompt = prompt_str

            s.visual_description = prompt_str

            s.camera_motion = cam

            prompts_map[s.tag] = prompt_str"""

new_prompts_loop = """            from core.action_registry import assign_gesture_to_scene, get_gesture_by_tag
            spk = s.speaker or shot.get("speaker", "主角")
            c_info = next((c for c in roster if c.get("name") == spk or c.get("id") == spk or spk in c.get("name", "")), {})
            app = c_info.get("appearance") or c_info.get("appearance_prompt") or f"{spk}"

            # Assign Action & Gesture from Registry
            prev_tag = scenes[i - 1].action_gesture if i > 0 else None
            assigned_gesture = get_gesture_by_tag(s.action_gesture) if s.action_gesture else None
            if not assigned_gesture:
                assigned_gesture = assign_gesture_to_scene(
                    narration=s.narration or "",
                    emotion=shot.get("dramatic_beat") or s.dramatic_beat or "",
                    role_or_speaker=spk,
                    previous_tag=prev_tag,
                    scene_idx=i
                )
            s.action_gesture = assigned_gesture.tag
            s.action = f"[gesture: {assigned_gesture.tag}]"
            s.action_prompt = assigned_gesture.visual_prompt
            s.motion_prompt = assigned_gesture.motion_prompt

            act = assigned_gesture.visual_prompt
            emo = shot.get("dramatic_beat") or s.dramatic_beat or "intense dramatic expression"
            shot_size = shot.get("shot_size") or assigned_gesture.framing or "medium_close_up"
            cam = shot.get("camera_motion") or s.camera_motion or "push_in"

            prompt_str = f"Cinematic {shot_size} vertical portrait (9:16) of {app}, {act}, {emo}, emotional intensity, high dynamic range cinematic dramatic lighting, 8k resolution, highly detailed photorealistic"
            s.prompt = prompt_str
            s.visual_description = prompt_str
            s.camera_motion = cam
            prompts_map[s.tag] = prompt_str"""

# 2. Update Stage 5 images generation (Consistent Face Reference with unique posture)
old_stage5_synthesis = """                styled_char_path = self.p.path("characters", f"{char_id}_styled_9x16.png")

                if styled_char_path.exists() and styled_char_path.stat().st_size > 1000 and cached_portraits.get(char_id) == styled_char_path:

                    import shutil

                    shutil.copy2(str(styled_char_path), str(img_path))

                else:

                    from generators.face_reference_generator import generate_face_referenced_portrait

                    clothes_p = "sharp corporate navy blue executive suit and necktie with rimless gold glasses" if ("經理" in spk or "manager" in spk.lower()) else ("bespoke charcoal tailored wool overcoat" if ("陳董" in spk or "董" in spk) else "stylish contemporary professional attire")

                    bg_p = "modern luxury executive high-rise corporate corner office with glass desk and city skyline view"

                    self.p.activity(f"Stage 5/9: Synthesizing character body, clothes and office setting with {spk}'s uploaded face...")

                    try:

                        generate_face_referenced_portrait(

                            reference_face_path=portrait_cand,

                            clothing_prompt=clothes_p,

                            background_prompt=bg_p,

                            output_path=styled_char_path,

                            target_width=width,

                            target_height=height

                        )

                        import shutil

                        shutil.copy2(str(styled_char_path), str(img_path))

                        cached_portraits[char_id] = styled_char_path

                    except Exception as s_err:

                        log.warning("Face-referenced portrait synthesis failed (%s); using auto-oriented crop fallback", s_err)"""

new_stage5_synthesis = """                styled_char_path = self.p.path("characters", f"{char_id}_styled_9x16.png")
                from generators.face_reference_generator import generate_face_referenced_portrait
                clothes_p = "sharp corporate navy blue executive suit and necktie with rimless gold glasses" if ("經理" in spk or "manager" in spk.lower()) else ("bespoke charcoal tailored wool overcoat" if ("陳董" in spk or "董" in spk) else "stylish contemporary professional attire")
                bg_p = "modern luxury executive high-rise corporate corner office with glass desk and city skyline view"
                act_p = getattr(s, "action_prompt", "") or getattr(s, "action", "")

                # 1. If anchor style portrait does not exist yet, synthesize it first
                if not (styled_char_path.exists() and styled_char_path.stat().st_size > 1000):
                    self.p.activity(f"Stage 5/9: Synthesizing canonical anchor portrait for {spk}...")
                    try:
                        generate_face_referenced_portrait(
                            reference_face_path=portrait_cand,
                            clothing_prompt=clothes_p,
                            background_prompt=bg_p,
                            action_prompt="authoritative executive portrait stance",
                            anchor_reference_path=None,
                            output_path=styled_char_path,
                            target_width=width,
                            target_height=height
                        )
                        cached_portraits[char_id] = styled_char_path
                    except Exception as anchor_err:
                        log.warning("Canonical anchor portrait synthesis failed (%s); using fallback", anchor_err)

                # 2. Consistent Face Reference: synthesize scene-specific posture anchored to styled_char_path
                synthesized_scene_img = False
                if act_p and styled_char_path.exists() and styled_char_path.stat().st_size > 1000:
                    self.p.activity(f"Stage 5/9: Anchoring {spk} face & attire with action [{getattr(s, 'action_gesture', 'pose')}] (Scene {s.scene_id})...")
                    try:
                        generate_face_referenced_portrait(
                            reference_face_path=portrait_cand,
                            clothing_prompt=clothes_p,
                            background_prompt=bg_p,
                            action_prompt=act_p,
                            anchor_reference_path=styled_char_path,
                            output_path=img_path,
                            target_width=width,
                            target_height=height
                        )
                        synthesized_scene_img = (img_path.exists() and img_path.stat().st_size > 1000)
                    except Exception as pose_err:
                        log.warning("Scene-specific action synthesis failed (%s); copying anchor fallback", pose_err)

                # 3. Graceful fallback to styled_char_path copy if synthesis was skipped or failed
                if not synthesized_scene_img:
                    import shutil
                    if styled_char_path.exists() and styled_char_path.stat().st_size > 1000:
                        shutil.copy2(str(styled_char_path), str(img_path))
                    else:
                        cached_portraits[char_id] = styled_char_path"""

# 3. Update Stage 7 animation engine selection (Respect MiniMax Video-01 when selected or configured)
old_stage7_engine = """        target_anim_engine = self.get_stage_model("animation") or "hedra"
        # In Short Drama mode, if hedra_key is configured, hedra is the designated lip-sync engine
        if hedra_key and (not target_anim_engine or target_anim_engine in ("minimax", "hailuo", "cloud")):
            target_anim_engine = "hedra" """

new_stage7_engine = """        from generators.minimax_client import is_minimax_configured
        chosen_engine = self.get_stage_model("animation")
        # Priority: explicit user choice > minimax if configured > hedra
        if chosen_engine and chosen_engine in ("minimax", "video-01", "hailuo"):
            target_anim_engine = "minimax"
        elif chosen_engine and chosen_engine in ("hedra", "kling", "kling_avatar", "local_fallback"):
            target_anim_engine = chosen_engine
        elif is_minimax_configured():
            target_anim_engine = "minimax"
        elif hedra_key:
            target_anim_engine = "hedra"
        else:
            target_anim_engine = "local_fallback" """

# 4. Update Stage 7 animation loop to prioritize MiniMax Video-01 with motion_prompt
old_stage7_loop = """            # 1. Primary: Hedra AI Character Lip-Syncing (Guaranteed phoneme/lip synchronization)
            if not success and hedra_key and (target_anim_engine in ("hedra", "cloud") or target_anim_engine not in ("local_fallback", "kling_avatar")):
                try:
                    self.p.activity(f"Stage 7/9: Hedra rendering lip-synced video for {s.speaker} (Scene {s.scene_id})...")
                    meta = generate_hedra_character_video(portrait_file, audio_file, out_clip, hedra_key, text_prompt=s.narration, cancel_check=self.is_cancelled)
                    success = True
                    log.info("Hedra lip-sync succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)
                except Exception as he:
                    log.warning("Hedra lip-sync failed for scene %d (%s); trying fallback: %s", s.scene_id, he)

            # 2. Secondary: Fal.ai Kling Avatar / SadTalker if Fal key configured



            if not success and fal_key and "TOP_UP" not in str(meta):

                try:

                    self.p.activity(f"Stage 7/9: Fal.ai generating actor performance for {s.speaker} (Scene {s.scene_id})...")

                    if target_anim_engine in ("kling", "kling_avatar"):

                        meta = _generate_fal_kling_avatar(portrait_file, audio_file, out_clip, fal_key)

                    else:

                        meta = _generate_fal_sadtalker(portrait_file, audio_file, out_clip, fal_key)

                    success = True

                except Exception as fe:

                    log.warning("Fal avatar generation failed for scene %d (%s); falling back...", s.scene_id, fe)







            # 3. Tertiary: MiniMax Video-01 physical dynamic motion
            if not success and target_anim_engine in ("minimax", "hailuo", "video-01"):
                try:
                    from generators.minimax_client import generate_minimax_character_video
                    self.p.activity(f"Stage 7/9: MiniMax generating dynamic action & scene for {s.speaker} (Scene {s.scene_id})...")
                    cam_text = "A dramatic cinematic push-in." if s.camera_motion and "push" in s.camera_motion else ("A smooth camera pull-out shot." if s.camera_motion and "pull" in s.camera_motion else "Cinematic camera movement.")
                    raw_action = s.visual_description or s.prompt or ""
                    desc_parts = [p.strip() for p in raw_action.split(",") if p.strip() and not any(tag in p.lower() for tag in ("8k", "resolution", "photorealistic", "vertical portrait", "9:16"))]
                    core_action = ", ".join(desc_parts[:3]) if desc_parts else f"{s.speaker} speaking in dramatic scene"
                    act_prompt = f"{cam_text} {core_action}, natural expressive facial acting and body movement, cinematic dramatic lighting, vertical 9:16 video"
                    meta = generate_minimax_character_video(portrait_path=portrait_file, prompt=act_prompt, output_mp4=out_clip, audio_path=audio_file, cancel_check=self.is_cancelled)
                    success = True
                except Exception as me:
                    log.warning("MiniMax generation failed for scene %d (%s); falling back...", s.scene_id, me)"""

new_stage7_loop = """            # 1. MiniMax Video-01 Physical Dynamic Motion (Natural gestures & camera dynamic acting)
            if not success and (target_anim_engine in ("minimax", "hailuo", "video-01") or (not hedra_key and is_minimax_configured())):
                try:
                    from generators.minimax_client import generate_minimax_character_video
                    self.p.activity(f"Stage 7/9: MiniMax Video-01 generating physical dynamic acting for {s.speaker} (Scene {s.scene_id})...")
                    cam_text = "Dramatic cinematic push-in shot." if s.camera_motion and "push" in s.camera_motion else ("Smooth camera pull-out shot." if s.camera_motion and "pull" in s.camera_motion else "Cinematic camera movement.")
                    motion_p = getattr(s, "motion_prompt", "") or getattr(s, "action_prompt", "") or f"{s.speaker} delivering intense dialogue"
                    act_prompt = f"{cam_text} {motion_p}, natural expressive facial acting and hand gestures, eye contact with camera, authentic breathing, cinematic dramatic lighting, vertical 9:16 video"
                    meta = generate_minimax_character_video(portrait_path=portrait_file, prompt=act_prompt, output_mp4=out_clip, audio_path=audio_file, cancel_check=self.is_cancelled)
                    success = True
                    log.info("MiniMax Video-01 dynamic video succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)
                except Exception as me:
                    log.warning("MiniMax generation failed for scene %d (%s); falling back: %s", s.scene_id, me)

            # 2. Hedra AI Character Lip-Syncing (Precision phoneme lip synchronization)
            if not success and hedra_key and (target_anim_engine in ("hedra", "cloud") or target_anim_engine not in ("local_fallback", "kling_avatar")):
                try:
                    self.p.activity(f"Stage 7/9: Hedra rendering lip-synced video for {s.speaker} (Scene {s.scene_id})...")
                    meta = generate_hedra_character_video(portrait_file, audio_file, out_clip, hedra_key, text_prompt=s.narration, cancel_check=self.is_cancelled)
                    success = True
                    log.info("Hedra lip-sync succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)
                except Exception as he:
                    log.warning("Hedra lip-sync failed for scene %d (%s); trying fallback: %s", s.scene_id, he)

            # 3. Fal.ai Kling Avatar / SadTalker if Fal key configured
            if not success and fal_key and "TOP_UP" not in str(meta):
                try:
                    self.p.activity(f"Stage 7/9: Fal.ai generating actor performance for {s.speaker} (Scene {s.scene_id})...")
                    if target_anim_engine in ("kling", "kling_avatar"):
                        meta = _generate_fal_kling_avatar(portrait_file, audio_file, out_clip, fal_key)
                    else:
                        meta = _generate_fal_sadtalker(portrait_file, audio_file, out_clip, fal_key)
                    success = True
                except Exception as fe:
                    log.warning("Fal avatar generation failed for scene %d (%s); falling back: %s", s.scene_id, fe)"""

# Apply replacements with normalization fallback
pairs = [
    ("Stage 4 prompts loop", old_prompts_loop, new_prompts_loop),
    ("Stage 5 synthesis", old_stage5_synthesis, new_stage5_synthesis),
    ("Stage 7 engine selection", old_stage7_engine, new_stage7_engine),
    ("Stage 7 animation loop", old_stage7_loop, new_stage7_loop)
]

for name, old_s, new_s in pairs:
    if old_s in content:
        content = content.replace(old_s, new_s, 1)
        print(f"OK: {name}")
    else:
        c_norm = content.replace("\r\n", "\n")
        old_norm = old_s.replace("\r\n", "\n")
        if old_norm in c_norm:
            c_norm = c_norm.replace(old_norm, new_s.replace("\r\n", "\n"), 1)
            content = c_norm.replace("\n", "\r\n")
            print(f"OK (normalized LF): {name}")
        else:
            print(f"FAILED: {name}")

drama_p.write_text(content, encoding="utf-8")
print("Done writing core/drama_pipeline.py")
