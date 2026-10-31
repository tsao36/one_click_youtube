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

from core.base_pipeline import BasePipeline, PipelineCancelled, apply_presenter_placement

from core.config import ROOT, get_secret, load_providers

from core.logging_setup import log

from core.models import STAGES, Asset, Scene, Status

from core.project_manager import Project, now

from core.versioning import record_stage_version

from generators.subtitle_generator import build_cues, write_ass, write_srt

from generators.voice_generator import default_profile_name, load_profile, synthesize, list_profiles

from providers.images import ImageRequest, get_image_provider

from providers.video import get_video_provider

from rendering.ffmpeg_renderer import project_timeline, render_project

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



        self.p.activity("Stage 1/9: Analyzing topic & researching...")



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



            )



            self.p.write_json("research/research.json", res)



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



        self.p.activity("Stage 2/9: Generating narration script...")



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



        self.p.activity("Stage 3/9: Storyboarding & scene segmentation...")



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







        try:



            scenes = direct_scenes(self.p.data.topic, raw, bible, cfg, client, progress=on_prog)



            placement = self.p.data.settings.get("presenter_placement")



            if not placement and self.p.data.settings.get("auto_presenter", False):



                placement = "intro"



            def_avatar = self.p.data.settings.get("default_avatar")



            if placement:



                scenes = apply_presenter_placement(scenes, placement, def_avatar)



            self.p.set_scenes(scenes)



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



        self.p.activity("Stage 4/9: Creating image generation prompts...")



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







        try:



            prompts = generate_prompts(scenes, style, bible, client, batch=int(cfg.get("scenes", {}).get("llm_batch_size", 8)), progress=on_prog, topic=self.p.data.topic)



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



        done = sum(1 for s in scenes if s.image.status == Status.COMPLETED and self.p.abs(s.image.path) and self.p.abs(s.image.path).exists())



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







        provider = get_image_provider(current_model_name, self.p.settings)



        avail, reason = provider.available()



        if not avail:



            log.warning("Image provider '%s' unavailable (%s); using fallback '%s'", current_model_name, reason, fallback_name)



            current_model_name = fallback_name



            provider = get_image_provider(fallback_name, self.p.settings)

















        width = int(img_cfg.get("width") or cfg.get("video", {}).get("width") or 1920)
        height = int(img_cfg.get("height") or cfg.get("video", {}).get("height") or 1080)

        steps = int(img_cfg.get("steps", 25))



        cfg_val = float(img_cfg.get("cfg", 6.5))



        retries = int(img_cfg.get("retries", 2))



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



                    self.p.activity(f"Stage 5/9: Switching engine to {latest_model_name} for scene {s.scene_id}...")



                    



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







                self.p.activity(f"Stage 5/9: Generating image {s.scene_id}/{total} ({provider.name})...")



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







                anti_clone_tokens = "multiple people with the same face, cloned faces, identical faces, duplicate faces, identical twins, clone army, copy-paste faces, repeated facial features"



                curr_neg = (s.negative_prompt or "").strip()



                if "cloned faces" not in curr_neg.lower():



                    curr_neg = f"{curr_neg}, {anti_clone_tokens}".strip(", ")







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



                        "progress_callback": _on_img_step



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







                # Sourcing authentic YouTube footage/snippet if flagged



                is_yt = bool(getattr(s, "search_keyword", None) and getattr(s, "media_source", "ai") in ("youtube_snippet", "youtube_screenshot"))



                if is_yt:



                    as_clip = (getattr(s, "media_source", "ai") == "youtube_snippet")



                    clip_path = self.p.path("animation", f"{s.tag}.mp4") if as_clip else None



                    self.p.activity(f"Stage 5/9: Fetching YouTube {'clip' if as_clip else 'screenshot'} for '{s.search_keyword}' (scene {s.scene_id})...")



                    try:



                        from providers.youtube_snippet_client import extract_youtube_snippet



                        clip_dur = min(max(3.0, float(s.audio_duration or s.estimated_duration or 3.0)), 6.0)



                        yt_res = extract_youtube_snippet(



                            s.search_keyword,



                            output_video_path=clip_path,



                            output_image_path=img_path,



                            duration_sec=clip_dur,



                            as_clip=as_clip



                        )



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



                is_wiki = bool(getattr(s, "search_keyword", None) and getattr(s, "media_source", "ai") in ("wikimedia", "stock", "stock_photos"))



                if not generated and (is_wiki or (is_yt and not generated)):



                    search_term = getattr(s, "search_keyword", None) or s.narration



                    self.p.activity(f"Stage 5/9: Fetching Wikimedia photo for '{search_term}' (scene {s.scene_id})...")



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



                            chosen = wiki_res[0]



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



                            self.p.activity(f"Stage 5/9: Scene {s.scene_id} {provider.name} failed ({err_short}) → falling back to ComfyUI (GPU)...")



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



                                self.p.activity(f"Stage 5/9: Scene {s.scene_id} falling back to {candidate}...")



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







    # ---------------- Stage 6: Voice Generation ----------------





    # ---------------- Stage 6: Voice ----------------

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





    # ---------------- Stage 7: Animation ----------------

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

        presenter_scenes = [s for s in scenes if (getattr(s, "is_presenter", False) or s.visual_type == "talking_head")]

        if presenter_scenes:
            self.p.activity(f"Stage 7/9: Generating talking avatar presenter clips for {len(presenter_scenes)} scene(s)...")
            avatar_turned_off = False

            for ps in presenter_scenes:
                if self._cancel_flag: raise PipelineCancelled()

                anim_file = self.p.abs(ps.animation.path) if (ps.animation and ps.animation.path) else None
                if ps.animation.status == Status.COMPLETED and anim_file and anim_file.exists():
                    continue

                audio_file = self.p.abs(ps.audio.path) if (ps.audio and ps.audio.path) else None
                if not audio_file or not os.path.exists(audio_file):
                    cand = self.p.path("audio", f"{ps.tag}.wav")
                    if os.path.exists(cand):
                        audio_file = cand

                if not audio_file or not os.path.exists(audio_file):
                    log.warning("No audio found for presenter scene %d, skipping talking head generation", ps.scene_id)
                    continue

                av_prof = load_avatar(getattr(ps, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar"))
                if not av_prof or (not av_prof.get("has_image") and not av_prof.get("has_base_video")):
                    log.warning("No avatar profile found for presenter scene %d", ps.scene_id)
                    continue

                self.p.activity(f"Stage 7/9: Generating talking avatar clip for Scene {ps.scene_id} ({av_prof.get('name')})...")
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
                        self.p.activity("Stage 7/9: ⚠️ Fal.ai 額度已耗盡，已全面關閉影片中的虛擬人出鏡，繼續以全畫面分鏡視覺製作影片...")
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
                self.p.activity("Stage 7/9: AI Motion Graphics Director analyzing narration & selecting scene components...")
                from agents.motion_graphics_director import MotionGraphicsDirector
                from generators.motion_graphics_renderer import render_timeline_motion_graphics

                density = (self.p.settings.get("animation") or {}).get("motion_graphics_density") or self.p.data.settings.get("motion_graphics_density", "balanced")
                director = MotionGraphicsDirector(self.p)
                timeline = director.plan_motion_graphics(non_presenter_scenes, density=density, cancel_check=self.is_cancelled)

                targets_count = len(timeline.scenes)
                self.p.set_stage("animation", Status.RUNNING, done=0, total=max(1, targets_count))
                self.p.activity(f"Stage 7/9: Rendering {targets_count} AI Motion Graphics scene(s) via Remotion...")

                done_ids = render_timeline_motion_graphics(
                    self.p,
                    non_presenter_scenes,
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

            # Legacy single-card Remotion mode
            from generators.remotion_cards import render_critical_scene_cards, select_critical_scenes
            comp = "TechCard"
            if anim_prov_name in ("remotion_minimalist", "minimalist"):
                comp = "MinimalistCard"
            elif anim_prov_name in ("remotion_cinema", "cinema"):
                comp = "CinemaImpactCard"
            elif anim_prov_name == "remotion":
                comp = (self.p.data.settings or {}).get("remotion_style", "TechCard")

            targets = [s for s in select_critical_scenes(non_presenter_scenes)
                       if not (s.animation.status == Status.COMPLETED
                               and (s.animation.meta or {}).get("provider") == "remotion"
                               and (s.animation.meta or {}).get("composition") == comp)]

            self.p.set_stage("animation", Status.RUNNING, done=0, total=max(1, len(targets)))
            self.p.activity(f"Stage 7/9: Rendering {len(targets)} Remotion [{comp}] motion-graphic card(s) for critical scenes...")

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







            self.p.activity(f"Stage 7/9: Generating AI video clip {i + 1}/{total_anim} (scene {s.scene_id}, {anim_prov_name})...")



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







    # ---------------- Stage 8: Subtitles ----------------





    # ---------------- Stage 8: Subtitles ----------------

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



            max_lines=int(sub_cfg.get("max_lines", 2))



        )







        srt_file = self.p.path("subtitles", "subtitles.srt")



        ass_file = self.p.path("subtitles", "subtitles.ass")



        write_srt(cues, srt_file)







        # Check if fOx Hsiao style motion graphics callouts are enabled (toggleable)



        enabled_motion_callouts = bool(

            sub_cfg.get("motion_graphics_callouts", True)

            and sub_cfg.get("motion_graphics", True)

            and sub_cfg.get("callouts_enabled", True)

            and self.p.data.settings.get("motion_callouts", True)

        )

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



            ai_watermark=bool(sub_cfg.get("ai_watermark", False)),



        )







        elapsed = round(max(0.1, time.perf_counter() - t0), 1)



        callouts_info = f" with {len(callouts)} motion graphic cards" if callouts else " (motion callouts disabled)"



        self.p.set_stage("subtitles", Status.COMPLETED, done=len(cues), total=len(cues), duration_override=elapsed)



        log.info("Subtitles generated in %.1fs: %d dialogue cues%s", elapsed, len(cues), callouts_info)







    # ---------------- Stage 9: Final Render ----------------





    # ---------------- Stage 9: Render ----------------

    def _run_render(self) -> None:



        if self._cancel_flag: raise PipelineCancelled()



        self.p.sync_avatar_disabled_state()



        self.p.clear_clips_cache()



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



