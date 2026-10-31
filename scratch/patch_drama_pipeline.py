# Precise patch script for core/drama_pipeline.py
from pathlib import Path

drama_p = Path("core/drama_pipeline.py")
lines = drama_p.read_text(encoding="utf-8").splitlines(keepends=True)

# 1. Update Stage 4 Prompts Loop (around line 967)
# Find line with spk = s.speaker or shot.get("speaker"
idx_spk = next(i for i, l in enumerate(lines) if 'spk = s.speaker or shot.get("speaker"' in l)
# Find end of this block: self.p.progress("prompts", i + 1, len(scenes))
idx_prog = next(i for i, l in enumerate(lines) if 'self.p.progress("prompts", i + 1, len(scenes))' in l)

new_stage4_lines = [
    '            from core.action_registry import assign_gesture_to_scene, get_gesture_by_tag\n',
    '            spk = s.speaker or shot.get("speaker", "主角")\n',
    '            c_info = next((c for c in roster if c.get("name") == spk or c.get("id") == spk or spk in c.get("name", "")), {})\n',
    '            app = c_info.get("appearance") or c_info.get("appearance_prompt") or f"{spk}"\n',
    '\n',
    '            # Action & Gesture Registry: Assign dynamic dramatic posture per scene\n',
    '            prev_tag = scenes[i - 1].action_gesture if i > 0 else None\n',
    '            assigned_gesture = get_gesture_by_tag(s.action_gesture) if s.action_gesture else None\n',
    '            if not assigned_gesture:\n',
    '                assigned_gesture = assign_gesture_to_scene(\n',
    '                    narration=s.narration or "",\n',
    '                    emotion=shot.get("dramatic_beat") or s.dramatic_beat or "",\n',
    '                    role_or_speaker=spk,\n',
    '                    previous_tag=prev_tag,\n',
    '                    scene_idx=i\n',
    '                )\n',
    '            s.action_gesture = assigned_gesture.tag\n',
    '            s.action = f"[gesture: {assigned_gesture.tag}]"\n',
    '            s.action_prompt = assigned_gesture.visual_prompt\n',
    '            s.motion_prompt = assigned_gesture.motion_prompt\n',
    '\n',
    '            act = assigned_gesture.visual_prompt\n',
    '            emo = shot.get("dramatic_beat") or s.dramatic_beat or "intense dramatic expression"\n',
    '            shot_size = shot.get("shot_size") or assigned_gesture.framing or "medium_close_up"\n',
    '            cam = shot.get("camera_motion") or s.camera_motion or "push_in"\n',
    '\n',
    '            prompt_str = f"Cinematic {shot_size} vertical portrait (9:16) of {app}, {act}, {emo}, emotional intensity, high dynamic range cinematic dramatic lighting, 8k resolution, highly detailed photorealistic"\n',
    '            s.prompt = prompt_str\n',
    '            s.visual_description = prompt_str\n',
    '            s.camera_motion = cam\n',
    '            prompts_map[s.tag] = prompt_str\n',
]

lines[idx_spk:idx_prog] = new_stage4_lines
print("1. Patched Stage 4 Prompts Loop")

# 2. Update Stage 5 Styled Char Synthesis (Consistent Face Reference with unique posture)
idx_styled = next(i for i, l in enumerate(lines) if 'styled_char_path = self.p.path("characters"' in l)
# Find end of this block: where fallback ImageOps handling starts or next block
idx_styled_end = next(i for i, l in enumerate(lines) if 'except Exception as s_err:' in l) + 1

new_stage5_lines = [
    '                styled_char_path = self.p.path("characters", f"{char_id}_styled_9x16.png")\n',
    '                from generators.face_reference_generator import generate_face_referenced_portrait\n',
    '                clothes_p = "sharp corporate navy blue executive suit and necktie with rimless gold glasses" if ("經理" in spk or "manager" in spk.lower()) else ("bespoke charcoal tailored wool overcoat" if ("陳董" in spk or "董" in spk) else "stylish contemporary professional attire")\n',
    '                bg_p = "modern luxury executive high-rise corporate corner office with glass desk and city skyline view"\n',
    '                act_p = getattr(s, "action_prompt", "") or getattr(s, "action", "")\n',
    '\n',
    '                # 1. Synthesize canonical anchor portrait once per character if not yet cached\n',
    '                if not (styled_char_path.exists() and styled_char_path.stat().st_size > 1000):\n',
    '                    self.p.activity(f"Stage 5/9: Synthesizing canonical anchor portrait for {spk}...")\n',
    '                    try:\n',
    '                        generate_face_referenced_portrait(\n',
    '                            reference_face_path=portrait_cand,\n',
    '                            clothing_prompt=clothes_p,\n',
    '                            background_prompt=bg_p,\n',
    '                            action_prompt="authoritative executive portrait stance",\n',
    '                            anchor_reference_path=None,\n',
    '                            output_path=styled_char_path,\n',
    '                            target_width=width,\n',
    '                            target_height=height\n',
    '                        )\n',
    '                        cached_portraits[char_id] = styled_char_path\n',
    '                    except Exception as anchor_err:\n',
    '                        log.warning("Canonical anchor portrait synthesis failed (%s); using fallback", anchor_err)\n',
    '\n',
    '                # 2. Consistent Face Reference: synthesize scene-specific posture anchored to styled_char_path\n',
    '                synthesized_scene_img = False\n',
    '                if act_p and styled_char_path.exists() and styled_char_path.stat().st_size > 1000:\n',
    '                    self.p.activity(f"Stage 5/9: Anchoring {spk} face & attire with action [{getattr(s, "action_gesture", "pose")}] (Scene {s.scene_id})...")\n',
    '                    try:\n',
    '                        generate_face_referenced_portrait(\n',
    '                            reference_face_path=portrait_cand,\n',
    '                            clothing_prompt=clothes_p,\n',
    '                            background_prompt=bg_p,\n',
    '                            action_prompt=act_p,\n',
    '                            anchor_reference_path=styled_char_path,\n',
    '                            output_path=img_path,\n',
    '                            target_width=width,\n',
    '                            target_height=height\n',
    '                        )\n',
    '                        synthesized_scene_img = (img_path.exists() and img_path.stat().st_size > 1000)\n',
    '                    except Exception as pose_err:\n',
    '                        log.warning("Scene-specific action synthesis failed (%s); copying anchor fallback", pose_err)\n',
    '\n',
    '                # 3. Graceful fallback to styled_char_path copy if synthesis was skipped or failed\n',
    '                if not synthesized_scene_img:\n',
    '                    import shutil\n',
    '                    if styled_char_path.exists() and styled_char_path.stat().st_size > 1000:\n',
    '                        shutil.copy2(str(styled_char_path), str(img_path))\n',
    '                    else:\n',
    '                        cached_portraits[char_id] = styled_char_path\n',
    '                    log.info("Anchor copy applied for Scene %d (%s)", s.scene_id, s.speaker)\n',
]

lines[idx_styled:idx_styled_end] = new_stage5_lines
print("2. Patched Stage 5 Image Synthesis")

# 3. Update Stage 7 Animation Engine Selection
idx_engine = next(i for i, l in enumerate(lines) if 'target_anim_engine = self.get_stage_model("animation")' in l)
idx_engine_end = next(i for i, l in enumerate(lines[idx_engine:], start=idx_engine) if 'target_anim_engine = "hedra"' in l) + 1

new_engine_lines = [
    '        from generators.minimax_client import is_minimax_configured\n',
    '        chosen_engine = self.get_stage_model("animation")\n',
    '        # Priority: explicit user choice > minimax if configured > hedra\n',
    '        if chosen_engine and chosen_engine in ("minimax", "video-01", "hailuo"):\n',
    '            target_anim_engine = "minimax"\n',
    '        elif chosen_engine and chosen_engine in ("hedra", "kling", "kling_avatar", "local_fallback"):\n',
    '            target_anim_engine = chosen_engine\n',
    '        elif is_minimax_configured():\n',
    '            target_anim_engine = "minimax"\n',
    '        elif hedra_key:\n',
    '            target_anim_engine = "hedra"\n',
    '        else:\n',
    '            target_anim_engine = "local_fallback"\n',
]

lines[idx_engine:idx_engine_end] = new_engine_lines
print("3. Patched Stage 7 Engine Selection")

# 4. Update Stage 7 Generation Loop (Prioritizing MiniMax Video-01 with motion_prompt)
idx_loop_start = next(i for i, l in enumerate(lines) if '# 1. Primary: Hedra AI Character Lip-Syncing' in l)
idx_loop_end = next(i for i, l in enumerate(lines) if '# 3. Dynamic Local Animated Actor Performance' in l)

new_stage7_loop_lines = [
    '            # 1. MiniMax Video-01 Dynamic Physical Motion & Natural Acting\n',
    '            if not success and (target_anim_engine in ("minimax", "hailuo", "video-01") or (not hedra_key and is_minimax_configured())):\n',
    '                try:\n',
    '                    from generators.minimax_client import generate_minimax_character_video\n',
    '                    self.p.activity(f"Stage 7/9: MiniMax Video-01 generating dynamic physical action for {s.speaker} (Scene {s.scene_id})...")\n',
    '                    cam_text = "Dramatic cinematic push-in shot." if s.camera_motion and "push" in s.camera_motion else ("Smooth camera pull-out shot." if s.camera_motion and "pull" in s.camera_motion else "Cinematic camera movement.")\n',
    '                    motion_p = getattr(s, "motion_prompt", "") or getattr(s, "action_prompt", "") or f"{s.speaker} delivering intense dialogue"\n',
    '                    act_prompt = f"{cam_text} {motion_p}, natural expressive facial acting and hand gestures, eye contact with camera, authentic breathing, cinematic dramatic lighting, vertical 9:16 video"\n',
    '                    meta = generate_minimax_character_video(portrait_path=portrait_file, prompt=act_prompt, output_mp4=out_clip, audio_path=audio_file, cancel_check=self.is_cancelled)\n',
    '                    success = True\n',
    '                    log.info("MiniMax Video-01 dynamic video succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)\n',
    '                except Exception as me:\n',
    '                    log.warning("MiniMax generation failed for scene %d (%s); falling back to lip-sync: %s", s.scene_id, me)\n',
    '\n',
    '            # 2. Hedra AI Character Lip-Syncing (Precision phoneme lip synchronization)\n',
    '            if not success and hedra_key and (target_anim_engine in ("hedra", "cloud") or target_anim_engine not in ("local_fallback", "kling_avatar")):\n',
    '                try:\n',
    '                    self.p.activity(f"Stage 7/9: Hedra rendering lip-synced video for {s.speaker} (Scene {s.scene_id})...")\n',
    '                    meta = generate_hedra_character_video(portrait_file, audio_file, out_clip, hedra_key, text_prompt=s.narration, cancel_check=self.is_cancelled)\n',
    '                    success = True\n',
    '                    log.info("Hedra lip-sync succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)\n',
    '                except Exception as he:\n',
    '                    log.warning("Hedra lip-sync failed for scene %d (%s); trying fallback: %s", s.scene_id, he)\n',
    '\n',
    '            # 3. Fal.ai Kling Avatar / SadTalker if Fal key configured\n',
    '            if not success and fal_key and "TOP_UP" not in str(meta):\n',
    '                try:\n',
    '                    self.p.activity(f"Stage 7/9: Fal.ai generating actor performance for {s.speaker} (Scene {s.scene_id})...")\n',
    '                    if target_anim_engine in ("kling", "kling_avatar"):\n',
    '                        meta = _generate_fal_kling_avatar(portrait_file, audio_file, out_clip, fal_key)\n',
    '                    else:\n',
    '                        meta = _generate_fal_sadtalker(portrait_file, audio_file, out_clip, fal_key)\n',
    '                    success = True\n',
    '                except Exception as fe:\n',
    '                    log.warning("Fal avatar generation failed for scene %d (%s); falling back...", s.scene_id, fe)\n',
    '\n',
]

lines[idx_loop_start:idx_loop_end] = new_stage7_loop_lines
print("4. Patched Stage 7 Generation Loop")

drama_p.write_text("".join(lines), encoding="utf-8")
print("Finished updating core/drama_pipeline.py successfully!")
