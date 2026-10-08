"""Pipeline coordinator: executes stages with memory awareness, resumability, and fallbacks."""
from __future__ import annotations

import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.animation_selector import select_for_animation
from agents.prompt_generator import generate_prompts, project_style
from agents.researcher import research
from agents.scene_planner import direct_scenes, segment, visual_bible
from agents.script_writer import script_markdown, write_script
from core.config import ROOT, get_secret, load_providers
from core.logging_setup import log
from core.models import STAGES, Asset, Scene, Status
from core.project_manager import Project, now
from core.versioning import record_stage_version
from generators.subtitle_generator import build_cues, write_ass, write_srt
from generators.voice_generator import default_profile_name, load_profile, synthesize
from providers.images import ImageRequest, get_image_provider
from providers.llm.base import LLMProvider
from providers.video import get_video_provider
from rendering.ffmpeg_renderer import project_timeline, render_project
from rendering.transitions import total_length


class PipelineCancelled(Exception):
    pass


class Pipeline:
    """Orchestrates an end-to-end video project."""

    def __init__(self, project: Project, stop_at: Optional[str] = None):
        self.p = project
        self.stop_at = stop_at
        self._cancel_flag = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel_flag = True
        try:
            from rendering.ffmpeg_utils import kill_all_ffmpeg_processes
            kill_all_ffmpeg_processes()
        except Exception:
            pass

    def is_cancelled(self) -> bool:
        return self._cancel_flag

    def _track_llm_request(self, provider: LLMProvider) -> None:
        with self.p.lock:
            self.p.data.usage.llm_requests += 1
            if provider.is_cloud:
                self.p.data.usage.llm_cloud_requests += 1
                rate = float(load_providers().get("pricing", {}).get("llm_request_usd", 0.0))
                self.p.data.usage.estimated_cost_usd += rate
            self.p.save()

    def run(self) -> None:
        """Run through all stages sequentially, picking up from last completed step."""
        with self._lock:
            self._cancel_flag = False
            if not self.p.data.started_at:
                self.p.data.started_at = now()
            self.p.data.state = "running"
            self.p.data.error = None
            self.p.save()

        try:
            self._run_research()
            if self._check_stop("research"): return

            self._run_script()
            if self._check_stop("script"): return

            self._run_scenes()
            if self._check_stop("scenes"): return

            self._run_prompts()
            if self._check_stop("prompts"): return

            self._run_images()
            if self._check_stop("images"): return

            self._run_voice()
            if self._check_stop("voice"): return

            self._run_animation()
            if self._check_stop("animation"): return

            self._run_subtitles()
            if self._check_stop("subtitles"): return

            self._run_render()

            with self.p.lock:
                self.p.data.state = "completed"
                self.p.data.completed_at = now()
                if self.p.data.started_at:
                    try:
                        t_start = datetime.fromisoformat(self.p.data.started_at)
                        t_end = datetime.fromisoformat(self.p.data.completed_at)
                        self.p.data.total_duration_seconds = max(
                            self.p.data.total_duration_seconds,
                            round((t_end - t_start).total_seconds(), 1)
                        )
                    except Exception:
                        pass
                self.p.data.activity = "Video generation complete!"
                self.p.save()
            log.info("Project '%s' finished successfully (took %.1fs)", self.p.id, self.p.data.total_duration_seconds)

        except PipelineCancelled:
            with self.p.lock:
                self.p.data.state = "paused"
                self.p.data.activity = "Cancelled by user"
                self.p.save()
            log.info("Project '%s' pipeline cancelled", self.p.id)
        except Exception as e:
            with self.p.lock:
                self.p.data.state = "failed"
                self.p.data.error = str(e)
                self.p.data.activity = f"Failed: {e}"
                for s_name, s_state in self.p.data.stages.items():
                    if s_state.status == Status.RUNNING:
                        s_state.status = Status.FAILED
                        s_state.error = str(e)
                self.p.save()
            log.exception("Project '%s' pipeline error: %s", self.p.id, e)
            raise

    def run_stage(self, stage_name: str) -> None:
        """Run exactly one stage in isolation for testing and tuning."""
        stage_methods = {
            "research": self._run_research,
            "script": self._run_script,
            "scenes": self._run_scenes,
            "prompts": self._run_prompts,
            "images": self._run_images,
            "voice": self._run_voice,
            "animation": self._run_animation,
            "subtitles": self._run_subtitles,
            "render": self._run_render,
        }
        if stage_name not in stage_methods:
            raise ValueError(f"Unknown stage '{stage_name}'")

        with self._lock:
            self._cancel_flag = False
            self.p.data.state = "running"
            self.p.data.activity = f"Testing stage: {stage_name}..."
            self.p.data.error = None
            self.p.set_stage(stage_name, Status.PENDING)
            # Archive active files as a version before generating a new version
            try:
                record_stage_version(self.p, stage_name)
            except Exception as ex:
                log.warning("Could not archive version for %s: %s", stage_name, ex)

            if stage_name == "research":
                (self.p.path("research", "research.json")).unlink(missing_ok=True)
                self.p.set_stage("script", Status.PENDING)
            elif stage_name == "script":
                (self.p.path("script", "script.json")).unlink(missing_ok=True)
                (self.p.path("script", "script.md")).unlink(missing_ok=True)
                self.p.set_stage("scenes", Status.PENDING)
            elif stage_name == "scenes":
                (self.p.path("scenes", "scenes.json")).unlink(missing_ok=True)
                (self.p.path("scenes", "visual_bible.json")).unlink(missing_ok=True)
                self.p.data.scenes = []
                self.p.set_stage("prompts", Status.PENDING)
            elif stage_name == "prompts":
                (self.p.path("prompts", "image_prompts.json")).unlink(missing_ok=True)
                for s in self.p.scenes:
                    s.prompt = None
                self.p.save_scenes()
                self.p.set_stage("images", Status.PENDING)
            elif stage_name == "voice":
                for s in self.p.scenes:
                    s.audio.status = Status.PENDING
                    s.audio.path = None
                self.p.save_scenes()
                self.p.set_stage("subtitles", Status.PENDING)
                self.p.set_stage("render", Status.PENDING)
            elif stage_name == "images":
                for s in self.p.scenes:
                    s.image.status = Status.PENDING
                    s.image.path = None
                self.p.save_scenes()
                self.p.set_stage("render", Status.PENDING)
            elif stage_name == "animation":
                for s in self.p.scenes:
                    s.animation.status = Status.PENDING
                    s.animation.path = None
                self.p.save_scenes()
                self.p.set_stage("render", Status.PENDING)
            elif stage_name == "subtitles":
                (self.p.path("subtitles", "subtitles.srt")).unlink(missing_ok=True)
                self.p.set_stage("render", Status.PENDING)
            self.p.save()

        try:
            stage_methods[stage_name]()
            # Snapshot newly completed output as the active version
            try:
                record_stage_version(self.p, stage_name)
            except Exception as ex:
                log.warning("Could not record new version for %s: %s", stage_name, ex)
            with self.p.lock:
                self.p.data.state = "paused"
                self.p.data.activity = f"Stage '{stage_name}' complete! Ready for tuning & review."
                self.p.save()
            log.info("Stage '%s' completed successfully in isolation", stage_name)
        except PipelineCancelled:
            with self.p.lock:
                self.p.data.state = "paused"
                self.p.data.activity = f"Stage '{stage_name}' cancelled by user"
                self.p.save()
        except Exception as e:
            with self.p.lock:
                self.p.data.state = "failed"
                self.p.data.error = str(e)
                self.p.data.activity = f"Stage '{stage_name}' failed: {e}"
                self.p.set_stage(stage_name, Status.FAILED, error=str(e))
                self.p.save()
            raise

    def _check_stop(self, current_stage: str) -> bool:
        if self._cancel_flag:
            raise PipelineCancelled()
        if self.stop_at == current_stage:
            with self.p.lock:
                self.p.data.state = "paused"
                self.p.data.activity = f"Paused after stage '{current_stage}'. Ready for inspection or next stage."
                self.p.save()
            return True
        return False

    # ---------------- Stage 1: Research ----------------
    def _run_research(self) -> None:
        st = self.p.stage("research")
        if st.status == Status.COMPLETED and self.p.path("research", "research.json").exists():
            return
        if self._cancel_flag: raise PipelineCancelled()

        self.p.activity("Stage 1/9: Analyzing topic & researching...")
        self.p.set_stage("research", Status.RUNNING)
        cfg = self.p.settings
        stage_models = cfg.get("stage_models", {})
        res_prov = stage_models.get("research")
        enabled = bool(cfg.get("script", {}).get("research_enabled", False)) or (res_prov == "gemini_search")
        lang = cfg.get("video", {}).get("language", "English")
        dur_mins = float(cfg.get("video", {}).get("duration_minutes", 5.0))
        try:
            res = research(self.p.data.topic, lang, enabled, self._track_llm_request, duration_minutes=dur_mins, provider_override=res_prov)
            self.p.write_json("research/research.json", res)
            self.p.set_stage("research", Status.COMPLETED, done=1, total=1)
            log.info("Research complete for %s", self.p.id)
        except Exception as e:
            self.p.set_stage("research", Status.FAILED, error=str(e))
            raise

    # ---------------- Stage 2: Script ----------------
    def _run_script(self) -> None:
        st = self.p.stage("script")
        if st.status == Status.COMPLETED and self.p.path("script", "script.json").exists():
            return
        if self._cancel_flag: raise PipelineCancelled()

        self.p.activity("Stage 2/9: Generating narration script...")
        self.p.set_stage("script", Status.RUNNING)
        cfg = self.p.settings
        stage_models = cfg.get("stage_models", {})
        scr_prov = stage_models.get("script")
        res = self.p.read_json("research/research.json", {})
        partial = self.p.read_json("script/script.json", {})

        def on_sec(cur):
            self.p.write_json("script/script.json", cur)

        try:
            scr = write_script(self.p.data.topic, res, cfg, self._track_llm_request, partial=partial, on_section=on_sec, provider_override=scr_prov)
            self.p.write_json("script/script.json", scr)
            self.p.path("script", "script.md").write_text(script_markdown(scr), encoding="utf-8")
            self.p.data.title = scr.get("title", self.p.data.topic)
            self.p.set_stage("script", Status.COMPLETED, done=scr.get("word_count", 0), total=scr.get("target_words", 0))
            self.p.save()
            log.info("Script complete: %d words", scr.get("word_count", 0))
        except Exception as e:
            self.p.set_stage("script", Status.FAILED, error=str(e))
            raise

    # ---------------- Stage 3: Scene Planning ----------------
    def _run_scenes(self) -> None:
        st = self.p.stage("scenes")
        if st.status == Status.COMPLETED and self.p.path("scenes", "scenes.json").exists() and self.p.scenes:
            return
        if self._cancel_flag: raise PipelineCancelled()

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
        stage_models = cfg.get("stage_models", {})
        scenes_prov = stage_models.get("scenes")
        client = LLMClient("scene_planning", self._track_llm_request, provider_override=scenes_prov)
        script_full = " ".join(s["text"] for s in scr["sections"])
        bible = visual_bible(self.p.data.topic, script_full, client)
        self.p.write_json("scenes/visual_bible.json", bible)

        def on_prog(done, total):
            self.p.progress("scenes", done, total)

        try:
            scenes = direct_scenes(self.p.data.topic, raw, bible, cfg, client, progress=on_prog)
            self.p.set_scenes(scenes)
            self.p.set_stage("scenes", Status.COMPLETED, done=len(scenes), total=len(scenes))
            log.info("Scene planning complete: %d scenes", len(scenes))
        except Exception as e:
            self.p.set_stage("scenes", Status.FAILED, error=str(e))
            raise

    # ---------------- Stage 4: Visual Prompts ----------------
    def _run_prompts(self) -> None:
        st = self.p.stage("prompts")
        if st.status == Status.COMPLETED and self.p.path("prompts", "image_prompts.json").exists():
            return
        if self._cancel_flag: raise PipelineCancelled()

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
        stage_models = cfg.get("stage_models", {})
        prompts_prov = stage_models.get("prompts")
        client = LLMClient("prompt_generation", self._track_llm_request, provider_override=prompts_prov)

        def on_prog(done, total):
            self.p.progress("prompts", done, total)

        try:
            prompts = generate_prompts(scenes, style, bible, client, batch=int(cfg.get("scenes", {}).get("llm_batch_size", 8)), progress=on_prog)
            self.p.write_json("prompts/image_prompts.json", prompts)
            self.p.save_scenes()
            self.p.set_stage("prompts", Status.COMPLETED, done=len(prompts), total=len(prompts))
            log.info("Visual prompts complete for %d scenes", len(prompts))
        except Exception as e:
            self.p.set_stage("prompts", Status.FAILED, error=str(e))
            raise

    # ---------------- Stage 5: Image Generation ----------------
    def _run_images(self) -> None:
        scenes = self.p.active_scenes()
        total = len(scenes)
        done = sum(1 for s in scenes if s.image.status == Status.COMPLETED and self.p.abs(s.image.path) and self.p.abs(s.image.path).exists())

        if done == total and total > 0:
            self.p.set_stage("images", Status.COMPLETED, done=total, total=total)
            return

        self.p.set_stage("images", Status.RUNNING, done=done, total=total)
        cfg = self.p.settings
        img_cfg = cfg.get("images", {})
        stage_models = cfg.get("stage_models", {})
        primary_name = stage_models.get("images") or img_cfg.get("provider", "comfyui")
        fallback_name = img_cfg.get("fallback_provider", "placeholder")

        provider = get_image_provider(primary_name, cfg)
        avail, reason = provider.available()
        if not avail:
            log.warning("Image provider '%s' unavailable (%s); using fallback '%s'", primary_name, reason, fallback_name)
            provider = get_image_provider(fallback_name, cfg)

        width = int(img_cfg.get("width", 1024))
        height = int(img_cfg.get("height", 576))
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

                req = ImageRequest(
                    prompt=raw_prompt,
                    negative=s.negative_prompt,
                    seed=s.seed or (s.scene_id * 101),
                    width=width,
                    height=height,
                    steps=steps,
                    cfg=cfg_val,
                    output=img_path,
                    extra={
                        "description": s.visual_description,
                        "checkpoint": img_cfg.get("checkpoint"),
                        "progress_callback": _on_img_step
                    }
                )

                existing_img_meta = dict(s.image.meta or {})
                prev_img_takes = list(existing_img_meta.get("takes", []))

                generated = False
                for attempt in range(1, retries + 1):
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

                # Fallback to placeholder if primary model crashed or failed
                if not generated and fallback_name and fallback_name != provider.name:
                    log.warning("Scene %d falling back to %s image", s.scene_id, fallback_name)
                    fb = get_image_provider(fallback_name, cfg)
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
                        record_scene_image_take(self.p, s.scene_id, s.image.path, img_cfg.get("checkpoint", ""), s.prompt or "", s.visual_style or "")
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

            failed_count = sum(1 for sc in scenes if sc.image.status == Status.FAILED)
            if failed_count > 0:
                self.p.set_stage("images", Status.FAILED, error=f"{failed_count} images failed to generate", done=done, total=total)
            else:
                self.p.set_stage("images", Status.COMPLETED, done=total, total=total)
                log.info("Image generation complete: %d images", total)

        except Exception as e:
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
    def _run_voice(self) -> None:
        scenes = self.p.active_scenes()
        total = len(scenes)
        done = sum(1 for s in scenes if s.audio.status == Status.COMPLETED and self.p.abs(s.audio.path) and self.p.abs(s.audio.path).exists())

        if done == total and total > 0:
            self.p.set_stage("voice", Status.COMPLETED, done=total, total=total)
            return

        self.p.set_stage("voice", Status.RUNNING, done=done, total=total)
        cfg = self.p.settings
        p_name = self.p.data.settings.get("voice_profile") or default_profile_name(cfg)
        profile = load_profile(p_name)

        try:
            for s in scenes:
                if self._cancel_flag: raise PipelineCancelled()
                audio_path = self.p.path("audio", f"{s.tag}.wav")

                if s.audio.status == Status.COMPLETED and audio_path.exists() and audio_path.stat().st_size > 1000:
                    continue

                self.p.activity(f"Stage 6/9: Generating voice {s.scene_id}/{total}...")
                s.audio.status = Status.RUNNING
                self.p.save_scenes()

                scene_p_name = s.voice_profile or p_name
                scene_profile = load_profile(scene_p_name)
                existing_audio_meta = dict(s.audio.meta or {})
                prev_audio_takes = list(existing_audio_meta.get("takes", []))

                try:
                    meta = synthesize(s.narration, scene_profile, audio_path, cfg)
                    merged_audio_meta = dict(existing_audio_meta)
                    merged_audio_meta.update(meta)
                    merged_audio_meta["voice"] = scene_p_name
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

            self.p.set_stage("voice", Status.COMPLETED, done=total, total=total)
            log.info("Voice generation complete: %d clips", total)
        except Exception as e:
            self.p.set_stage("voice", Status.FAILED, error=str(e))
            raise

    # ---------------- Stage 7: Animation & Video Clips ----------------
    def _run_animation(self) -> None:
        scenes = self.p.active_scenes()
        cfg = self.p.settings
        pct = float(self.p.data.settings.get("ai_video_percentage", cfg.get("animation", {}).get("ai_video_percentage", 10)))
        cloud_enabled = bool(cfg.get("cloud", {}).get("enabled", False))
        max_clips = int(cfg.get("cloud", {}).get("max_video_clips", 8))

        # Determine which scenes get AI video
        chosen_ids = select_for_animation(scenes, pct, max_clips=max_clips)
        self.p.save_scenes()

        stage_models = cfg.get("stage_models", {})
        anim_prov_name = stage_models.get("animation")
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
                log.info("Video provider unavailable or cloud disabled (%s); using Ken Burns for all %d scenes", reason, len(scenes))
            self.p.set_stage("animation", Status.COMPLETED, done=len(scenes), total=len(scenes))
            return

        to_gen = [s for s in scenes if s.ai_video and s.animation.status != Status.COMPLETED]
        total_anim = len(to_gen)
        self.p.set_stage("animation", Status.RUNNING, done=0, total=total_anim)

        for i, s in enumerate(to_gen):
            if self._cancel_flag: raise PipelineCancelled()
            self.p.activity(f"Stage 7/9: Generating AI video clip {i + 1}/{total_anim} (scene {s.scene_id})...")
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

        self.p.set_stage("animation", Status.COMPLETED, done=total_anim, total=total_anim)

    # ---------------- Stage 8: Subtitles ----------------
    def _run_subtitles(self) -> None:
        st = self.p.stage("subtitles")
        if st.status == Status.COMPLETED and self.p.path("subtitles", "subtitles.srt").exists():
            return
        if self._cancel_flag: raise PipelineCancelled()

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
        write_ass(
            cues, ass_file,
            style=sub_cfg.get("style", "youtube_standard"),
            width=int(cfg["video"]["width"]),
            height=int(cfg["video"]["height"])
        )

        self.p.set_stage("subtitles", Status.COMPLETED, done=len(cues), total=len(cues))
        log.info("Subtitles generated: %d cues", len(cues))

    # ---------------- Stage 9: Final Render ----------------
    def _run_render(self) -> None:
        if self._cancel_flag: raise PipelineCancelled()
        self.p.activity("Stage 9/9: Assembling final video with FFmpeg...")
        self.p.set_stage("render", Status.RUNNING)

        def on_prog(done, total, msg):
            self.p.activity(f"Rendering: {msg} ({done}/{total})")
            self.p.progress("render", done, total)

        try:
            stage_models = self.p.settings.get("stage_models", {})
            if stage_models.get("render"):
                self.p.settings.setdefault("rendering", {})["encoder"] = stage_models["render"]
            mp4_path = render_project(self.p, draft=False, progress=on_prog, cancel=self.is_cancelled)
            self.p.data.outputs["final"] = self.p.rel(mp4_path)
            self.p.set_stage("render", Status.COMPLETED, done=1, total=1)
            log.info("Final video rendered: %s", mp4_path)
        except Exception as e:
            if self._cancel_flag or "cancelled" in str(e).lower():
                self.p.set_stage("render", Status.PENDING)
                raise PipelineCancelled()
            self.p.set_stage("render", Status.FAILED, error=str(e))
            raise
