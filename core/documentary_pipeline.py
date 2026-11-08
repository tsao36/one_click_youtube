"""Documentary Pipeline: 16:9 documentary production pipeline."""

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



from agents.animation_selector import select_for_animation

from agents.prompt_generator import generate_prompts, project_style

from agents.researcher import research

from agents.scene_planner import direct_scenes, segment, visual_bible

from agents.script_writer import script_markdown, write_script

from agents.prompts_common import merge_negative_prompts, UNIVERSAL_QUALITY_NEGATIVE
from core.base_pipeline import BasePipeline, PipelineCancelled, apply_presenter_placement

from core.config import ROOT, get_secret, load_providers

from core.logging_setup import log

from core.models import STAGES, Asset, Scene, Status

from core.project_manager import Project, now

from core.versioning import record_stage_version

from generators.voice_generator import default_profile_name, load_profile, synthesize, list_profiles

from providers.images import ImageRequest, get_image_provider

from providers.video import get_video_provider

from rendering.ffmpeg_renderer import project_timeline

from rendering.transitions import total_length





class DocumentaryPipeline(BasePipeline):

    """Dedicated Pipeline for 16:9 Widescreen Documentary Videos."""



    # ---------------- Stage 1: Research ----------------

    def _run_research(self) -> None:



        st = self.p.stage("research")



        if st.status == Status.COMPLETED and self.p.path("research", "research.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 1/10: Analyzing topic & researching...")



        self.p.set_stage("research", Status.RUNNING)



        cfg = self.p.settings



        res_prov = self.get_stage_model("research")



        user_research = cfg.get("user_research") or self.p.data.settings.get("user_research") or ""



        research_mode = cfg.get("research_mode") or self.p.data.settings.get("research_mode", "auto")







        enabled = bool(cfg.get("script", {}).get("research_enabled", False)) or (res_prov == "gemini_search")



        if user_research and research_mode == "user_only":



            enabled = False







        lang = cfg.get("video", {}).get("language", "Traditional Chinese")



        dur_mins = float(cfg.get("video", {}).get("duration_minutes", 5.0))



        # Smart World Setting Preservation: check if user previously customized world_setting
        existing_res = self.p.read_json("research/research.json", {})
        existing_ws = existing_res.get("world_setting") if isinstance(existing_res, dict) else None
        has_custom_ws = bool(
            existing_ws and any([
                existing_ws.get("temporal_era", "").strip() not in ("", "Contemporary"),
                existing_ws.get("environment_reality", "").strip() not in ("", "Realistic authentic environment"),
                existing_ws.get("key_settings", "").strip(),
                existing_ws.get("ensemble_specs", "").strip(),
                existing_ws.get("negative_anachronisms"),
            ])
        )

        try:



            res = research(



                self.p.data.topic,



                lang,



                enabled,



                self._track_llm_request,



                duration_minutes=dur_mins,



                provider_override=res_prov,



                user_research=user_research if user_research.strip() else None,



                research_mode=research_mode,
                world_setting_override=existing_ws if has_custom_ws else None,



            )



            self.p.write_json("research/research.json", res)

            # Double-check fact validity, purge PRC sources, and generate fact verification reports
            try:
                from core.fact_checker import verify_project_facts
                verify_project_facts(self.p, on_request=self._track_llm_request, provider_override=res_prov)
            except Exception as fce:
                log.warning("Stage 1 fact verification report generation failed: %s", fce)

            # Identify key characters and discover authentic online media
            try:
                self.p.activity("Stage 1/10: Identifying key characters & discovering authentic online media...")
                from core.character_detector import scan_and_populate_project_characters
                scan_and_populate_project_characters(self.p)
            except Exception as ce:
                log.warning("Stage 1 character media discovery failed: %s", ce)



            if user_research and user_research.strip() and not (self.p.path("research", "user_research.md")).exists():



                self.p.write_text("research/user_research.md", f"# User-Submitted Research\n\n{user_research.strip()}\n")



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("research", Status.COMPLETED, done=1, total=1, duration_override=elapsed)



            log.info("Research complete for %s in %.1fs (provider=%s, user_research=%s)", self.p.id, elapsed, res_prov, bool(user_research))



        except Exception as e:



            self.p.set_stage("research", Status.FAILED, error=str(e))



            raise





    # ---------------- Stage 2: Script ----------------

    def _run_script(self) -> None:



        st = self.p.stage("script")



        if st.status == Status.COMPLETED and self.p.path("script", "script.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 2/10: Generating narration script...")



        self.p.set_stage("script", Status.RUNNING)



        cfg = self.p.settings



        scr_prov = self.get_stage_model("script")



        res = self.p.read_json("research/research.json", {})



        partial = self.p.read_json("script/script.json", {})







        def on_sec(cur):



            self.p.write_json("script/script.json", cur)







        try:



            scr = write_script(self.p.data.topic, res, cfg, self._track_llm_request, partial=partial, on_section=on_sec, provider_override=scr_prov)



            self.p.write_json("script/script.json", scr)



            self.p.path("script", "script.md").write_text(script_markdown(scr), encoding="utf-8")

            # Stage 2: Fact check script against research dossier to catch hallucinations and invalid multipliers
            try:
                self.p.activity("Stage 2/10: Verifying script factual grounding & numbers...")
                from core.fact_checker import verify_script_facts
                verify_script_facts(self.p, on_request=self._track_llm_request, provider_override=scr_prov, auto_patch=True)
            except Exception as fce:
                log.warning("Stage 2 script fact verification failed: %s", fce)

            self.p.data.title = scr.get("title", self.p.data.topic)



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("script", Status.COMPLETED, done=scr.get("word_count", 0), total=scr.get("target_words", 0), duration_override=elapsed)



            self.p.save()



            log.info("Script complete: %d words in %.1fs (provider=%s)", scr.get("word_count", 0), elapsed, scr_prov)



        except Exception as e:



            self.p.set_stage("script", Status.FAILED, error=str(e))



            raise







    # ---------------- Stage 3: Scene Planning ----------------





    # ---------------- Stage 3: Scenes ----------------

    def _run_scenes(self) -> None:



        st = self.p.stage("scenes")



        if st.status == Status.COMPLETED and self.p.path("scenes", "scenes.json").exists() and self.p.scenes:



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 3/10: Storyboarding & scene segmentation...")



        self.p.set_stage("scenes", Status.RUNNING)



        cfg = self.p.settings



        scr = self.p.read_json("script/script.json")



        if not scr or not scr.get("sections"):



            raise RuntimeError("Cannot plan scenes without script")







        sc_cfg = cfg.get("scenes", {})



        wpm = float(cfg.get("script", {}).get("speech_rate_wpm", 150))



        avg_d = float(sc_cfg.get("average_duration", 8.0))



        min_d = float(sc_cfg.get("minimum_duration", 4.0))



        max_d = float(sc_cfg.get("maximum_duration", 14.0))







        raw = segment(scr["sections"], wpm, avg_d, min_d, max_d, seed=len(self.p.id))



        self.p.progress("scenes", 0, len(raw))







        from providers.llm import LLMClient



        scenes_prov = self.get_stage_model("scenes")



        client = LLMClient("scene_planning", self._track_llm_request, provider_override=scenes_prov)



        script_full = " ".join(s["text"] for s in scr["sections"])



        bible = visual_bible(self.p.data.topic, script_full, client)



        self.p.write_json("scenes/visual_bible.json", bible)







        def on_prog(done, total):
            self.p.progress("scenes", done, total)

        res_data = self.p.read_json("research/research.json", {})
        world_setting = res_data.get("world_setting") if isinstance(res_data, dict) else None

        try:
            scenes = direct_scenes(self.p.data.topic, raw, bible, cfg, client, progress=on_prog, world_setting=world_setting)



            placement = self.p.data.settings.get("presenter_placement")



            if not placement and self.p.data.settings.get("auto_presenter", False):



                placement = "intro"



            def_avatar = self.p.data.settings.get("default_avatar")
            proj_vp = self.p.data.settings.get("voice_profile") or self.p.settings.get("voice_profile")

            if placement:

                scenes = apply_presenter_placement(scenes, placement, def_avatar, project_voice_profile=proj_vp)



            self.p.set_scenes(scenes)

            # Automatically enforce >= 90% real images/footage for scenes mentioning main character
            try:
                auto_stock_mode = self.p.data.settings.get("images", {}).get("auto_stock_mode") or self.p.settings.get("auto_stock_mode", "balanced")
                if auto_stock_mode not in ("disabled", "off"):
                    from core.character_detector import enforce_main_character_real_image_ratio
                    enforce_main_character_real_image_ratio(self.p, ratio=0.9)
            except Exception as enf_err:
                log.warning("Auto enforcement of 90% real images for main character skipped: %s", enf_err)



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("scenes", Status.COMPLETED, done=len(scenes), total=len(scenes), duration_override=elapsed)



            log.info("Scene planning complete: %d scenes in %.1fs (provider=%s)", len(scenes), elapsed, scenes_prov)



        except Exception as e:



            self.p.set_stage("scenes", Status.FAILED, error=str(e))



            raise







    # ---------------- Stage 4: Visual Prompts ----------------





    # ---------------- Stage 4: Prompts ----------------

    def _run_prompts(self) -> None:



        st = self.p.stage("prompts")



        if st.status == Status.COMPLETED and self.p.path("prompts", "image_prompts.json").exists():



            return



        if self._cancel_flag: raise PipelineCancelled()







        t0 = time.perf_counter()



        self.p.activity("Stage 4/10: Creating image generation prompts...")



        self.p.set_stage("prompts", Status.RUNNING)



        cfg = self.p.settings



        scenes = self.p.scenes



        if not scenes:



            raise RuntimeError("No scenes available to prompt")







        seed = int(self.p.data.settings.get("seed", 12345))



        style = project_style(cfg, seed)



        self.p.data.style = style



        self.p.save()







        bible = self.p.read_json("scenes/visual_bible.json", {"entities": []})



        from providers.llm import LLMClient



        prompts_prov = self.get_stage_model("prompts")



        client = LLMClient("prompt_generation", self._track_llm_request, provider_override=prompts_prov)







        def on_prog(done, total):
            self.p.progress("prompts", done, total)

        res_data = self.p.read_json("research/research.json", {})
        world_setting = res_data.get("world_setting") if isinstance(res_data, dict) else None

        try:
            prompts = generate_prompts(scenes, style, bible, client, batch=int(cfg.get("scenes", {}).get("llm_batch_size", 8)), progress=on_prog, topic=self.p.data.topic, world_setting=world_setting)



            self.p.write_json("prompts/image_prompts.json", prompts)



            self.p.save_scenes()



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("prompts", Status.COMPLETED, done=len(prompts), total=len(prompts), duration_override=elapsed)



            log.info("Visual prompts complete for %d scenes in %.1fs", len(prompts), elapsed)



        except Exception as e:



            self.p.set_stage("prompts", Status.FAILED, error=str(e))



            raise







    # ---------------- Stage 5: Image Generation ----------------





    # ---------------- Stage 5: Images ----------------

    def _run_images(self) -> None:



        scenes = self.p.active_scenes()



        total = len(scenes)



        done = self._completed_image_count(scenes)



        if done == total and total > 0:

            st = self.p.stage("images")

            if st.status != Status.COMPLETED:

                self.p.set_stage("images", Status.COMPLETED, done=total, total=total, duration_override=st.duration_seconds or None)

            return

        t0 = time.perf_counter()



        prev_dur = self.p.stage("images").duration_seconds if done > 0 else 0.0



        self.p.set_stage("images", Status.RUNNING, done=done, total=total)



        cfg = self.p.settings



        img_cfg = cfg.get("images", {})



        fallback_name = img_cfg.get("fallback_provider", "placeholder")



        default_model = img_cfg.get("provider", "comfyui")



        current_model_name = self.get_stage_model("images") or default_model







        provider, current_model_name = self._resolve_image_provider(current_model_name, fallback_name)

















        width = int(img_cfg.get("width") or cfg.get("video", {}).get("width") or 1920)
        height = int(img_cfg.get("height") or cfg.get("video", {}).get("height") or 1080)

        steps = int(img_cfg.get("steps", 25))



        cfg_val = float(img_cfg.get("cfg", 6.5))



        retries = int(img_cfg.get("retries", 2))
        from core.media_dedup import (
            get_project_media_registry,
            is_media_in_cooldown,
            pick_best_media_candidate,
            extract_canonical_media_id,
            DEFAULT_MIN_SCENE_DISTANCE,
        )
        media_registry = get_project_media_registry(scenes)

        try:

            for s in scenes:



                if self._cancel_flag: raise PipelineCancelled()



                img_path = self.p.path("images", f"{s.tag}.png")







                # Skip if already generated



                if s.image.status == Status.COMPLETED and img_path.exists() and img_path.stat().st_size > 1000:



                    continue







                # Dynamic check: did the user switch the image engine between scenes?



                latest_model_name = self.get_stage_model("images") or img_cfg.get("provider", "comfyui")



                if latest_model_name != current_model_name:



                    log.info("Dynamic image engine switch between scenes: '%s' -> '%s' (Scene %d/%d)",



                             current_model_name, latest_model_name, s.scene_id, total)



                    self.p.activity(f"Stage 5/10: Switching engine to {latest_model_name} for scene {s.scene_id}...")



                    



                    # If switching away from ComfyUI, free GPU VRAM immediately



                    if current_model_name == "comfyui":



                        try:



                            provider.release()



                        except Exception:



                            pass



                    



                    new_prov = get_image_provider(latest_model_name, self.p.settings)



                    new_avail, new_reason = new_prov.available()



                    if new_avail:



                        provider = new_prov



                        current_model_name = latest_model_name



                        log.info("Successfully switched image provider to '%s' for scene %d", provider.name, s.scene_id)



                    else:



                        log.warning("Requested model '%s' unavailable (%s); continuing with '%s'",



                                    latest_model_name, new_reason, current_model_name)







                self.p.activity(f"Stage 5/10: Generating image {s.scene_id}/{total} ({provider.name})...")



                s.image.status = Status.RUNNING



                self.p.save_scenes()







                def _on_img_step(step_val: int, max_steps: int, st_txt: str = "sampling"):



                    try:



                        from api_server import update_image_progress



                        update_image_progress(self.p.id, s.scene_id, step_val, max_steps, st_txt)



                    except Exception as ex:



                        log.debug("on_img_step note: %s", ex)







                raw_prompt = s.prompt or s.visual_description



                if raw_prompt and re.search(r"[\u4e00-\u9fff]", raw_prompt):



                    try:



                        from agents.prompt_generator import translate_to_english_for_sdxl



                        raw_prompt = translate_to_english_for_sdxl(raw_prompt)



                        s.prompt = raw_prompt



                        self.p.save_scenes()



                    except Exception as ex:



                        log.warning("Failed to translate prompt to English in pipeline: %s", ex)







                curr_neg = merge_negative_prompts((s.negative_prompt or "").strip(), UNIVERSAL_QUALITY_NEGATIVE)







                checkpoint_override = current_model_name if current_model_name not in ("stock", "stock_photos", "placeholder", "comfyui") else img_cfg.get("checkpoint")



                req = ImageRequest(



                    prompt=raw_prompt,



                    negative=curr_neg,



                    seed=s.seed or (s.scene_id * 101),



                    width=width,



                    height=height,



                    steps=steps,



                    cfg=cfg_val,



                    output=img_path,



                    extra={

                        "description": s.visual_description,

                        "entities": getattr(s, "entities", []),

                        "checkpoint": checkpoint_override,

                        "progress_callback": _on_img_step,

                        "search_keyword": getattr(s, "search_keyword", None),

                        "media_source": getattr(s, "media_source", None),

                        "used_stock_keys": list(media_registry.keys()),

                        "recent_asset_keys": [cid for cid, sids in media_registry.items() if any(abs(prev_sid - s.scene_id) < DEFAULT_MIN_SCENE_DISTANCE for prev_sid in sids)],

                        "target_scene_id": s.scene_id,

                    }



                )







                existing_img_meta = dict(s.image.meta or {})



                prev_img_takes = list(existing_img_meta.get("takes", []))







                generated = False







                # Dynamic evaluation of authentic real-life media if auto_stock_mode is active



                auto_stock_mode = img_cfg.get("auto_stock_mode") or self.p.settings.get("auto_stock_mode", "balanced")



                if not getattr(s, "search_keyword", None) and auto_stock_mode not in ("disabled", None):



                    from agents.scene_planner import detect_real_world_footage_target



                    dyn_kw, dyn_src = detect_real_world_footage_target(

                        s.narration,

                        getattr(s, "visual_description", "") or "",

                        mode=auto_stock_mode,

                        topic=self.p.data.topic or ""

                    )



                    if dyn_kw:



                        s.search_keyword = dyn_kw



                        s.media_source = dyn_src



                        log.info("Stage 5 dynamic real-media detection for Scene %d: '%s' -> %s",



                                 s.scene_id, dyn_kw, dyn_src)
                # 0. Sourcing authentic biographical portrait (Wikipedia Infobox -> Wikimedia)
                is_portrait = bool(getattr(s, "search_keyword", None) and getattr(s, "media_source", "ai") in ("stock_portrait", "celebrity_portrait"))
                if is_portrait and not generated:
                    person_name = s.search_keyword
                    self.p.activity(f"Stage 5/10: Resolving authentic portrait for '{person_name}' (scene {s.scene_id})...")
                    try:
                        from providers.stock_client import resolve_wikipedia_portrait, search_wikimedia, download_media_file, format_stock_image
                        w_target = int(self.p.settings.get("images", {}).get("width", 1920))
                        h_target = int(self.p.settings.get("images", {}).get("height", 1080))

                        portrait_info = None
                        wiki_lead = resolve_wikipedia_portrait(person_name)
                        if wiki_lead and wiki_lead.get("media_url"):
                            cid = extract_canonical_media_id(wiki_lead["media_url"])
                            in_cooldown, conf_sid = is_media_in_cooldown(cid, s.scene_id, media_registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
                            if not in_cooldown:
                                portrait_info = wiki_lead
                            else:
                                log.info("Wikipedia lead portrait for '%s' is in cooldown (used in scene %s). Searching Wikimedia gallery...", person_name, conf_sid)

                        if not portrait_info:
                            wiki_res = search_wikimedia(person_name, media_type="image", limit=12)
                            alt_name = "沈伯洋" if person_name == "Puma Shen" else ("Puma Shen" if "沈伯洋" in person_name else "")
                            if alt_name and len(wiki_res) < 6:
                                extra_wiki = search_wikimedia(alt_name, media_type="image", limit=12)
                                existing_u = {w.get("media_url") for w in wiki_res}
                                for ew in extra_wiki:
                                    if ew.get("media_url") not in existing_u:
                                        wiki_res.append(ew)
                            if wiki_res:
                                # Strict name relevance validation: reject unrelated figures with the same surname
                                p_words = [pw.lower() for pw in re.split(r"\s+", person_name.strip()) if len(pw) >= 2]
                                valid_wiki_res = []
                                for w in wiki_res:
                                    w_text = f"{w.get('title', '')} {w.get('description', '')}".lower()
                                    if len(p_words) >= 2:
                                        if all(pw in w_text for pw in p_words):
                                            valid_wiki_res.append(w)
                                    else:
                                        if any(pw in w_text for pw in p_words):
                                            valid_wiki_res.append(w)
                                wiki_res = valid_wiki_res

                                chosen_candidate = pick_best_media_candidate(
                                    wiki_res, s.scene_id, media_registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE
                                )
                                if chosen_candidate:
                                    portrait_info = chosen_candidate
                                else:
                                    log.info("All %d Wikimedia photos for '%s' are currently in cooldown. Falling back to diverse AI generation for scene %d.", len(wiki_res), person_name, s.scene_id)

                        if portrait_info and portrait_info.get("media_url"):
                            temp_dl = img_path.with_name(f"{img_path.stem}_portrait_raw.jpg")
                            download_media_file(portrait_info["media_url"], temp_dl)
                            format_stock_image(temp_dl, img_path, target_w=w_target, target_h=h_target)
                            if temp_dl.exists():
                                try:
                                    temp_dl.unlink()
                                except Exception:
                                    pass

                            if img_path.exists() and img_path.stat().st_size > 1000:
                                merged_meta = dict(existing_img_meta)
                                merged_meta.update({
                                    "provider": portrait_info.get("source", "wikipedia"),
                                    "search_keyword": person_name,
                                    "title": portrait_info.get("title"),
                                    "url": portrait_info.get("media_url"),
                                    "author": portrait_info.get("author", "Wikipedia / Wikimedia Commons"),
                                    "license": portrait_info.get("license", "Public Domain / CC"),
                                    "media_source": "stock_portrait",
                                    "is_stock": True,
                                })
                                merged_meta["takes"] = prev_img_takes
                                s.image.status = Status.COMPLETED
                                s.image.path = self.p.rel(img_path)
                                s.image.meta = merged_meta
                                s.image.error = None
                                generated = True
                                cid = extract_canonical_media_id(portrait_info.get("media_url"))
                                if cid:
                                    media_registry.setdefault(cid, []).append(s.scene_id)
                                log.info("Scene %d successfully grounded authentic portrait for '%s' from %s: %s",
                                         s.scene_id, person_name, portrait_info.get("source"), portrait_info.get("title"))
                    except Exception as port_err:
                        log.warning("Portrait resolution failed for scene %d ('%s'): %s; falling back",
                                    s.scene_id, person_name, port_err)









                # Sourcing authentic YouTube footage/snippet if flagged



                is_yt = bool(getattr(s, "search_keyword", None) and getattr(s, "media_source", "ai") in ("youtube_snippet", "youtube_screenshot"))



                if is_yt:



                    as_clip = (getattr(s, "media_source", "ai") == "youtube_snippet")



                    clip_path = self.p.path("animation", f"{s.tag}.mp4") if as_clip else None



                    self.p.activity(f"Stage 5/10: Fetching YouTube {'clip' if as_clip else 'screenshot'} for '{s.search_keyword}' (scene {s.scene_id})...")



                    try:



                        from providers.youtube_snippet_client import extract_youtube_snippet



                        clip_dur = min(max(7.0, float(s.audio_duration or s.estimated_duration or 10.0)), 15.0)



                        yt_res = extract_youtube_snippet(

                            s.search_keyword,

                            output_video_path=clip_path,

                            output_image_path=img_path,

                            duration_sec=clip_dur,

                            as_clip=as_clip,

                            target_scene_id=s.scene_id,

                            media_registry=media_registry,

                            min_scene_distance=DEFAULT_MIN_SCENE_DISTANCE,

                        )
                        if yt_res and yt_res.get("source_url") and yt_res.get("source_url") != s.search_keyword:
                            s.search_keyword = yt_res["source_url"]
                        cid = extract_canonical_media_id(yt_res.get("video_id") or s.search_keyword)
                        if cid:
                            media_registry.setdefault(cid, []).append(s.scene_id)



                        if img_path.exists() and img_path.stat().st_size > 1000:



                            merged_meta = dict(existing_img_meta)



                            merged_meta.update({



                                "provider": "youtube",



                                "search_keyword": s.search_keyword,



                                "video_id": yt_res.get("video_id"),



                                "title": yt_res.get("title"),



                                "url": yt_res.get("url"),



                                "media_source": s.media_source



                            })



                            merged_meta["takes"] = prev_img_takes



                            s.image.status = Status.COMPLETED



                            s.image.path = self.p.rel(img_path)



                            s.image.meta = merged_meta



                            s.image.error = None







                            if as_clip and clip_path and clip_path.exists() and clip_path.stat().st_size > 1000:



                                s.animation.status = Status.COMPLETED



                                s.animation.path = self.p.rel(clip_path)



                                s.animation.meta = {



                                    "provider": "youtube",



                                    "source_url": yt_res.get("url"),



                                    "title": yt_res.get("title"),



                                    "duration": clip_dur



                                }



                                s.ai_video = True







                            generated = True



                            log.info("Scene %d successfully sourced YouTube %s for '%s': %s",



                                     s.scene_id, s.media_source, s.search_keyword, yt_res.get("title"))



                    except Exception as yt_err:



                        log.warning("YouTube snippet fetch failed for scene %d ('%s'): %s; falling back to Wikimedia/AI image",



                                    s.scene_id, s.search_keyword, yt_err)







                # Sourcing authentic Wikimedia Commons / Quick Stock photo if flagged or as YouTube fallback



                is_wiki = bool(getattr(s, "search_keyword", None) and getattr(s, "media_source", "ai") in ("wikimedia", "stock", "stock_photos", "stock_portrait"))



                if not generated and (is_wiki or (is_yt and not generated)):



                    search_term = getattr(s, "search_keyword", None) or s.narration



                    self.p.activity(f"Stage 5/10: Fetching Wikimedia photo for '{search_term}' (scene {s.scene_id})...")



                    try:



                        from providers.stock_client import search_wikimedia, search_stock_media, download_media_file, format_stock_image, extract_stock_search_keywords



                        w_target = int(self.p.settings.get("images", {}).get("width", 1920))



                        h_target = int(self.p.settings.get("images", {}).get("height", 1080))



                        wiki_res = search_wikimedia(search_term, media_type="image", limit=5)



                        if not wiki_res:



                            cand_kws = extract_stock_search_keywords(search_term)



                            for ckw in cand_kws:



                                wiki_res = search_wikimedia(ckw, media_type="image", limit=5)



                                if wiki_res:



                                    break



                        if not wiki_res:



                            wiki_res = search_stock_media(search_term, media_type="image", limit=5)







                        if wiki_res:
                            chosen = pick_best_media_candidate(
                                wiki_res, s.scene_id, media_registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE
                            )
                            if not chosen:
                                log.info("All Wikimedia candidates for '%s' are in cooldown. Falling back to AI image generation for scene %d.", search_term, s.scene_id)
                            else:
                                temp_dl = img_path.with_name(f"{img_path.stem}_wiki_raw.jpg")
                                download_media_file(chosen["media_url"], temp_dl)
                                format_stock_image(temp_dl, img_path, target_w=w_target, target_h=h_target)
                                if temp_dl.exists():
                                    try:
                                        temp_dl.unlink()
                                    except Exception:
                                        pass

                                if img_path.exists() and img_path.stat().st_size > 1000:
                                    merged_meta = dict(existing_img_meta)
                                    merged_meta.update({
                                        "provider": "stock",
                                        "source": chosen.get("source", "wikimedia"),
                                        "search_keyword": search_term,
                                        "title": chosen.get("title", ""),
                                        "author": chosen.get("author", "Wikimedia Contributor"),
                                        "license": chosen.get("license", "CC / Public Domain"),
                                        "url": chosen.get("media_url", ""),
                                        "media_source": "wikimedia",
                                        "is_stock": True,
                                    })
                                    merged_meta["takes"] = prev_img_takes
                                    s.image.status = Status.COMPLETED
                                    s.image.path = self.p.rel(img_path)
                                    s.image.meta = merged_meta
                                    s.image.error = None
                                    generated = True
                                    cid = extract_canonical_media_id(chosen.get("media_url"))
                                    if cid:
                                        media_registry.setdefault(cid, []).append(s.scene_id)
                                    log.info("Scene %d successfully sourced Wikimedia image for '%s': %s",
                                             s.scene_id, search_term, chosen.get("title"))
                    except Exception as wiki_err:



                        log.warning("Wikimedia fetch failed for scene %d ('%s'): %s; falling back to primary AI model",



                                    s.scene_id, search_term, wiki_err)







                for attempt in range(1, retries + 1):



                    if generated:



                        break



                    s.image.attempts = attempt



                    try:



                        meta = provider.generate(req, cancel=self.is_cancelled)



                        merged_meta = dict(existing_img_meta)



                        merged_meta.update(meta)



                        merged_meta["takes"] = prev_img_takes



                        s.image.status = Status.COMPLETED



                        s.image.path = self.p.rel(img_path)



                        s.image.meta = merged_meta



                        s.image.error = None



                        generated = True



                        break



                    except Exception as e:



                        log.warning("Image gen attempt %d for scene %d failed: %s", attempt, s.scene_id, e)



                        if attempt == retries:



                            s.image.error = str(e)







                if self._cancel_flag:



                    s.image.status = Status.PENDING



                    self.p.save_scenes()



                    raise PipelineCancelled()







                # Fallback to local GPU ComfyUI ONLY if primary was a cloud AI model (dalle3/imagen3/flux) that hit quota/credit errors,



                # never if the user chose online stock photos or placeholder



                if not generated and current_model_name not in ("comfyui", "stock", "stock_photos", "placeholder") and provider.name not in ("comfyui", "stock", "placeholder"):



                    try:



                        comfy_prov = get_image_provider("comfyui", self.p.settings)



                        avail, _ = comfy_prov.available()



                        if avail:



                            err_short = (s.image.error or "cloud API error")[:110]



                            log.warning("Scene %d primary image provider '%s' failed (%s); automatically falling back to local GPU ComfyUI...",



                                        s.scene_id, provider.name, s.image.error)



                            self.p.activity(f"Stage 5/10: Scene {s.scene_id} {provider.name} failed ({err_short}) → falling back to ComfyUI (GPU)...")



                            meta = comfy_prov.generate(req, cancel=self.is_cancelled)



                            merged_meta = dict(existing_img_meta)



                            merged_meta.update(meta)



                            merged_meta["takes"] = prev_img_takes



                            s.image.status = Status.COMPLETED



                            s.image.path = self.p.rel(img_path)



                            s.image.meta = merged_meta



                            s.image.error = None



                            generated = True



                    except Exception as comfy_err:



                        log.warning("ComfyUI fallback also failed for scene %d: %s", s.scene_id, comfy_err)







                # If cloud model failed and ComfyUI is unavailable, try Gemini nano-banana-2.1 or stock before placeholder



                if not generated and current_model_name not in ("nano-banana-2.1", "stock", "stock_photos", "placeholder"):



                    for candidate in ["nano-banana-2.1", "stock"]:



                        if candidate == current_model_name:



                            continue



                        try:



                            alt_prov = get_image_provider(candidate, self.p.settings)



                            avail, _ = alt_prov.available()



                            if avail:



                                log.warning("Scene %d primary '%s' failed (%s); trying fallback engine '%s'...",



                                            s.scene_id, provider.name, s.image.error, candidate)



                                self.p.activity(f"Stage 5/10: Scene {s.scene_id} falling back to {candidate}...")



                                meta = alt_prov.generate(req, cancel=self.is_cancelled)



                                merged_meta = dict(existing_img_meta)



                                merged_meta.update(meta)



                                merged_meta["takes"] = prev_img_takes



                                s.image.status = Status.COMPLETED



                                s.image.path = self.p.rel(img_path)



                                s.image.meta = merged_meta



                                s.image.error = None



                                generated = True



                                break



                        except Exception as alt_err:



                            log.warning("Alternative provider '%s' failed for scene %d: %s", candidate, s.scene_id, alt_err)







                if self._cancel_flag:



                    s.image.status = Status.PENDING



                    self.p.save_scenes()



                    raise PipelineCancelled()







                # Only if all real image generation engines failed, fall back to placeholder



                if not generated and fallback_name and fallback_name != provider.name:



                    log.warning("Scene %d falling back to %s image", s.scene_id, fallback_name)



                    fb = get_image_provider(fallback_name, self.p.settings)



                    try:



                        meta = fb.generate(req, cancel=self.is_cancelled)



                        merged_meta = dict(existing_img_meta)



                        merged_meta.update(meta)



                        merged_meta["takes"] = prev_img_takes



                        s.image.status = Status.COMPLETED



                        s.image.path = self.p.rel(img_path)



                        s.image.meta = merged_meta



                        s.image.error = f"Primary failed ({s.image.error}); used fallback"



                        generated = True



                    except Exception as fb_err:



                        s.image.status = Status.FAILED



                        s.image.error = f"Fallback also failed: {fb_err}"







                if generated:



                    with self.p.lock:



                        if getattr(provider, "is_cloud", False):



                            self.p.data.usage.images_cloud += 1



                        else:



                            self.p.data.usage.images_local += 1



                    try:



                        from core.versioning import record_scene_image_take



                        record_scene_image_take(self.p, s.scene_id, s.image.path, current_model_name, s.prompt or "", s.visual_style or "")



                    except Exception as tk_err:



                        log.debug("Take record note: %s", tk_err)



                else:



                    s.image.status = Status.FAILED







                self.p.save_scenes()



                done = sum(1 for sc in scenes if sc.image.status == Status.COMPLETED)



                self.p.progress("images", done, total)







            # VRAM Management: free ComfyUI VRAM after image stage



            if bool(img_cfg.get("free_vram_after_stage", True)):



                try:



                    provider.release()



                except Exception:



                    pass







            try:



                from api_server import reset_image_progress



                reset_image_progress()



            except Exception:



                pass







            elapsed = round(prev_dur + max(0.1, time.perf_counter() - t0), 1)



            failed_count = sum(1 for sc in scenes if sc.image.status == Status.FAILED)



            if failed_count > 0:



                self.p.set_stage("images", Status.FAILED, error=f"{failed_count} images failed to generate", done=done, total=total)



            else:



                self.p.set_stage("images", Status.COMPLETED, done=total, total=total, duration_override=elapsed)



                log.info("Image generation complete: %d images in %.1fs", total, elapsed)







        except Exception as e:



            with self.p.lock:



                self.p.stage("images").duration_seconds = round(prev_dur + max(0.0, time.perf_counter() - t0), 1)



            if not isinstance(e, PipelineCancelled):



                self.p.set_stage("images", Status.FAILED, error=str(e))



            raise



        finally:



            try:



                from api_server import reset_image_progress, set_image_inactive



                reset_image_progress()



                set_image_inactive()



            except Exception:



                pass


    # ---------------- Stage 7: Animation & Video Clips ----------------


    # ---------------- Stage 7: Ambient Music ----------------
    def _run_music(self) -> None:
        t0 = time.perf_counter()
        st = self.p.stage("music")
        if st.status == Status.COMPLETED:
            if self.p.path("music/music_plan.json").exists():
                return

        self.p.set_stage("music", Status.RUNNING, done=0, total=1)
        self.p.activity("Stage 7/10: Planning multi-movement ambient soundtrack & matching tracks...")

        try:
            from generators.music import plan_music_timeline
            from rendering.ffmpeg_renderer import project_timeline
            from rendering.transitions import total_length

            scenes, slots = project_timeline(self.p)
            total = total_length(slots)
            m = self.p.settings.get("music", {})
            pref = self.p.settings.get("music_preference") or m.get("track")
            topic = getattr(self.p, "topic", None) or (self.p.data.topic if hasattr(self.p, "data") and self.p.data else None)

            chapters = None
            chap_file = self.p.path("scenes/chapters.json")
            if chap_file.exists():
                try:
                    chapters = json.loads(chap_file.read_text(encoding="utf-8"))
                except Exception as e:
                    log.warning("Could not load chapters for music stage: %s", e)

            # Extract context text from script or research for semantic grounding
            context_text = ""
            scr_file = self.p.path("script/script.md")
            if scr_file.exists():
                try:
                    context_text = scr_file.read_text(encoding="utf-8")[:1200]
                except Exception:
                    pass
            if not context_text:
                res_file = self.p.path("research/research.json")
                if res_file.exists():
                    try:
                        context_text = str(json.loads(res_file.read_text(encoding="utf-8")))[:1200]
                    except Exception:
                        pass

            music_plan = plan_music_timeline(
                directory=m.get("directory", "data/music"),
                key=self.p.id,
                preferred=pref,
                topic=topic,
                context_text=context_text,
                total_duration=total,
                scenes=scenes,
                slots=slots,
                chapters=chapters,
                music_settings=m,
            )

            # Persist plan to music/music_plan.json
            plan_dicts = [seg.to_dict() for seg in music_plan]
            self.p.write_json("music/music_plan.json", plan_dicts)
            log.info("Planned and saved ambient music with %d segments to music/music_plan.json", len(plan_dicts))

            elapsed = round(time.perf_counter() - t0, 2)
            self.p.set_stage("music", Status.COMPLETED, done=1, total=1)
            self.p.stage("music").duration_seconds = elapsed
            self.p.save()
        except Exception as e:
            self.p.stage("music").error = str(e)
            self.p.set_stage("music", Status.FAILED)
            log.error("Failed to plan ambient music: %s", e, exc_info=True)
            raise


    def _run_animation(self) -> None:



        t0 = time.perf_counter()



        scenes = self.p.active_scenes()



        self.p.set_stage("animation", Status.RUNNING, done=0, total=len(scenes))



        cfg = self.p.settings



        pct = float(self.p.data.settings.get("ai_video_percentage", cfg.get("animation", {}).get("ai_video_percentage", 10)))



        cloud_enabled = bool(cfg.get("cloud", {}).get("enabled", False))



        max_clips = int(cfg.get("cloud", {}).get("max_video_clips", 8))













        # 1. Talking Head / Presenter Scenes: render avatar lipsync video



        from generators.avatar_generator import (
            generate_talking_avatar, load_avatar, is_fal_balance_depleted,
            FalBalanceDepletedError, turn_off_project_avatar
        )

        avatar_allowed = self.p.is_avatar_enabled() if hasattr(self.p, "is_avatar_enabled") else (self.p.settings.get("presenter_placement") not in ("none", "off", "disabled", False))
        presenter_scenes = [s for s in scenes if (getattr(s, "is_presenter", False) or s.visual_type == "talking_head")] if avatar_allowed else []

        if presenter_scenes:
            self.p.activity(f"Stage 8/10: Generating talking avatar presenter clips for {len(presenter_scenes)} scene(s)...")
            avatar_turned_off = False

            for ps in presenter_scenes:
                if self._cancel_flag: raise PipelineCancelled()

                audio_file = self.p.abs(ps.audio.path) if (ps.audio and ps.audio.path) else None
                if not audio_file or not os.path.exists(audio_file):
                    cand = self.p.path("audio", f"{ps.tag}.wav")
                    if os.path.exists(cand):
                        audio_file = cand

                if not audio_file or not os.path.exists(audio_file):
                    log.warning("No audio found for presenter scene %d, skipping talking head generation", ps.scene_id)
                    continue

                anim_file = self.p.abs(ps.animation.path) if (ps.animation and ps.animation.path) else None
                if ps.animation.status == Status.COMPLETED and anim_file and anim_file.exists():
                    try:
                        from rendering.ffmpeg_utils import duration as get_dur
                        a_dur = float(get_dur(audio_file))
                        v_dur = float(get_dur(anim_file))
                        a_mtime = os.path.getmtime(audio_file)
                        v_mtime = anim_file.stat().st_mtime
                        if v_dur >= a_dur - 0.25 and v_mtime >= a_mtime:
                            continue
                        log.info("Presenter scene %d avatar clip outdated (v_dur=%.2fs vs a_dur=%.2fs); re-rendering", ps.scene_id, v_dur, a_dur)
                    except Exception:
                        continue

                av_prof = load_avatar(getattr(ps, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar"))
                if not av_prof or (not av_prof.get("has_image") and not av_prof.get("has_base_video")):
                    log.warning("No avatar profile found for presenter scene %d", ps.scene_id)
                    continue

                self.p.activity(f"Stage 8/10: Generating talking avatar clip for Scene {ps.scene_id} ({av_prof.get('name')})...")
                out_clip = self.p.path("animation", f"{ps.tag}.mp4")

                try:
                    t_av0 = time.perf_counter()
                    meta = generate_talking_avatar(Path(audio_file), av_prof, Path(out_clip))
                    av_dur = round(max(0.1, time.perf_counter() - t_av0), 1)

                    ps.animation.status = Status.COMPLETED
                    ps.animation.path = self.p.rel(out_clip)
                    ps.animation.meta = meta
                    ps.animation.error = None
                    ps.ai_video = True

                    with self.p.lock:
                        if meta.get("is_cloud"):
                            self.p.data.usage.presenter_clips_cloud = getattr(self.p.data.usage, "presenter_clips_cloud", 0) + 1
                        else:
                            self.p.data.usage.presenter_clips_local = getattr(self.p.data.usage, "presenter_clips_local", 0) + 1
                        self.p.data.stage_durations["presenter"] = round(self.p.data.stage_durations.get("presenter", 0.0) + av_dur, 1)
                        self.p.save()

                    log.info("Generated talking avatar clip for scene %d using %s in %.1fs", ps.scene_id, meta.get("provider"), av_dur)

                except Exception as ex:
                    if is_fal_balance_depleted(ex):
                        log.warning(
                            "Fal.ai balance depleted (%s). Turning off avatar altogether in the video and continuing video making.",
                            ex
                        )
                        self.p.activity("Stage 8/10: ⚠️ Fal.ai 額度已耗盡，已全面關閉影片中的虛擬人出鏡，繼續以全畫面分鏡視覺製作影片...")
                        turn_off_project_avatar(self.p)
                        avatar_turned_off = True
                        break
                    else:
                        log.error("Failed to generate talking avatar for scene %d: %s", ps.scene_id, ex)
                        ps.animation.error = f"Avatar gen error: {ex}"

            if avatar_turned_off:
                scenes = self.p.scenes
            else:
                self.p.save_scenes()

        # Determine which scenes get AI video (excluding presenter scenes)

        non_presenter_scenes = [s for s in scenes if not (getattr(s, "is_presenter", False) or s.visual_type == "talking_head")]



        chosen_ids = select_for_animation(non_presenter_scenes, pct, max_clips=max_clips)



        self.p.save_scenes()







        stage_anim = self.get_stage_model("animation")



        anim_prov_name = stage_anim if stage_anim is not None else cfg.get("stage_models", {}).get("animation")







        if anim_prov_name and (anim_prov_name in ("remotion", "motion_graphics", "ai_motion_graphics") or anim_prov_name.startswith("remotion_")):

            for s in non_presenter_scenes:
                s.ai_video = False

            # Check if AI Motion Graphics Director mode (default for remotion or motion_graphics)
            use_ai_director = anim_prov_name in ("remotion", "motion_graphics", "ai_motion_graphics")
            if use_ai_director:
                self.p.activity("Stage 8/10: AI Motion Graphics Director analyzing narration & selecting scene components...")
                from agents.motion_graphics_director import MotionGraphicsDirector
                from generators.motion_graphics_renderer import render_timeline_motion_graphics

                remotion_cfg = (self.p.settings.get("remotion") or {})
                data_settings = getattr(self.p, "data", None) and getattr(self.p.data, "settings", None) or {}
                data_rem_cfg = (data_settings.get("remotion") or {})
                density = (
                    remotion_cfg.get("density")
                    or data_rem_cfg.get("density")
                    or (self.p.settings.get("animation") or {}).get("motion_graphics_density")
                    or data_settings.get("motion_graphics_density")
                    or "balanced"
                )
                is_modern = (
                    remotion_cfg.get("style") == "modern_tech_explainer"
                    or data_rem_cfg.get("style") == "modern_tech_explainer"
                    or density == "full"
                )
                candidate_scenes = scenes if is_modern else non_presenter_scenes
                director = MotionGraphicsDirector(self.p)
                timeline = director.plan_motion_graphics(candidate_scenes, density=density, cancel_check=self.is_cancelled)

                targets_count = len(timeline.scenes)
                self.p.set_stage("animation", Status.RUNNING, done=0, total=max(1, targets_count))
                self.p.activity(f"Stage 8/10: Rendering {targets_count} AI Motion Graphics scene(s) via Remotion (density={density})...")

                done_ids = render_timeline_motion_graphics(
                    self.p,
                    candidate_scenes,
                    timeline,
                    progress_callback=lambda d, t: self.p.progress("animation", d, max(1, t)),
                    cancel_check=self.is_cancelled,
                )
                if self._cancel_flag: raise PipelineCancelled()
                self.p.save_scenes()
                elapsed = round(max(0.1, time.perf_counter() - t0), 1)
                self.p.set_stage("animation", Status.COMPLETED, done=targets_count, total=max(1, targets_count), duration_override=elapsed)
                log.info("AI Motion Graphics rendered for scenes %s in %.1fs (others use Ken Burns)", done_ids, elapsed)
                return

            # Remotion documentary motion graphic mode
            from generators.remotion_cards import render_critical_scene_cards, select_critical_scenes
            comp = "FoxHeaderScene"
            if anim_prov_name in ("remotion_foxheader", "foxheader", "header"):
                comp = "FoxHeaderScene"
            elif anim_prov_name in ("remotion_foxmetric", "foxmetric", "metric"):
                comp = "FoxMetricScene"
            elif anim_prov_name in ("remotion_foxdatalist", "foxdatalist", "datalist"):
                comp = "FoxDataListScene"
            elif anim_prov_name in ("remotion_foxtimeline", "foxtimeline", "timeline"):
                comp = "FoxTimelineScene"
            elif anim_prov_name in ("remotion_pathway", "pathway", "branch"):
                comp = "BranchPathwayScene"
            elif anim_prov_name in ("remotion_callout", "callout", "leader"):
                comp = "LeaderCalloutScene"
            elif anim_prov_name in ("remotion_scale", "scale", "loupe"):
                comp = "ScaleCompareScene"
            elif anim_prov_name in ("remotion_evidence", "evidence", "highlight"):
                comp = "EvidenceHighlightScene"
            elif anim_prov_name == "remotion":
                comp = (self.p.data.settings or {}).get("remotion_style", "FoxHeaderScene")

            targets = [s for s in select_critical_scenes(non_presenter_scenes)
                       if not (s.animation.status == Status.COMPLETED
                               and (s.animation.meta or {}).get("provider") == "remotion"
                               and (s.animation.meta or {}).get("composition") == comp)]

            self.p.set_stage("animation", Status.RUNNING, done=0, total=max(1, len(targets)))
            self.p.activity(f"Stage 8/10: Rendering {len(targets)} Remotion [{comp}] motion-graphic card(s) for critical scenes...")

            done_ids = render_critical_scene_cards(
                self.p, targets,
                progress=lambda d, t: self.p.progress("animation", d, max(1, t)),
                cancel=self.is_cancelled, select=False,
                composition=comp,
            ) if targets else []

            if self._cancel_flag: raise PipelineCancelled()
            self.p.save_scenes()
            elapsed = round(max(0.1, time.perf_counter() - t0), 1)
            self.p.set_stage("animation", Status.COMPLETED, done=len(targets), total=max(1, len(targets)),
                             duration_override=elapsed)
            log.info("Remotion [%s] cards rendered for scenes %s in %.1fs (others use Ken Burns)", comp, done_ids, elapsed)
            return






        if anim_prov_name == "kenburns" or pct == 0:



            v_provider = get_video_provider("none")



        elif anim_prov_name:



            v_provider = get_video_provider(anim_prov_name)



        else:



            v_provider = get_video_provider()







        avail, reason = v_provider.available()



        if not avail or (v_provider.is_cloud and not cloud_enabled and anim_prov_name != v_provider.name):



            # Fall back to Ken Burns for all scenes



            if chosen_ids:



                log.info("Video provider unavailable or cloud disabled (%s); using Ken Burns for non-presenter scenes", reason)



            elapsed = round(max(0.1, time.perf_counter() - t0), 1)



            self.p.set_stage("animation", Status.COMPLETED, done=len(scenes), total=len(scenes), duration_override=elapsed)



            return







        to_gen = [s for s in non_presenter_scenes if s.ai_video and s.animation.status != Status.COMPLETED]



        total_anim = len(to_gen)



        self.p.set_stage("animation", Status.RUNNING, done=0, total=total_anim)







        for i, s in enumerate(to_gen):



            if self._cancel_flag: raise PipelineCancelled()







            # Dynamic check: did the user switch the animation engine between scenes?



            latest_anim = self.get_stage_model("animation")



            if latest_anim and latest_anim != anim_prov_name:



                log.info("Dynamic animation engine switch between scenes: '%s' -> '%s' (Scene %d)",



                         anim_prov_name, latest_anim, s.scene_id)



                anim_prov_name = latest_anim



                v_provider = get_video_provider("none" if anim_prov_name == "kenburns" else anim_prov_name)







            self.p.activity(f"Stage 8/10: Generating AI video clip {i + 1}/{total_anim} (scene {s.scene_id}, {anim_prov_name})...")



            s.animation.status = Status.RUNNING



            self.p.save_scenes()







            img_path = self.p.abs(s.image.path)



            out_clip = self.p.path("animation", f"{s.tag}.mp4")







            try:



                meta = v_provider.generate(img_path, s.visual_description, float(s.audio_duration or 6.0), out_clip, cancel=self.is_cancelled)



                s.animation.status = Status.COMPLETED



                s.animation.path = self.p.rel(out_clip)



                s.animation.meta = meta



                s.animation.error = None







                with self.p.lock:



                    if v_provider.is_cloud:



                        self.p.data.usage.video_clips_cloud += 1



                        rate = float(load_providers().get("pricing", {}).get("video_clip_usd", 0.5))



                        self.p.data.usage.estimated_cost_usd += rate



                    else:



                        self.p.data.usage.video_clips_local += 1



                    self.p.save()







            except Exception as e:



                log.warning("Video clip generation failed for scene %d (%s); falling back to Ken Burns", s.scene_id, e)



                s.animation.status = Status.SKIPPED



                s.animation.error = f"Video gen failed: {e}; used Ken Burns"







            self.p.save_scenes()



            self.p.progress("animation", i + 1, total_anim)







        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        self.p.set_stage("animation", Status.COMPLETED, done=total_anim, total=total_anim, duration_override=elapsed)



        try:



            from core.pricing import calculate_and_update_project_costs



            calculate_and_update_project_costs(self.p)



        except Exception as cost_err:



            log.warning("Cost update after animation: %s", cost_err)



        log.info("Animation stage complete in %.1fs", elapsed)


    # ---------------- Stage 9: Final Render ----------------


    # ---------------- Stage 9: Render ----------------

    def _run_render(self) -> None:
        if self._cancel_flag:
            raise PipelineCancelled()
        self.p.sync_avatar_disabled_state()
        super()._run_render()
