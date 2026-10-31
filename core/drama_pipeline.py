"""Short Drama Pipeline: 9:16 vertical drama production pipeline."""

from __future__ import annotations



import math

import os

import random

import re

import shutil

import time

from datetime import datetime

from pathlib import Path

from typing import Callable, Optional



from agents.drama_agent import plan_drama_production

from core.base_pipeline import BasePipeline, PipelineCancelled

from core.config import ROOT, get_secret, load_providers

from core.logging_setup import log

from core.models import STAGES, Asset, Scene, Status

from core.project_manager import Project, now

from core.versioning import record_stage_version

from generators.avatar_generator import _generate_fallback_talking_avatar, _generate_fal_kling_avatar, _generate_fal_sadtalker

from generators.character_manager import slugify_character

from generators.hedra_client import generate_hedra_character_video, get_hedra_key

from generators.minimax_client import is_minimax_configured, generate_minimax_character_video

from generators.subtitle_generator import build_cues, write_ass, write_srt

from generators.voice_generator import default_profile_name, load_profile, synthesize, list_profiles

from providers.images import ImageRequest, get_image_provider

from providers.llm import LLMClient

from providers.video import get_video_provider

from rendering.ffmpeg_renderer import project_timeline, render_project, run_ffmpeg

from rendering.transitions import total_length





def parse_drama_script_markdown(md_text: str) -> tuple[str, list[dict]]:

    """Parse short drama script markdown into title and structured dialogue shots."""

    title = ""

    sections = []

    shot_id = 1

    lines = md_text.splitlines()

    for line in lines:

        l = line.strip()

        if not l or l.startswith("##"):

            continue

        if l.startswith("# "):

            title = l[2:].strip()

            continue



        act = ""

        m_act = re.search(r'\*\((.*?)\)\*\s*$', l)

        if m_act:

            act = m_act.group(1).replace('鏡頭動作：', '').replace('鏡頭動作:', '').strip()

            l_no_act = l[:m_act.start()].strip()

        else:

            l_no_act = l



        # pattern 1: **[Speaker]**：dialogue

        m = re.match(r'^\*\*\[([^\]]+)\]\*\*[:：]\s*(.*)$', l_no_act)

        if not m:

            # pattern 2: [Speaker]：dialogue

            m = re.match(r'^\[([^\]]+)\][:：]\s*(.*)$', l_no_act)

        if not m:

            # pattern 3: **Speaker**：dialogue

            m = re.match(r'^\*\*([^\*]+)\*\*[:：]\s*(.*)$', l_no_act)

        if not m:

            # pattern 4: Speaker：dialogue

            m = re.match(r'^([^:：]{2,15})[:：]\s*(.*)$', l_no_act)



        if m:

            spk = m.group(1).strip()

            diag = m.group(2).strip()

            sections.append({

                "name": f"Shot {shot_id}",

                "speaker": spk,

                "dialogue": diag,

                "action": act,

                "text": f"{spk}：{diag}"

            })

            shot_id += 1

        elif l and not l.startswith("*"):

            sections.append({

                "name": f"Shot {shot_id}",

                "speaker": "旁白",

                "dialogue": l_no_act,

                "action": act,

                "text": l_no_act

            })

            shot_id += 1



    return title, sections





class DramaPipeline(BasePipeline):

    """Dedicated Pipeline for 9:16 Vertical Short Drama Videos."""



    # ---------------- Stage 1: Storyboard & Premise ----------------

    def _run_research(self) -> None:



        st = self.p.stage("research")



        if st.status == Status.COMPLETED and self.p.path("research", "research.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 1/9: Analyzing topic & researching...")



        self.p.set_stage("research", Status.RUNNING)



        cfg = self.p.settings



        res_prov = self.get_stage_model("research")



        user_research = cfg.get("user_research") or self.p.data.settings.get("user_research") or ""



        research_mode = cfg.get("research_mode") or self.p.data.settings.get("research_mode", "auto")







        enabled = bool(cfg.get("script", {}).get("research_enabled", False)) or (res_prov == "gemini_search")



        if user_research and research_mode == "user_only":



            enabled = False









        self.p.activity("Stage 1/9: Planning short drama concept & character turnaround roster...")



        from agents.drama_agent import plan_drama_production



        from providers.llm import LLMClient



        formula_key = cfg.get("drama_formula") or self.p.data.settings.get("drama_formula", "workplace_revenge")



        dur_sec = int(cfg.get("video", {}).get("duration_seconds", 50))



        aspect = cfg.get("aspect_ratio") or self.p.data.settings.get("aspect_ratio", "9:16")



        client = LLMClient("research", self._track_llm_request, json_retries=2, provider_override=res_prov)



        custom_chars = cfg.get("drama_characters") or self.p.data.settings.get("drama_characters")



        drama_pkg = plan_drama_production(



            topic=self.p.data.topic,



            formula_key=formula_key,



            duration_sec=dur_sec,



            aspect_ratio=aspect,



            user_premise=user_research if user_research.strip() else None,



            client=client,



            settings=cfg,



            custom_characters=custom_chars



        )



        self.p.write_json("research/drama_plan.json", drama_pkg)



        self.p.write_json("research/character_roster.json", drama_pkg.get("characters", []))



        self.p.write_json("research/research.json", {



            "summary": drama_pkg.get("tagline", ""),



            "key_facts": [c["name"] + ": " + c.get("role", "") for c in drama_pkg.get("characters", [])],



            "dramatic_beats": [s.get("dramatic_beat", "") + ": " + s.get("dialogue", "") for s in drama_pkg.get("shots", [])],



            "drama_plan": drama_pkg



        })



        bible_md = f"# AI Short Drama: {drama_pkg.get('title', self.p.data.topic)}\n\n**Tagline**: {drama_pkg.get('tagline', '')}\n\n## Character Roster (定妝表)\n"



        for ch in drama_pkg.get("characters", []):



            bible_md += f"- **{ch.get('name')}** ({ch.get('role', '')}): {ch.get('appearance', ch.get('appearance_prompt', ''))}\n"



        self.p.write_text("research/drama_bible.md", bible_md)



        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("research", Status.COMPLETED, done=1, total=1, duration_override=elapsed)



        log.info("Short drama planning complete for %s in %.1fs", self.p.id, elapsed)



        return



    # ---------------- Stage 2: Screenplay Dialogue ----------------

    def _run_script(self) -> None:



        st = self.p.stage("script")



        if st.status == Status.COMPLETED and self.p.path("script", "script.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 2/9: Generating narration script...")



        self.p.set_stage("script", Status.RUNNING)



        cfg = self.p.settings



        scr_prov = self.get_stage_model("script")



        res = self.p.read_json("research/research.json", {})



        partial = self.p.read_json("script/script.json", {})









        self.p.activity("Stage 2/9: Formatting screenplay dialogue & dramatic beats...")



        drama_pkg = self.p.read_json("research/drama_plan.json", {})



        shots = drama_pkg.get("shots", [])



        scr_text = f"# {drama_pkg.get('title', self.p.data.topic)}\n\n"



        sections = []



        for s in shots:



            spk = s.get("speaker", "旁白")



            diag = s.get("dialogue", "")



            act = s.get("action", "")



            scr_text += f"**[{spk}]**：{diag}  *(鏡頭動作：{act})*\n\n"



            sections.append({



                "name": f"Shot {s.get('shot_id')}",



                "text": f"{spk}：{diag}",



                "speaker": spk,



                "dialogue": diag,



                "action": act,



                "shot": s



            })



        scr_data = {



            "title": drama_pkg.get("title", self.p.data.topic),



            "sections": sections,



            "word_count": len(scr_text),



            "target_words": len(scr_text),



            "shots": shots



        }



        self.p.write_json("script/script.json", scr_data)



        self.p.path("script", "script.md").write_text(scr_text, encoding="utf-8")



        self.p.data.title = drama_pkg.get("title", self.p.data.topic)



        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("script", Status.COMPLETED, done=len(sections), total=len(sections), duration_override=elapsed)



        self.p.save()



        log.info("Drama screenplay complete: %d shots in %.1fs", len(shots), elapsed)



        return



    # ---------------- Stage 3: Scene & Cast Allocation ----------------

    def _run_scenes(self) -> None:

        st = self.p.stage("scenes")

        if st.status == Status.COMPLETED and self.p.path("scenes", "scenes.json").exists() and self.p.scenes:

            return

        if self._cancel_flag: raise PipelineCancelled()



        t0 = time.perf_counter()

        self.p.activity("Stage 3/9: Allocating screenplay dialogue into animated scenes...")

        self.p.set_stage("scenes", Status.RUNNING)

        cfg = self.p.settings



        # 1. Read script directly from Stage 2 (script.md & script.json)

        scr = self.p.read_json("script/script.json", {})

        script_md = self.p.read_text("script/script.md", "")



        script_sections = []

        if script_md.strip():

            _, parsed_sections = parse_drama_script_markdown(script_md)

            if parsed_sections:

                script_sections = parsed_sections

        if not script_sections:

            script_sections = scr.get("sections") or []



        if not script_sections:

            raise RuntimeError("Cannot plan drama scenes without screenplay script from Stage 2")



        # 2. Resolve characters & voice profiles

        drama_pkg = self.p.read_json("research/drama_plan.json", {})

        roster = (

            self.p.settings.get("drama_characters")

            or self.p.data.settings.get("drama_characters")

            or drama_pkg.get("characters", [])

            or self.p.read_json("research/character_roster.json", [])

            or []

        )



        from generators.voice_generator import list_profiles

        avail_voices = list_profiles()



        from generators.character_manager import slugify_character



        def _resolve_char(raw_spk: str, idx: int) -> dict:

            if not roster:

                return {"id": slugify_character(raw_spk), "name": raw_spk, "gender": "female", "voice_profile": "ichiehchieh"}

            for c in roster:

                if c.get("name") == raw_spk or c.get("id") == raw_spk:

                    return c

            for c in roster:

                cn = c.get("name", "")

                if cn and (cn in raw_spk or raw_spk in cn):

                    return c

            for c in roster:

                role = c.get("role", "")

                if role and (role in raw_spk or raw_spk in role):

                    return c

            # Semantic keyword matching: Chairman / Executive

            if any(k in raw_spk for k in ("董", "董事長", "長官", "老闆", "總裁", "集團", "老", "陳", "張")):

                for c in roster:

                    if any(k in c.get("name", "") or k in c.get("role", "") for k in ("董", "董事長", "老闆", "總裁")):

                        return c

            # Manager / Antagonist

            if any(k in raw_spk for k in ("經理", "主管", "組長", "王", "李")):

                for c in roster:

                    if any(k in c.get("name", "") or k in c.get("role", "") for k in ("經理", "主管", "組長")):

                        return c

            # Lead / Female

            if any(k in raw_spk for k in ("主", "女", "芸", "沈", "工程師", "架構師", "林", "妹")):

                for c in roster:

                    if any(k in c.get("name", "") or k in c.get("role", "") for k in ("女", "主", "架構師", "總監")):

                        return c

            return roster[idx % len(roster)]



        aspect = cfg.get("aspect_ratio") or self.p.data.settings.get("aspect_ratio", "9:16")

        aspect_tag = "vertical 9:16 composition" if aspect == "9:16" else "widescreen 16:9 composition"



        # 3. Create 1:1 Scene allocation for each dialogue line

        scenes = []

        for idx, sec in enumerate(script_sections):

            sid = idx + 1

            raw_spk = sec.get("speaker") or "主角"

            c_info = _resolve_char(raw_spk, idx)

            spk = c_info.get("name") or raw_spk

            char_id = c_info.get("id") or slugify_character(spk)



            # Extract clean dialogue text (strictly without repeated speaker prefix)

            full_narration = sec.get("dialogue") or sec.get("text") or ""

            if "：" in full_narration and full_narration.startswith(spk):

                full_narration = full_narration.split("：", 1)[1].strip()

            elif ":" in full_narration and full_narration.startswith(spk):

                full_narration = full_narration.split(":", 1)[1].strip()



            # Resolve distinct voice profile

            target_vp = c_info.get("voice_profile") or c_info.get("voice_provider")

            matched_v = None

            if target_vp:

                for v in avail_voices:

                    if v["name"] == target_vp or v.get("display_name") == target_vp:

                        matched_v = v["name"]

                        break

            if not matched_v:

                c_gender = str(c_info.get("gender", "female")).lower()

                c_age = int(c_info.get("age", 30))

                if c_gender == "female":

                    matched_v = "ichiehchieh"

                elif c_age >= 55 or any(k in spk for k in ("董", "老", "長官")):

                    matched_v = "aurora_mandarin"

                else:

                    matched_v = "mytsaovoicemagpie"



            char_app = c_info.get("appearance") or c_info.get("appearance_prompt") or ""

            act = sec.get("action") or f"{spk}情緒飽滿說出台詞"

            vis_desc = f"{char_app}, {act}, {aspect_tag}, cinematic vertical lighting, 8k drama still" if char_app else f"{act}, {aspect_tag}"



            is_climax = (idx >= len(script_sections) - 1)

            # Duration calculated from dialogue length (~3.2 chars/sec)

            per_scene_dur = max(3.5, round(len(full_narration) / 3.2, 1))



            scenes.append(Scene(

                scene_id=sid,

                section=sec.get("name") or f"Beat {sid}",

                speaker=raw_spk,

                character_id=char_id,

                narration=full_narration,

                action=act,

                estimated_duration=per_scene_dur,

                visual_type="talking_actor",

                visual_description=vis_desc,

                camera_motion="push_in_fast" if is_climax else ("push_in" if idx == 0 else "dolly_left"),

                transition="cut" if is_climax else "crossfade",

                dramatic_beat="climax" if is_climax else ("hook" if idx == 0 else "tension"),

                has_impact_hit=is_climax,

                voice_profile=matched_v,

                callout_text=None,

                callout_type=None,

            ))



        self.p.set_scenes(scenes)

        elapsed = round(max(0.1, time.perf_counter() - t0), 1)

        self.p.set_stage("scenes", Status.COMPLETED, done=len(scenes), total=len(scenes), duration_override=elapsed)

        log.info("Direct scenes complete: %d allocated animated scenes matching Stage 2 script dialogue lines in %.1fs", len(scenes), elapsed)

        return



    # ---------------- Stage 4: Actor Action & Framing Prompts ----------------

    def _run_prompts(self) -> None:



        st = self.p.stage("prompts")



        if st.status == Status.COMPLETED and self.p.path("prompts", "image_prompts.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 4/9: Creating image generation prompts...")



        self.p.set_stage("prompts", Status.RUNNING)



        cfg = self.p.settings



        scenes = self.p.scenes



        if not scenes:



            raise RuntimeError("No scenes available to prompt")









        self.p.activity("Stage 4/9: Creating character action, emotion & camera framing prompts...")



        drama_pkg = self.p.read_json("research/drama_plan.json", {})



        shots = drama_pkg.get("shots", [])



        roster = drama_pkg.get("characters", []) or self.p.read_json("research/character_roster.json", [])



        prompts_map = {}



        for i, s in enumerate(scenes):



            shot = shots[i] if i < len(shots) else {}



            from core.action_registry import assign_gesture_to_scene, get_gesture_by_tag
            spk = s.speaker or shot.get("speaker", "主角")
            c_info = next((c for c in roster if c.get("name") == spk or c.get("id") == spk or spk in c.get("name", "")), {})
            app = c_info.get("appearance") or c_info.get("appearance_prompt") or f"{spk}"

            # Action & Gesture Registry: Assign dynamic dramatic posture per scene
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
            prompts_map[s.tag] = prompt_str
            self.p.progress("prompts", i + 1, len(scenes))







        self.p.write_json("prompts/image_prompts.json", prompts_map)



        self.p.save_scenes()



        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("prompts", Status.COMPLETED, done=len(scenes), total=len(scenes), duration_override=elapsed)



        log.info("Drama action prompts generated: %d scenes in %.1fs", len(scenes), elapsed)



        return







    # ---------------- Stage 5: MiniMax Actor Dynamic Generation ----------------

    def _run_images(self) -> None:



        scenes = self.p.active_scenes()



        total = len(scenes)



        done = sum(1 for s in scenes if s.image.status == Status.COMPLETED and self.p.abs(s.image.path) and self.p.abs(s.image.path).exists())



        if done == total and total > 0:

            st = self.p.stage("images")

            if st.status != Status.COMPLETED:

                self.p.set_stage("images", Status.COMPLETED, done=total, total=total, duration_override=st.duration_seconds or None)

            return



        default_model = "minimax"

        t0 = time.perf_counter()



        prev_dur = self.p.stage("images").duration_seconds if done > 0 else 0.0



        self.p.set_stage("images", Status.RUNNING, done=done, total=total)



        cfg = self.p.settings



        img_cfg = cfg.get("images", {})



        fallback_name = img_cfg.get("fallback_provider", "placeholder")



        default_model = "minimax" 



        current_model_name = self.get_stage_model("images") or default_model







        provider = get_image_provider(current_model_name, self.p.settings)



        avail, reason = provider.available()



        if not avail:



            log.warning("Image provider '%s' unavailable (%s); using fallback '%s'", current_model_name, reason, fallback_name)



            current_model_name = fallback_name



            provider = get_image_provider(fallback_name, self.p.settings)







        width = int(cfg.get("video", {}).get("width") or 1080)

        height = int(cfg.get("video", {}).get("height") or 1920)

        steps = int(img_cfg.get("steps", 25))

        cfg_val = float(img_cfg.get("cfg", 6.5))

        retries = int(img_cfg.get("retries", 2))



        self.p.activity("Stage 5/9: Generating animated actor video based on character set...")



        roster = self.p.settings.get("drama_characters") or self.p.data.settings.get("drama_characters") or self.p.read_json("research/character_roster.json", []) or []



        from generators.character_manager import slugify_character



        from rendering.ffmpeg_utils import run_ffmpeg



        from generators.avatar_generator import _generate_fallback_talking_avatar







        # 1. Normalize all characters in roster with guaranteed slug IDs and persist uploaded images



        used_ids = set()



        p_cdir = self.p.path("characters")



        p_cdir.mkdir(parents=True, exist_ok=True)



        for idx, c in enumerate(roster):



            cid = (c.get("id") or "").strip()



            if not cid or cid == "None" or cid == "char":



                cid = slugify_character(c.get("name") or f"actor_{idx+1}")



            if cid in used_ids:



                cid = f"{cid}_{idx+1}"



            used_ids.add(cid)



            c["id"] = cid







            uri = c.get("image_data_uri") or ""



            if uri and uri.startswith("data:image"):



                import base64



                try:



                    _, b64 = uri.split(",", 1)



                    img_bytes = base64.b64decode(b64)



                    p_file = p_cdir / f"{cid}.png"



                    p_file.write_bytes(img_bytes)



                    char_dir = ROOT / "data" / "characters" / cid



                    char_dir.mkdir(parents=True, exist_ok=True)



                    (char_dir / "portrait.png").write_bytes(img_bytes)



                    c["image_filename"] = f"{cid}.png"



                    c["image_url"] = f"/api/characters/image/{cid}"



                except Exception as de:



                    log.warning("Could not decode image_data_uri for %s: %s", cid, de)







        try:



            self.p.write_json("research/character_roster.json", roster)



            self.p.data.settings["drama_characters"] = roster



        except Exception:



            pass







        cached_portraits = {}



        fps = int(cfg.get("video", {}).get("fps", 30))







        for s in scenes:



            if self._cancel_flag: raise PipelineCancelled()



            img_path = self.p.path("images", f"{s.tag}.png")



            vid_path = self.p.path("images", f"{s.tag}.mp4")







            spk = s.speaker or "主角"



            c_info = None



            for c in roster:



                if c.get("name") == spk or c.get("id") == spk or (c.get("name") and (c.get("name") in spk or spk in c.get("name"))):



                    c_info = c



                    break



            if not c_info and getattr(s, "character_id", None):



                for c in roster:



                    if c.get("id") == s.character_id:



                        c_info = c



                        break



            if not c_info and roster:



                c_info = roster[(s.scene_id - 1) % len(roster)]







            char_id = (c_info or {}).get("id") or slugify_character(spk)



            s.character_id = char_id



            if c_info and c_info.get("name"):



                s.speaker = c_info["name"]



            if c_info and (c_info.get("voice_profile") or c_info.get("voice_provider")):



                s.voice_profile = c_info.get("voice_profile") or c_info.get("voice_provider")







            # Check canonical portrait for this specific character



            portrait_cand = None



            if char_id in cached_portraits and cached_portraits[char_id].exists():



                portrait_cand = cached_portraits[char_id]



            else:



                # 1. Project characters folder



                for cand in (self.p.path("characters", f"{char_id}.png"), self.p.path("characters", f"{char_id}.jpg")):



                    if cand.exists() and cand.stat().st_size > 1000:



                        portrait_cand = cand



                        break







                # 2. Character info image_data_uri fallback



                if not portrait_cand or not portrait_cand.exists():



                    uri = (c_info or {}).get("image_data_uri") or ""



                    if uri and uri.startswith("data:image"):



                        import base64



                        try:



                            _, b64 = uri.split(",", 1)



                            img_bytes = base64.b64decode(b64)



                            p_saved = self.p.path("characters", f"{char_id}.png")



                            p_saved.parent.mkdir(parents=True, exist_ok=True)



                            p_saved.write_bytes(img_bytes)



                            char_dir = ROOT / "data" / "characters" / char_id



                            char_dir.mkdir(parents=True, exist_ok=True)



                            (char_dir / "portrait.png").write_bytes(img_bytes)



                            portrait_cand = p_saved



                            log.info("Decoded uploaded character photo for %s (%d bytes)", char_id, len(img_bytes))



                        except Exception as de:



                            log.warning("Could not decode image_data_uri for %s: %s", char_id, de)







                # 3. Global characters library



                if not portrait_cand or not portrait_cand.exists():



                    for cand in (ROOT / "data" / "characters" / char_id / "portrait.png", ROOT / "data" / "characters" / char_id / "portrait.jpg"):



                        if cand.exists() and cand.stat().st_size > 1000:



                            portrait_cand = cand



                            break







                # 4. Known keyword presets



                if not portrait_cand or not portrait_cand.exists():



                    spk_slug = slugify_character(spk)



                    for cand in (



                        ROOT / "data" / "characters" / spk_slug / "portrait.png",



                        ROOT / "data" / "characters" / spk_slug / "portrait.jpg",



                        self.p.path("characters", f"{spk_slug}.png")



                    ):



                        if cand.exists() and cand.stat().st_size > 1000:



                            portrait_cand = cand



                            break







                if portrait_cand and portrait_cand.exists():



                    cached_portraits[char_id] = portrait_cand







            if portrait_cand and portrait_cand.exists():



                img_path.parent.mkdir(parents=True, exist_ok=True)



                styled_char_path = self.p.path("characters", f"{char_id}_styled_9x16.png")
                from generators.face_reference_generator import generate_face_referenced_portrait
                clothes_p = "sharp corporate navy blue executive suit and necktie with rimless gold glasses" if ("經理" in spk or "manager" in spk.lower()) else ("bespoke charcoal tailored wool overcoat" if ("陳董" in spk or "董" in spk) else "stylish contemporary professional attire")
                bg_p = "modern luxury executive high-rise corporate corner office with glass desk and city skyline view"
                act_p = getattr(s, "action_prompt", "") or getattr(s, "action", "")

                # 1. Synthesize canonical anchor portrait once per character if not yet cached
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
                    g_name = getattr(s, 'action_gesture', 'pose')
                    self.p.activity(f"Stage 5/9: Anchoring {spk} face & attire with action [{g_name}] (Scene {s.scene_id})...")
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
                        cached_portraits[char_id] = styled_char_path
                    log.info("Anchor copy applied for Scene %d (%s)", s.scene_id, s.speaker)
            else:



                # Generate canonical portrait for this character



                raw_prompt = s.prompt or s.visual_description or ((c_info or {}).get("appearance") or f"East Asian character {spk}")



                raw_prompt += ", vertical portrait, 9:16, cinematic character still, 8k photorealistic"



                self.p.activity(f"Stage 5/9: Generating canonical actor portrait for {spk}...")



                img_generated = False



                try:



                    req = ImageRequest(



                        prompt=raw_prompt,



                        negative="blurry, deformed, cartoon, low quality, watermark",



                        seed=s.scene_id + 42,



                        width=width,



                        height=height,



                        steps=steps,



                        cfg=cfg_val,



                        output=img_path,



                    )



                    res = provider.generate(req)



                    cached_portraits[char_id] = img_path



                    img_generated = True



                except Exception as ge:



                    log.warning("Actor portrait generation failed (%s); generating stylized 9:16 fallback portrait", ge)







                if not img_generated or not img_path.exists() or img_path.stat().st_size < 1000:



                    from PIL import Image, ImageDraw



                    img = Image.new("RGB", (width, height), color=(15, 23, 42))



                    draw = ImageDraw.Draw(img)



                    for y in range(height):



                        r = int(12 + 18 * (1 - y/height))



                        g = int(18 + 22 * (y/height))



                        b = int(38 + 42 * (y/height))



                        draw.line([(0, y), (width, y)], fill=(r, g, b))



                    cx, cy = width // 2, height // 3



                    rad = width // 4



                    draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(30, 41, 59), outline=(245, 158, 11), width=4)



                    draw.text((cx, cy), spk[0] if spk else "🎭", fill=(245, 158, 11), anchor="mm")



                    img.save(img_path)



                    cached_portraits[char_id] = img_path







            # In Stage 5, synthesize the animated actor video from the character portrait + action



            self.p.activity(f"Stage 5/9: Generating animated actor video clip for Scene {s.scene_id} ({spk})...")



            actor_dur = float(s.estimated_duration or 6.0)



            minimax_success = False



            stage_img_model = (self.get_stage_model("images") or "minimax").lower()



            use_minimax = True







            if use_minimax:



                from generators.minimax_client import is_minimax_configured, generate_minimax_character_video



                if is_minimax_configured():



                    try:



                        self.p.activity(f"Stage 5/9: MiniMax generating dynamic scene video for Scene {s.scene_id} ({spk})...")



                        cam_text = "Dramatic cinematic push-in shot." if s.camera_motion and "push" in s.camera_motion else ("Smooth camera pull-out shot." if s.camera_motion and "pull" in s.camera_motion else "Cinematic dynamic camera.")



                        raw_action = s.visual_description or s.prompt or ""



                        desc_parts = [p.strip() for p in raw_action.split(",") if p.strip() and not any(tag in p.lower() for tag in ("8k", "resolution", "photorealistic", "vertical portrait", "9:16"))]



                        core_action = ", ".join(desc_parts[:4]) if desc_parts else f"{spk} speaking and performing"



                        act_prompt = f"{cam_text} {core_action}, highly expressive authentic performance, natural body movement, dramatic cinematic lighting, 9:16 vertical video"







                        audio_file = self.p.abs(s.audio.path) if (s.audio and s.audio.path and self.p.abs(s.audio.path).exists()) else None



                        portrait_source = img_path if (img_path and img_path.exists()) else (portrait_cand if (portrait_cand and portrait_cand.exists()) else img_path)







                        meta = generate_minimax_character_video(



                            portrait_path=portrait_source,



                            prompt=act_prompt,



                            output_mp4=vid_path,



                            audio_path=audio_file,



                            cancel_check=self.is_cancelled



                        )



                        if vid_path.exists() and vid_path.stat().st_size > 1000:



                            minimax_success = True



                            log.info("Stage 5: Scene %d successfully generated via MiniMax (%s)", s.scene_id, vid_path)



                            base_anim = self.p.path("animation", f"{s.tag}_base.mp4")



                            base_anim.parent.mkdir(parents=True, exist_ok=True)



                            import shutil



                            shutil.copy2(str(vid_path), str(base_anim))







                            if hasattr(s, "animation"):



                                s.animation.status = Status.COMPLETED



                                s.animation.path = self.p.rel(vid_path)



                                s.animation.meta = meta







                            try:



                                run_ffmpeg(["-ss", "0.5", "-i", str(vid_path), "-vframes", "1", "-y", str(img_path)])



                            except Exception:



                                pass







                            s.image.status = Status.COMPLETED



                            s.image.path = self.p.rel(img_path)



                            s.image.meta = {



                                "provider": "minimax_video_01",



                                "character": spk,



                                "video_clip": self.p.rel(vid_path),



                                "minimax_task_id": meta.get("task_id"),



                                "active_take": 1,



                                "takes": [self.p.rel(img_path)]



                            }



                            self.p.save_scenes()



                            self.p.progress("images", s.scene_id, total)



                    except Exception as me:



                        log.warning("Stage 5 MiniMax generation failed for Scene %d: %s; falling back to organic camera motion", s.scene_id, me)







            if not minimax_success:



                # Generate realistic animated actor video with organic living breathing motion and camera dynamic



                # on / 90 gives a smooth 3-second (at 30fps) natural respiration cycle



                zoom_expr = "'1.02+0.02*sin(6.283*on/90)'"



                y_expr = "'ih/2-(ih/zoom/2)+(ih*0.008)*sin(6.283*on/90)'"



                x_expr = "'iw/2-(iw/zoom/2)'"



                if s.camera_motion in ("push_in", "push_in_fast"):



                    zoom_expr = f"'1.02+0.04*(on/{max(30, int(actor_dur*fps))})+0.01*sin(6.283*on/90)'"



                elif s.camera_motion in ("pull_out", "pull_out_fast"):



                    zoom_expr = f"'1.06-0.04*(on/{max(30, int(actor_dur*fps))})+0.01*sin(6.283*on/90)'"







                vf_pan = (



                    f"scale={width}:{height}:force_original_aspect_ratio=increase,"



                    f"crop={width}:{height},"



                    f"zoompan=z={zoom_expr}:d={int(actor_dur*fps)}:x={x_expr}:y={y_expr}:s={width}x{height}:fps={fps},"



                    f"setsar=1,format=yuv420p"



                )



                try:



                    run_ffmpeg([



                        "-loop", "1",



                        "-i", str(img_path),



                        "-vf", vf_pan,



                        "-t", f"{actor_dur:.3f}",



                        "-c:v", "libx264",



                        "-preset", "veryfast",



                        "-crf", "19",



                        "-pix_fmt", "yuv420p",



                        "-y",



                        str(vid_path),



                    ])



                    base_anim = self.p.path("animation", f"{s.tag}_base.mp4")



                    base_anim.parent.mkdir(parents=True, exist_ok=True)



                    if vid_path.exists():



                        import shutil



                        shutil.copy2(str(vid_path), str(base_anim))



                except Exception as ve:



                    log.warning("Stage 5 video gen note: %s", ve)







                s.image.status = Status.COMPLETED



                s.image.path = self.p.rel(img_path)



                s.image.meta = {"provider": "character_actor_video", "character": spk, "video_clip": self.p.rel(vid_path) if vid_path.exists() else None}



                self.p.save_scenes()



                self.p.progress("images", s.scene_id, total)







        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("images", Status.COMPLETED, done=total, total=total, duration_override=elapsed)



        log.info("Drama video generation complete: %d actor video scenes in %.1fs", total, elapsed)



        return



    # ---------------- Stage 6: Multi-Character Voiceover ----------------

    def _run_voice(self) -> None:



        scenes = self.p.active_scenes()



        total = len(scenes)



        done = sum(1 for s in scenes if s.audio.status == Status.COMPLETED and self.p.abs(s.audio.path) and self.p.abs(s.audio.path).exists())







        if done == total and total > 0:



            st = self.p.stage("voice")



            if st.status != Status.COMPLETED:



                self.p.set_stage("voice", Status.COMPLETED, done=total, total=total, duration_override=st.duration_seconds or None)



            return







        t0 = time.perf_counter()



        prev_dur = self.p.stage("voice").duration_seconds if done > 0 else 0.0



        self.p.set_stage("voice", Status.RUNNING, done=done, total=total)



        cfg = self.p.settings







        stage_provider = self.get_stage_model("voice") or cfg.get("voice", {}).get("provider", "bluemagpie")







        # Resolve project-level voice profile (timbre / reference audio)



        default_p_name = self.p.data.settings.get("voice_profile")



        PROVIDER_NAMES = ("bluemagpie", "cosyvoice", "cozyvoice", "http_clone", "elevenlabs", "voai", "edge", "sapi", "openai_tts")



        from generators.voice_generator import list_profiles



        all_vps = list_profiles()



        vp_names = [vp["name"] for vp in all_vps]







        if not default_p_name or default_p_name in PROVIDER_NAMES or default_p_name not in vp_names:



            if stage_provider in ("cosyvoice", "cozyvoice"):



                for vp in all_vps:



                    if vp.get("provider") in ("cosyvoice", "cozyvoice"):



                        default_p_name = vp["name"]



                        break



            elif stage_provider == "http_clone":



                for vp in all_vps:



                    if vp.get("provider") == "http_clone":



                        default_p_name = vp["name"]



                        break



            elif stage_provider == "bluemagpie":



                for vp in all_vps:



                    if vp.get("provider") == "bluemagpie":



                        default_p_name = vp["name"]



                        break



            elif stage_provider == "elevenlabs":



                for vp in all_vps:



                    if vp.get("provider") == "elevenlabs" and (vp.get("voice_id") or vp.get("voice")):



                        default_p_name = vp["name"]



                        break



            elif stage_provider == "voai":



                for vp in all_vps:



                    if vp.get("provider") == "voai":



                        default_p_name = vp["name"]



                        break







            if not default_p_name or default_p_name in PROVIDER_NAMES or default_p_name not in vp_names:



                lang = self.p.data.settings.get("video", {}).get("language", "")



                if "chinese" in lang.lower() or "taiwan" in lang.lower() or "trad" in lang.lower():



                    for vp in all_vps:



                        if "chinese" in vp.get("language", "").lower() or "tw" in vp.get("language", "").lower() or vp.get("reference_wav"):



                            default_p_name = vp["name"]



                            break



            if not default_p_name or default_p_name in PROVIDER_NAMES or default_p_name not in vp_names:



                default_p_name = default_profile_name(cfg)







        try:



            for s in scenes:



                if self._cancel_flag: raise PipelineCancelled()



                audio_path = self.p.path("audio", f"{s.tag}.wav")







                if s.audio.status == Status.COMPLETED and audio_path.exists() and audio_path.stat().st_size > 1000 and not (s.audio.meta or {}).get("text_outdated"):



                    continue







                # Dynamic check: did the user switch the voice model between scenes?



                scene_p_name = s.voice_profile or default_p_name



                # Only fall back to avatar profile's voice if neither the scene nor project has a configured voice profile



                if not s.voice_profile and not self.p.data.settings.get("voice_profile") and (getattr(s, "is_presenter", False) or s.visual_type == "talking_head"):



                    av_name = getattr(s, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar")



                    if av_name:



                        try:



                            from generators.avatar_generator import load_avatar



                            av_obj = load_avatar(av_name)



                            if av_obj and av_obj.get("voice_profile"):



                                scene_p_name = av_obj["voice_profile"]



                        except Exception:



                            pass



                if scene_p_name in PROVIDER_NAMES or scene_p_name not in vp_names:



                    scene_p_name = default_p_name



                scene_profile = load_profile(scene_p_name)



                # Ensure provider is aligned with the voice profile's configured provider



                prof_prov = scene_profile.get("provider")



                current_provider = prof_prov or stage_provider or "bluemagpie"



                if prof_prov:



                    self._stage_models_override["voice"] = prof_prov



                    self.p.data.settings.setdefault("stage_models", {})["voice"] = prof_prov



                    self.p.settings.setdefault("stage_models", {})["voice"] = prof_prov







                self.p.activity(f"Stage 6/9: Generating voice {s.scene_id}/{total} ({scene_p_name} / {current_provider})...")



                s.audio.status = Status.RUNNING



                self.p.save_scenes()







                existing_audio_meta = dict(s.audio.meta or {})



                prev_audio_takes = list(existing_audio_meta.get("takes", []))







                try:



                    meta = synthesize(s.narration, scene_profile, audio_path, cfg, provider_override=current_provider)



                    merged_audio_meta = dict(existing_audio_meta)



                    merged_audio_meta.update(meta)



                    merged_audio_meta["voice"] = scene_p_name



                    merged_audio_meta["provider"] = meta.get("provider", current_provider)



                    merged_audio_meta["takes"] = prev_audio_takes



                    s.audio.status = Status.COMPLETED



                    s.audio.path = self.p.rel(audio_path)



                    s.audio.meta = merged_audio_meta



                    s.audio_duration = meta.get("duration", 0.0)



                    s.audio.error = None



                    try:



                        from core.versioning import record_scene_voice_take



                        record_scene_voice_take(self.p, s.scene_id, s.audio.path, scene_p_name)



                    except Exception as vt_err:



                        log.debug("Voice take record note: %s", vt_err)







                    if meta.get("is_cloud"):



                        chars = int(meta.get("cloud_chars", len(s.narration)))



                        with self.p.lock:



                            self.p.data.usage.tts_cloud_chars += chars



                            rate = float(load_providers().get("pricing", {}).get("tts_cloud_per_1k_chars_usd", 0.0)) / 1000.0



                            self.p.data.usage.estimated_cost_usd += chars * rate



                            self.p.save()



                except Exception as e:



                    log.error("TTS failed for scene %d: %s", s.scene_id, e)



                    s.audio.status = Status.FAILED



                    s.audio.error = str(e)



                    self.p.save_scenes()



                    raise RuntimeError(f"Voice generation failed on scene {s.scene_id}: {e}")







                self.p.save_scenes()



                done = sum(1 for sc in scenes if sc.audio.status == Status.COMPLETED)



                self.p.progress("voice", done, total)







            elapsed = round(prev_dur + max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("voice", Status.COMPLETED, done=total, total=total, duration_override=elapsed)



            log.info("Voice generation complete: %d clips in %.1fs", total, elapsed)



        except Exception as e:



            with self.p.lock:



                self.p.stage("voice").duration_seconds = round(prev_dur + max(0.0, time.perf_counter() - t0), 1)



            if not isinstance(e, PipelineCancelled):



                self.p.set_stage("voice", Status.FAILED, error=str(e))



            raise







    # ---------------- Stage 7: Animation & Video Clips ----------------





    # ---------------- Stage 7: Lip-Sync & Face Dynamics ----------------

    def _run_animation(self) -> None:



        t0 = time.perf_counter()



        scenes = self.p.active_scenes()



        self.p.set_stage("animation", Status.RUNNING, done=0, total=len(scenes))



        cfg = self.p.settings



        pct = float(self.p.data.settings.get("ai_video_percentage", cfg.get("animation", {}).get("ai_video_percentage", 10)))



        cloud_enabled = bool(cfg.get("cloud", {}).get("enabled", False))



        max_clips = int(cfg.get("cloud", {}).get("max_video_clips", 8))









        self.p.activity("Stage 7/9: Lip-syncing actor video with dialogue audio line...")



        from generators.avatar_generator import _generate_fallback_talking_avatar, _generate_fal_kling_avatar, _generate_fal_sadtalker



        from generators.hedra_client import generate_hedra_character_video, get_hedra_key







        hedra_key = get_hedra_key()



        fal_key = get_secret("FAL_KEY") or get_secret("FAL_API_KEY") or ""



        from generators.minimax_client import is_minimax_configured
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
            target_anim_engine = "local_fallback"







        w = int(cfg.get("video", {}).get("width", 1080))



        h = int(cfg.get("video", {}).get("height", 1920))



        fps = int(cfg.get("video", {}).get("fps", 30))







        for i, s in enumerate(scenes):



            if self._cancel_flag: raise PipelineCancelled()



            out_clip = self.p.path("animation", f"{s.tag}.mp4")







            # Resolve portrait image for this specific scene.
            # CRITICAL: Stage 7 must use the exact styled visual created in Stage 5, NEVER falling back to raw unstyled uploads!
            portrait_file = None

            # 1. Primary: Scene-specific visual created in Stage 5 (image or video frame)
            stage5_img = self.p.abs(s.image.path) if (s.image and s.image.path) else self.p.path("images", f"{s.tag}.png")
            stage5_vid = self.p.path("images", f"{s.tag}.mp4")

            if stage5_img and stage5_img.exists() and stage5_img.stat().st_size > 1000:
                portrait_file = stage5_img
            elif stage5_vid and stage5_vid.exists() and stage5_vid.stat().st_size > 1000:
                # Extract frame 0 from Stage 5 MiniMax video to ensure exact visual identity
                frame_target = self.p.path("images", f"{s.tag}.png")
                try:
                    from rendering.ffmpeg_utils import run_ffmpeg
                    run_ffmpeg(["-ss", "0.0", "-i", str(stage5_vid), "-vframes", "1", "-y", str(frame_target)])
                    if frame_target.exists() and frame_target.stat().st_size > 1000:
                        portrait_file = frame_target
                except Exception as ef:
                    log.warning("Failed to extract frame from Stage 5 video %s: %s", stage5_vid, ef)

            # 2. Secondary: Styled 9:16 portrait synthesized for this character
            if not portrait_file:
                styled_cands = []
                if getattr(s, "character_id", None):
                    styled_cands.extend([
                        self.p.path("characters", f"{s.character_id}_styled_9x16.png"),
                        self.p.path("characters", f"{s.character_id}_styled_9x16.jpg"),
                    ])
                if getattr(s, "speaker", None):
                    from generators.character_manager import slugify_character
                    spk_slug = slugify_character(s.speaker)
                    styled_cands.extend([
                        self.p.path("characters", f"{spk_slug}_styled_9x16.png"),
                        self.p.path("characters", f"{spk_slug}_styled_9x16.jpg"),
                    ])
                for cand in styled_cands:
                    if cand.exists() and cand.stat().st_size > 1000:
                        portrait_file = cand
                        break

            # 3. Tertiary: Fall back to raw uploaded character photo only if no Stage 5 asset exists
            if not portrait_file:
                raw_cands = []
                if getattr(s, "character_id", None):
                    raw_cands.extend([
                        self.p.path("characters", f"{s.character_id}.png"),
                        self.p.path("characters", f"{s.character_id}.jpg"),
                        ROOT / "data" / "characters" / s.character_id / "portrait.png",
                        ROOT / "data" / "characters" / s.character_id / "portrait.jpg",
                    ])
                if getattr(s, "speaker", None):
                    from generators.character_manager import slugify_character
                    spk_slug = slugify_character(s.speaker)
                    raw_cands.extend([
                        self.p.path("characters", f"{spk_slug}.png"),
                        self.p.path("characters", f"{spk_slug}.jpg"),
                        ROOT / "data" / "characters" / spk_slug / "portrait.png",
                        ROOT / "data" / "characters" / spk_slug / "portrait.jpg",
                    ])
                for cand in raw_cands:
                    if cand.exists() and cand.stat().st_size > 1000:
                        portrait_file = cand
                        break

            audio_file = self.p.abs(s.audio.path) if (s.audio and s.audio.path) else self.p.path("audio", f"{s.tag}.wav")

            meta_prov = str((s.animation.meta or {}).get("provider", ""))
            prov_matches = (target_anim_engine in meta_prov) or ("hedra" in target_anim_engine and "hedra" in meta_prov)
            recorded_portrait = (s.animation.meta or {}).get("portrait_file")
            portrait_matches = bool(recorded_portrait and recorded_portrait == str(portrait_file))
            if s.animation.status == Status.COMPLETED and out_clip.exists() and out_clip.stat().st_size > 1000 and prov_matches and portrait_matches:



                p_mtime = portrait_file.stat().st_mtime if (portrait_file and portrait_file.exists()) else 0



                a_mtime = audio_file.stat().st_mtime if (audio_file and audio_file.exists()) else 0



                if out_clip.stat().st_mtime >= max(p_mtime, a_mtime):



                    continue







            self.p.activity(f"Stage 7/9: Generating AI actor performance for Scene {s.scene_id}/{len(scenes)} ({s.speaker})...")



            s.animation.status = Status.RUNNING



            self.p.save_scenes()







            meta = {}



            success = False







            # 1. MiniMax Video-01 Dynamic Physical Motion & Natural Acting
            if not success and (target_anim_engine in ("minimax", "hailuo", "video-01") or (not hedra_key and is_minimax_configured())):
                try:
                    from generators.minimax_client import generate_minimax_character_video
                    self.p.activity(f"Stage 7/9: MiniMax Video-01 generating dynamic physical action for {s.speaker} (Scene {s.scene_id})...")
                    cam_text = "Dramatic cinematic push-in shot." if s.camera_motion and "push" in s.camera_motion else ("Smooth camera pull-out shot." if s.camera_motion and "pull" in s.camera_motion else "Cinematic camera movement.")
                    motion_p = getattr(s, "motion_prompt", "") or getattr(s, "action_prompt", "") or f"{s.speaker} delivering intense dialogue"
                    act_prompt = f"{cam_text} {motion_p}, natural expressive facial acting and hand gestures, eye contact with camera, authentic breathing, cinematic dramatic lighting, vertical 9:16 video"
                    meta = generate_minimax_character_video(portrait_path=portrait_file, prompt=act_prompt, output_mp4=out_clip, audio_path=audio_file, cancel_check=self.is_cancelled)
                    success = True
                    log.info("MiniMax Video-01 dynamic video succeeded for Scene %d (%s): %s", s.scene_id, s.speaker, out_clip)
                except Exception as me:
                    log.warning("MiniMax generation failed for scene %d (%s); falling back to lip-sync: %s", s.scene_id, me)

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
                    log.warning("Fal avatar generation failed for scene %d (%s); falling back...", s.scene_id, fe)

            # 3. Dynamic Local Animated Actor Performance (Guaranteed $0, 0 error fallback)



            if not success or not out_clip.exists():



                self.p.activity(f"Stage 7/9: Generating dynamic actor motion for Scene {s.scene_id} ({s.speaker})...")



                meta = _generate_fallback_talking_avatar(portrait_file, audio_file, out_clip, width=w, height=h, fps=fps)



                success = True







            s.animation.status = Status.COMPLETED



            s.animation.path = self.p.rel(out_clip)



            if not isinstance(meta, dict):
                meta = {'raw': str(meta)}
            meta['portrait_file'] = str(portrait_file) if portrait_file else ''
            s.animation.meta = meta



            s.animation.error = None



            s.ai_video = True



            self.p.save_scenes()



            self.p.progress("animation", i + 1, len(scenes))







        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("animation", Status.COMPLETED, done=len(scenes), total=len(scenes), duration_override=elapsed)



        log.info("Drama animation stage complete: %d actor video clips in %.1fs", len(scenes), elapsed)



        return



    # ---------------- Stage 8: Vertical Dynamic Subtitles ----------------

    def _run_subtitles(self) -> None:



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 8/9: Building subtitles...")



        self.p.set_stage("subtitles", Status.RUNNING)



        cfg = self.p.settings



        sub_cfg = cfg.get("subtitles", {})







        scenes, slots = project_timeline(self.p)



        pairs = [(sc.narration, sl) for sc, sl in zip(scenes, slots)]







        cues = build_cues(



            pairs,



            max_chars_per_line=int(sub_cfg.get("max_chars_per_line", 42)),



            max_lines=int(sub_cfg.get("max_lines", 2)),
            frame_width=int(cfg["video"]["width"]),
            frame_height=int(cfg["video"]["height"]),
            style=sub_cfg.get("style", "youtube_standard"),
        )







        srt_file = self.p.path("subtitles", "subtitles.srt")



        ass_file = self.p.path("subtitles", "subtitles.ass")



        write_srt(cues, srt_file)







        # Check if fOx Hsiao style motion graphics callouts are enabled (toggleable)



        # Motion graphics callouts strictly disabled for short drama videos

        enabled_motion_callouts = False

        callouts = None

        if enabled_motion_callouts:

            from generators.motion_callout_generator import extract_motion_callouts

            callouts = extract_motion_callouts(scenes, slots)



        write_ass(



            cues, ass_file,



            style=sub_cfg.get("style", "youtube_standard"),



            width=int(cfg["video"]["width"]),



            height=int(cfg["video"]["height"]),



            callouts=callouts,



            font_override=sub_cfg.get("font"),



            ai_watermark=bool(sub_cfg.get("ai_watermark", True)),



        )







        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        callouts_info = f" with {len(callouts)} motion graphic cards" if callouts else " (motion callouts disabled)"



        self.p.set_stage("subtitles", Status.COMPLETED, done=len(cues), total=len(cues), duration_override=elapsed)



        log.info("Subtitles generated in %.1fs: %d dialogue cues%s", elapsed, len(cues), callouts_info)







    # ---------------- Stage 9: Final Render ----------------





    # ---------------- Stage 9: 9:16 Drama Master Render ----------------

    def _run_render(self) -> None:



        if self._cancel_flag: raise PipelineCancelled()



        t0 = time.perf_counter()



        self.p.activity("Stage 9/9: Assembling final video with FFmpeg...")



        self.p.set_stage("render", Status.RUNNING)







        def on_prog(done, total, msg):



            self.p.activity(f"Rendering: {msg} ({done}/{total})")



            self.p.progress("render", done, total)







        try:



            render_model = self.get_stage_model("render")



            if render_model:



                self.p.settings.setdefault("rendering", {})["encoder"] = render_model



            mp4_path = render_project(self.p, draft=False, progress=on_prog, cancel=self.is_cancelled)



            self.p.data.outputs["final"] = self.p.rel(mp4_path)



            try:



                thumb_file = self.p.path("output", "thumbnail.png")



                if not thumb_file.exists():



                    from generators.thumbnail_generator import render_project_thumbnail



                    render_project_thumbnail(self.p)



            except Exception as th_err:



                log.warning("Auto thumbnail generation skipped: %s", th_err)



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("render", Status.COMPLETED, done=1, total=1, duration_override=elapsed)



            log.info("Final video rendered in %.1fs: %s", elapsed, mp4_path)



        except Exception as e:



            if self._cancel_flag or "cancelled" in str(e).lower():



                self.p.set_stage("render", Status.PENDING)



                raise PipelineCancelled()



            self.p.set_stage("render", Status.FAILED, error=str(e))



            raise



