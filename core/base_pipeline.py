"""Base Pipeline class providing lifecycle management, cancellation, stage tracking and shared utilities."""
from __future__ import annotations

import os
import random
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.config import ROOT, get_secret, load_providers
from core.logging_setup import log
from core.models import STAGES, Asset, Scene, Status
from core.project_manager import Project, now
from core.versioning import record_stage_version
from generators.subtitle_generator import build_cues, write_ass, write_srt
from generators.voice_generator import default_profile_name, load_profile, synthesize
from providers.llm.base import LLMProvider
from rendering.ffmpeg_renderer import project_timeline, render_project


class PipelineCancelled(Exception):

    pass


def apply_presenter_placement(

    scenes: list[Scene],

    placement: str = "none",

    default_avatar: Optional[str] = None

) -> list[Scene]:

    """Applies presenter placement strategy to a list of scenes.



    Strategies:

      - 'none': No presenter scenes (pure visuals / b-roll)

      - 'intro': Scene 1 only (opening hook)

      - 'intro_outro': Scene 1 + final scene (hook + call to action)

      - 'intro_middle_outro': Scene 1 + midpoint scene (~50%) + final scene

      - 'chapters': First scene of each unique chapter/section

      - 'all': Presenter on all scenes

    """

    if not scenes:

        return scenes



    n = len(scenes)

    target_indices: set[int] = set()

    strat = (placement or "none").strip().lower()



    if strat in ("none", "false", "", "off", "disabled"):

        target_indices = set()

    elif strat in ("intro", "beginning", "hook", "scene_1", "true", "start"):

        target_indices = {0}

    elif strat in ("intro_outro", "beginning_end", "start_end", "intro_end"):

        target_indices = {0}

        if n > 1:

            target_indices.add(n - 1)

    elif strat in ("intro_middle_outro", "beginning_middle_end", "start_middle_end", "middle_and_end", "three_point"):

        target_indices = {0}

        if n >= 3:

            target_indices.add(n // 2)

        if n > 1:

            target_indices.add(n - 1)

    elif strat in ("chapters", "sections", "chapter_intros"):

        seen_sections: set[str] = set()

        for idx, sc in enumerate(scenes):

            sec = (getattr(sc, "section", "") or "").strip()

            if sec and sec not in seen_sections:

                seen_sections.add(sec)

                target_indices.add(idx)

        if not target_indices:

            target_indices = {0}

    elif strat in ("all", "all_scenes", "full"):

        target_indices = set(range(n))

    else:

        target_indices = {0}



    for idx, sc in enumerate(scenes):

        if idx in target_indices:

            sc.is_presenter = True

            sc.visual_type = "talking_head"

            if default_avatar:

                sc.avatar_profile = default_avatar

                try:

                    from generators.avatar_generator import load_avatar

                    av_obj = load_avatar(default_avatar)

                    if av_obj and av_obj.get("voice_profile"):

                        sc.voice_profile = av_obj["voice_profile"]

                except Exception:

                    pass

        else:

            if getattr(sc, "is_presenter", False):

                sc.is_presenter = False

                if sc.visual_type == "talking_head":

                    sc.visual_type = "image"



    return scenes






class BasePipeline:
    """Orchestrates an end-to-end video project."""



    def __init__(self, project: Project, stop_at: Optional[str] = None):

        self.p = project

        self.stop_at = stop_at

        self._cancel_flag = False

        self._lock = threading.RLock()

        self._stage_models_override: dict[str, str] = {}



    def update_stage_models(self, new_models: dict[str, str]) -> None:

        """Dynamically update models for upcoming stages or active scene iterations."""

        with self._lock:

            self._stage_models_override.update(new_models)

            with self.p.lock:


                self.p.data.settings.setdefault("stage_models", {}).update(new_models)

                if "images" in new_models:

                    model_val = new_models["images"]

                    if model_val not in ("stock", "stock_photos", "placeholder"):


                        self.p.data.settings.setdefault("images", {})["checkpoint"] = model_val

                    else:


                        self.p.data.settings.setdefault("images", {})["provider"] = model_val

                if "voice" in new_models:

                    v_val = new_models["voice"]

                    if v_val not in ("bluemagpie", "elevenlabs", "edge", "sapi", "openai_tts", "http_clone", "voai"):


                        self.p.data.settings["voice_profile"] = v_val

                        try:

                            from generators.voice_generator import load_profile

                            vp_obj = load_profile(v_val)

                            vp_prov = vp_obj.get("provider")

                            if vp_prov:

                                self._stage_models_override["voice"] = vp_prov


                                self.p.data.settings.setdefault("stage_models", {})["voice"] = vp_prov

                        except Exception:

                            pass

                    else:

                        from generators.voice_generator import list_profiles, load_profile

                        cur_prof_name = self.p.data.settings.get("voice_profile")

                        cur_prov = None

                        if cur_prof_name:

                            try:

                                cur_prov = load_profile(cur_prof_name).get("provider")

                            except Exception:

                                pass

                        if cur_prov != v_val:

                            for vp in list_profiles():

                                if vp.get("provider") == v_val:


                                    self.p.data.settings["voice_profile"] = vp["name"]

                                    break

                if "render" in new_models:

                    self.p.data.settings.setdefault("rendering", {})["encoder"] = new_models["render"]

                self.p.save()

            log.info("Pipeline[%s] dynamically updated stage_models: %s", self.p.id, new_models)



    def get_stage_model(self, stage_name: str, default: str | None = None) -> str | None:

        """Retrieve the current model configured for a given stage, checking dynamic overrides first."""

        with self._lock:

            if stage_name in self._stage_models_override:

                return self._stage_models_override[stage_name]

        with self.p.lock:

            sm = self.p.data.settings.get("stage_models", {}) or self.p.settings.get("stage_models", {})

            return sm.get(stage_name, default)



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

            if getattr(self.p, "project_mode", "documentary") != "short_drama":
                self._run_music()
                if self._check_stop("music"): return

            self._run_animation()

            if self._check_stop("animation"): return



            self._run_subtitles()

            if self._check_stop("subtitles"): return



            self._run_render()



            with self.p.lock:

                self.p.data.state = "completed"

                self.p.data.completed_at = now()

                for s_name in STAGES:

                    st_obj = self.p.data.stages.get(s_name)

                    if st_obj and st_obj.duration_seconds > 0:

                        self.p.data.stage_durations[s_name] = st_obj.duration_seconds

                self.p.data.total_duration_seconds = round(sum(self.p.data.stage_durations.values()), 1)

                self.p.data.activity = "Video generation complete!"

                self.p.save()



            # Calculate and save accurate cost breakdown for each stage and total sum

            try:

                from core.pricing import calculate_and_update_project_costs

                cost_summary = calculate_and_update_project_costs(self.p)

                total_usd = cost_summary.get("total_cost_usd", 0.0)

                is_cloud = cost_summary.get("is_cloud_accelerated", False)

                stage_costs = cost_summary.get("stage_costs", {})

                parts = [f"{k}: ${v:.4f}" for k, v in stage_costs.items() if v > 0]

                breakdown_str = ", ".join(parts) if parts else "100% Local GPU Free"

                log.info("Project '%s' finished successfully (%.1fs). Cloud Cost: $%.4f (%s)",

                         self.p.id, self.p.data.total_duration_seconds, total_usd, breakdown_str)

                with self.p.lock:

                    if is_cloud:

                        self.p.data.activity = f"Complete ({self.p.data.total_duration_seconds:.1f}s)! Cloud Cost: ${total_usd:.4f} ({breakdown_str})"

                    else:

                        self.p.data.activity = f"Video generation complete in {self.p.data.total_duration_seconds:.1f}s! (Local GPU: $0.00)"

                    self.p.save()

            except Exception as cost_err:

                log.warning("Cost calculation note: %s", cost_err)



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

            "music": self._run_music,

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

            self.p.stage(stage_name).duration_seconds = 0.0

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

                self.p.set_scenes([])

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

            try:

                from core.pricing import calculate_and_update_project_costs

                calculate_and_update_project_costs(self.p)

            except Exception as ex:

                log.debug("run_stage cost update note: %s", ex)

            st_dur = self.p.stage(stage_name).duration_seconds

            with self.p.lock:

                self.p.data.state = "paused"

                self.p.data.activity = f"Stage '{stage_name}' complete in {st_dur:.1f}s! Ready for tuning & review."

                self.p.save()

            log.info("Stage '%s' completed successfully in isolation (%.1fs)", stage_name, st_dur)

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



    def rerender_voice_and_video(

        self,

        voice_profile: Optional[str] = None,

        tts_provider: Optional[str] = None,

        scope: str = "all",

        scene_ids: Optional[list[int]] = None,

    ) -> None:

        """Re-synthesize voice narration (all or selected scenes), re-sync subtitles, and re-render the final 1080p video."""

        with self._lock:

            self._cancel_flag = False

            self.p.data.state = "running"

            self.p.data.error = None

            self.p.data.activity = "Preparing voice re-synthesis & video update..."



            # Update voice profile & TTS engine on project settings

            if voice_profile:


                self.p.data.settings["voice_profile"] = voice_profile

                if not tts_provider:

                    try:

                        vp_obj = load_profile(voice_profile)

                        if vp_obj and vp_obj.get("provider"):

                            tts_provider = vp_obj["provider"]

                            voice_profile = vp_obj["name"]


                            self.p.data.settings["voice_profile"] = voice_profile

                    except Exception:

                        pass



            if tts_provider:

                self._stage_models_override["voice"] = tts_provider


                self.p.data.settings.setdefault("stage_models", {})["voice"] = tts_provider



            target_prof_name = voice_profile or self.p.data.settings.get("voice_profile") or default_profile_name(self.p.settings)

            target_prof = load_profile(target_prof_name)

            target_prov = tts_provider or self.get_stage_model("voice") or target_prof.get("provider", "bluemagpie")

            target_voice_id = target_prof.get("voice_id") or target_prof.get("voice") or ""



            # Preserve existing scene audio clips as takes before re-generating

            try:

                from core.versioning import ensure_initial_voice_take

                for sc in self.p.scenes:

                    ensure_initial_voice_take(self.p, sc.scene_id)

                record_stage_version(self.p, "voice")

            except Exception as ex:

                log.debug("Archive voice takes before rerender note: %s", ex)



            active_sc = self.p.active_scenes()

            scene_id_set = set(scene_ids or [])



            invalidated_count = 0

            for s in active_sc:

                should_regen = True

                if scope == "custom" and scene_id_set:

                    should_regen = s.scene_id in scene_id_set

                elif scope in ("mismatched", "outdated"):

                    meta = s.audio.meta if s.audio and s.audio.meta else {}

                    cur_prov = meta.get("provider", "")

                    cur_vid = meta.get("voice_id", "")

                    cur_prof = s.voice_profile or meta.get("voice") or meta.get("profile") or ""

                    audio_f = self.p.abs(s.audio.path) if s.audio and s.audio.path else self.p.path("audio", f"{s.tag}.wav")

                    is_audio_missing = not audio_f.exists() or audio_f.stat().st_size < 1000

                    is_pending = s.audio.status != Status.COMPLETED

                    is_text_outdated = bool(meta.get("text_outdated"))

                    dur = float(s.audio_duration or 0.0)

                    is_duration_invalid = dur <= 0.1

                    is_duration_mismatch = False

                    if meta.get("duration"):

                        try:

                            if abs(float(meta["duration"]) - dur) > 0.5:

                                is_duration_mismatch = True

                        except (ValueError, TypeError):

                            pass

                    is_text_mismatch = False

                    if meta.get("previous_narration") and meta.get("previous_narration").strip() != s.narration.strip():

                        is_text_mismatch = True

                    if meta.get("text") and meta.get("text").strip() != s.narration.strip():

                        is_text_mismatch = True

                    if meta.get("narration") and meta.get("narration").strip() != s.narration.strip():

                        is_text_mismatch = True

                    is_voice_mismatch = False

                    if cur_prov != target_prov:

                        is_voice_mismatch = True

                    elif target_prov in ("elevenlabs", "voai") and target_voice_id and cur_vid != target_voice_id:

                        is_voice_mismatch = True

                    elif target_prof_name and cur_prof != target_prof_name:

                        is_voice_mismatch = True

                    if is_pending or is_text_outdated or is_audio_missing or is_duration_invalid or is_duration_mismatch or is_text_mismatch or is_voice_mismatch:

                        should_regen = True

                    else:

                        should_regen = False



                if should_regen:

                    if voice_profile:

                        s.voice_profile = voice_profile

                    s.audio.status = Status.PENDING

                    s.audio.error = None

                    invalidated_count += 1



            if scope == "custom" and invalidated_count == 0 and scene_id_set:

                raise ValueError(f"No active scenes matched custom range: {sorted(list(scene_id_set))}")

            elif scope in ("mismatched", "outdated") and invalidated_count == 0:

                log.info("Mismatched scope: all %d scenes already match voice and narration. Keeping existing audio.", len(active_sc))



            self.p.save_scenes()

            done_voice = sum(1 for s in active_sc if s.audio.status == Status.COMPLETED)

            self.p.set_stage("voice", Status.PENDING, done=done_voice, total=len(active_sc))

            if scope == "all" or done_voice == 0:

                self.p.stage("voice").duration_seconds = 0.0



            (self.p.path("subtitles", "subtitles.srt")).unlink(missing_ok=True)

            (self.p.path("subtitles", "subtitles.ass")).unlink(missing_ok=True)

            self.p.set_stage("subtitles", Status.PENDING)

            self.p.set_stage("render", Status.PENDING)

            self.p.save()



        try:

            log.info(

                "Re-rendering voice (%d/%d scenes, profile=%s, provider=%s) & updating video for '%s'",

                invalidated_count, len(self.p.active_scenes()), target_prof_name, target_prov, self.p.id

            )

            self._run_voice()

            if self._cancel_flag:

                raise PipelineCancelled()

            try:

                record_stage_version(self.p, "voice")

            except Exception:

                pass



            
            # If any scene has a presenter / talking avatar, ensure avatar animation video matches the new audio
            presenter_scenes = [s for s in self.p.scenes if (getattr(s, "is_presenter", False) or s.visual_type in ("talking_head", "talking_actor"))]
            if presenter_scenes:
                from generators.avatar_generator import generate_talking_avatar, load_avatar
                for ps in presenter_scenes:
                    if self._cancel_flag: raise PipelineCancelled()
                    audio_f = self.p.abs(ps.audio.path) if (ps.audio and ps.audio.path) else self.p.path("audio", f"{ps.tag}.wav")
                    if not audio_f or not audio_f.exists():
                        continue
                    av_name = getattr(ps, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar")
                    av_prof = load_avatar(av_name)
                    if not av_prof:
                        continue
                    out_clip = self.p.path("animation", f"{ps.tag}.mp4")
                    try:
                        self.p.activity(f"Re-generating talking avatar for Scene {ps.scene_id} to match new audio narration...")
                        meta = generate_talking_avatar(audio_f, av_prof, out_clip)
                        ps.animation.status = Status.COMPLETED
                        ps.animation.path = self.p.rel(out_clip)
                        ps.animation.meta = meta
                        ps.animation.error = None
                        ps.ai_video = True
                    except Exception as ex:
                        log.warning("Could not regenerate avatar for scene %d: %s", ps.scene_id, ex)
                self.p.save_scenes()

            self._run_subtitles()

            if self._cancel_flag:

                raise PipelineCancelled()



            self._run_render()



            with self.p.lock:

                self.p.data.state = "completed"

                self.p.data.completed_at = now()

                for s_name in STAGES:

                    st_obj = self.p.data.stages.get(s_name)

                    if st_obj and st_obj.duration_seconds > 0:

                        self.p.data.stage_durations[s_name] = st_obj.duration_seconds

                self.p.data.total_duration_seconds = round(sum(self.p.data.stage_durations.values()), 1)

                self.p.data.activity = "Voice re-rendered & 1080p video updated!"

                self.p.save()



            try:

                from core.pricing import calculate_and_update_project_costs

                cost_summary = calculate_and_update_project_costs(self.p)

                total_usd = cost_summary.get("total_cost_usd", 0.0)

                with self.p.lock:

                    self.p.data.activity = (

                        f"Voice & Video Updated! Total Time: {self.p.data.total_duration_seconds:.1f}s "

                        f"• Cloud Cost: ${total_usd:.4f}"

                    )

                    self.p.save()

            except Exception as cost_err:

                log.debug("rerender_voice_and_video cost update note: %s", cost_err)



        except PipelineCancelled:

            with self.p.lock:

                self.p.data.state = "paused"

                self.p.data.activity = "Voice & video re-render cancelled by user"

                self.p.save()

        except Exception as e:

            with self.p.lock:

                self.p.data.state = "failed"

                self.p.data.error = str(e)

                self.p.data.activity = f"Voice & video re-render failed: {e}"

                self.p.save()

            log.exception("rerender_voice_and_video failed for '%s': %s", self.p.id, e)

            raise



    def ensure_consistent_project_voice(self, target_profile: Optional[str] = None) -> None:

        """Ensures that all active scene audio tracks strictly match the project's configured voice profile.

        If a scene has an existing take generated with the target voice profile, activates/restores it.

        If any scenes lack audio or are mismatched, synthesizes them with the target profile and syncs subtitles.

        """

        target = target_profile or self.p.data.settings.get("voice_profile") or self.p.settings.get("voice_profile") or default_profile_name(self.p.settings)

        if not target:

            return




        self.p.data.settings["voice_profile"] = target



        from generators.voice_generator import load_profile

        vp_obj = load_profile(target)

        target_provider = (

            (vp_obj.get("provider") if vp_obj else None)

            or self.get_stage_model("voice")

            or (self.p.data.settings.get("stage_models") or {}).get("voice")

            or "bluemagpie"

        )


        self.p.data.settings.setdefault("stage_models", {})["voice"] = target_provider



        scenes = self.p.active_scenes()

        mismatched_scenes: list[Scene] = []

        needs_subtitle_refresh = False



        for sc in scenes:

            if not sc.voice_profile or sc.voice_profile != target:

                sc.voice_profile = target



            audio_f = self.p.abs(sc.audio.path) if (sc.audio and sc.audio.path) else self.p.path("audio", f"{sc.tag}.wav")

            meta = (sc.audio.meta if sc.audio else {}) or {}

            cur_voice = meta.get("voice") or meta.get("profile") or sc.voice_profile

            cur_prov = meta.get("provider")



            is_text_outdated = bool((meta or {}).get("text_outdated"))

            is_valid = audio_f and audio_f.exists() and audio_f.stat().st_size > 1000 and cur_voice == target and (cur_prov == target_provider or not target_provider) and not is_text_outdated

            if not is_valid:

                # Check existing takes for a take synthesized with target voice

                takes = meta.get("takes", [])

                matching_take = None

                for tk in reversed(takes):

                    if tk.get("voice") == target:

                        tk_path = self.p.abs(tk.get("path"))

                        if tk_path and tk_path.exists() and tk_path.stat().st_size > 1000:

                            matching_take = tk

                            break

                if matching_take:

                    import shutil

                    tk_path = self.p.abs(matching_take["path"])

                    audio_f.parent.mkdir(parents=True, exist_ok=True)

                    try:

                        shutil.copy2(tk_path, audio_f)

                    except Exception:

                        pass

                    sc.audio.path = self.p.rel(audio_f)

                    sc.audio.status = Status.COMPLETED

                    sc.audio.error = None

                    sc.audio_duration = matching_take.get("duration_seconds")

                    sc.voice_profile = target

                    meta["active_take"] = matching_take.get("take")

                    meta["voice"] = target

                    meta["profile"] = target

                    meta["provider"] = matching_take.get("provider", target_provider)

                    sc.audio.meta = meta

                    needs_subtitle_refresh = True

                else:

                    sc.voice_profile = target

                    sc.audio.status = Status.PENDING

                    sc.audio.error = None

                    mismatched_scenes.append(sc)



        self.p.save_scenes()



        if mismatched_scenes:

            log.info(

                "Ensuring voice profile consistency for project '%s': synthesizing %d scenes with '%s' (%s)...",

                self.p.id, len(mismatched_scenes), target, target_provider

            )

            self._run_voice()

            self._run_subtitles()

        elif needs_subtitle_refresh:

            self._run_subtitles()



    def rerender_avatar_clips_and_video(

        self,

        avatar_profile: Optional[str] = None,

        scene_ids: Optional[list[int]] = None,

        engine: Optional[str] = None,

        voice_profile: Optional[str] = None,

        voice_scope: str = "all",

    ) -> None:

        """Re-generate human avatar presenter clips (and optionally update voice narration) and update the final 1080p video."""

        with self._lock:

            self._cancel_flag = False

            self.p.data.state = "running"

            self.p.data.error = None

            self.p.data.activity = "Preparing human avatar clip replacement & video update..."



            if avatar_profile:


                self.p.data.settings["default_avatar"] = avatar_profile



            # Handle Voice Profile update alongside avatar

            has_voice_update = bool(voice_profile and voice_profile.strip() and voice_profile != "keep")

            if has_voice_update:


                self.p.data.settings["voice_profile"] = voice_profile

                try:

                    from generators.voice_generator import load_profile

                    vp_obj = load_profile(voice_profile)

                    if vp_obj and vp_obj.get("provider"):

                        tts_prov = vp_obj["provider"]


                        self.p.data.settings.setdefault("stage_models", {})["voice"] = tts_prov

                        self._stage_models_override["voice"] = tts_prov

                except Exception as ex:

                    log.warning("Could not resolve voice provider for '%s': %s", voice_profile, ex)

            else:

                project_voice_profile = self.p.data.settings.get("voice_profile") or self.p.settings.get("voice_profile") or default_profile_name(self.p.settings)

                if project_voice_profile:


                    self.p.data.settings["voice_profile"] = project_voice_profile



            active_sc = self.p.active_scenes()

            presenter_scenes = [s for s in active_sc if (getattr(s, "is_presenter", False) or s.visual_type == "talking_head")]



            if scene_ids:

                target_scenes = [s for s in presenter_scenes if s.scene_id in set(scene_ids)]

            else:

                target_scenes = presenter_scenes



            if not target_scenes:

                log.warning("No presenter scenes found to replace avatar clips in project '%s'", self.p.id)

                self.p.data.state = "completed"

                self.p.data.activity = "No avatar presenter scenes found to replace."

                self.p.save()

                return



            if has_voice_update:

                try:

                    from core.versioning import ensure_initial_voice_take, record_stage_version

                    for sc in self.p.scenes:

                        ensure_initial_voice_take(self.p, sc.scene_id)

                    record_stage_version(self.p, "voice")

                except Exception as ex:

                    log.debug("Archive voice takes note: %s", ex)



                # Determine which scenes to re-synthesize

                voice_target_scenes = target_scenes if voice_scope == "presenter" else active_sc

                for sc in voice_target_scenes:

                    sc.voice_profile = voice_profile

                    sc.audio.status = Status.PENDING

                    sc.audio.error = None



                done_voice = sum(1 for s in active_sc if s.audio.status == Status.COMPLETED)

                self.p.set_stage("voice", Status.PENDING, done=done_voice, total=len(active_sc))

                (self.p.path("subtitles", "subtitles.srt")).unlink(missing_ok=True)

                (self.p.path("subtitles", "subtitles.ass")).unlink(missing_ok=True)

                self.p.set_stage("subtitles", Status.PENDING)



            for ps in target_scenes:

                if avatar_profile:

                    ps.avatar_profile = avatar_profile

                ps.animation.status = Status.PENDING

                ps.animation.error = None

                clip_file = self.p.abs(ps.animation.path) if (ps.animation and ps.animation.path) else None

                if clip_file and clip_file.exists():

                    try:

                        clip_file.unlink()

                    except Exception:

                        pass



            self.p.save_scenes()

            self.p.set_stage("render", Status.PENDING)

            self.p.save()



        try:

            if has_voice_update:

                log.info(

                    "Re-synthesizing voice for %s scenes with profile '%s' before avatar rendering for '%s'",

                    voice_scope, voice_profile, self.p.id

                )

                self.p.activity(f"Stage 4/9: Re-synthesizing voice narration with {voice_profile}...")

                self._run_voice()

                if self._cancel_flag:

                    raise PipelineCancelled()

                try:

                    record_stage_version(self.p, "voice")

                except Exception:

                    pass

                self.p.activity("Stage 8/9: Re-aligning subtitles to new voice timing...")

                self._run_subtitles()

                if self._cancel_flag:

                    raise PipelineCancelled()

            else:

                # Ensure narration voice consistency across all scenes (presenter and b-roll) before generating clips or rendering

                self.ensure_consistent_project_voice()



            t0 = time.perf_counter()

            log.info(

                "Replacing avatar clips (%d scenes, avatar=%s, engine=%s, voice=%s) & updating video for '%s'",

                len(target_scenes), avatar_profile or "default", engine or "default", voice_profile or "unchanged", self.p.id

            )

            from generators.avatar_generator import generate_talking_avatar, load_avatar



            for idx, ps in enumerate(target_scenes):

                if self._cancel_flag:

                    raise PipelineCancelled()



                audio_file = self.p.abs(ps.audio.path) if (ps.audio and ps.audio.path) else None

                if not audio_file or not os.path.exists(audio_file):

                    cand = self.p.path("audio", f"{ps.tag}.wav")

                    if os.path.exists(cand):

                        audio_file = cand



                if not audio_file or not os.path.exists(audio_file):

                    log.warning("No audio found for presenter scene %d, skipping avatar clip replacement", ps.scene_id)

                    continue



                av_name = getattr(ps, "avatar_profile", None) or (self.p.data.settings or {}).get("default_avatar")

                av_prof = load_avatar(av_name)

                if not av_prof or (not av_prof.get("has_image") and not av_prof.get("has_base_video")):

                    log.warning("No avatar profile found for presenter scene %d", ps.scene_id)

                    continue



                self.p.activity(f"Stage 7/9: Generating human avatar clip {idx + 1}/{len(target_scenes)} (Scene {ps.scene_id}, {av_prof.get('name')})...")

                ps.animation.status = Status.RUNNING

                self.p.save_scenes()



                out_clip = self.p.path("animation", f"{ps.tag}.mp4")

                try:

                    t_av0 = time.perf_counter()

                    meta = generate_talking_avatar(Path(audio_file), av_prof, Path(out_clip), engine=engine)

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

                    log.info("Generated human avatar clip for scene %d in %.1fs", ps.scene_id, av_dur)

                except Exception as ex:

                    log.error("Failed to generate avatar clip for scene %d: %s", ps.scene_id, ex)

                    ps.animation.status = Status.FAILED

                    ps.animation.error = f"Avatar gen error: {ex}"



                self.p.save_scenes()



            if self._cancel_flag:

                raise PipelineCancelled()



            # Re-render final video (only the avatar clips are conformed, everything else is cached)

            self._run_render()



            with self.p.lock:

                self.p.data.state = "completed"

                self.p.data.completed_at = now()

                msg = f"Human avatar clips & voice ('{voice_profile}') replaced & 1080p video updated!" if has_voice_update else "Human avatar clips replaced & 1080p video updated!"

                self.p.data.activity = msg

                self.p.save()



            try:

                from core.pricing import calculate_and_update_project_costs

                calculate_and_update_project_costs(self.p)

            except Exception as cost_err:

                log.debug("Cost calculation note: %s", cost_err)



        except PipelineCancelled:

            with self.p.lock:

                self.p.data.state = "paused"

                self.p.data.activity = "Avatar clip replacement cancelled by user"

                self.p.save()

        except Exception as e:

            with self.p.lock:

                self.p.data.state = "failed"

                self.p.data.error = str(e)

                self.p.data.activity = f"Avatar clip replacement failed: {e}"

                self.p.save()

            log.exception("rerender_avatar_clips_and_video failed for '%s': %s", self.p.id, e)

            raise



    def _check_stop(self, current_stage: str) -> bool:

        if self._cancel_flag:

            raise PipelineCancelled()

        if current_stage == "research" and self.p.data.settings.get("pause_after_research"):

            with self.p.lock:

                self.p.data.state = "paused"

                self.p.data.activity = "Research stage complete with your submitted data. Paused for review before script generation."

                self.p.data.settings["pause_after_research"] = False  # clear so clicking Resume continues

                self.p.save()

            return True

        if self.stop_at == current_stage:

            with self.p.lock:

                self.p.data.state = "paused"

                self.p.data.activity = f"Paused after stage '{current_stage}'. Ready for inspection or next stage."

                self.p.save()

            return True

        return False



    # ---------------- Stage 1: Research ----------------


    def _run_research(self) -> None:
        raise NotImplementedError

    def _run_script(self) -> None:
        raise NotImplementedError

    def _run_scenes(self) -> None:
        raise NotImplementedError

    def _run_prompts(self) -> None:
        raise NotImplementedError

    def _run_images(self) -> None:
        raise NotImplementedError

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

    def _run_music(self) -> None:
        pass

    def _run_animation(self) -> None:
        raise NotImplementedError

    def _run_subtitles(self, *, frame_aware: bool = False, callouts_allowed: bool = True, watermark_default: bool = False) -> None:
        if self._cancel_flag: raise PipelineCancelled()
        t0 = time.perf_counter()
        self.p.activity("Stage 8/9: Building subtitles...")
        self.p.set_stage("subtitles", Status.RUNNING)
        cfg = self.p.settings
        sub_cfg = cfg.get("subtitles", {})
        scenes, slots = project_timeline(self.p)
        pairs = [(sc.narration, sl) for sc, sl in zip(scenes, slots)]
        layout = {"frame_width": int(cfg["video"]["width"]), "frame_height": int(cfg["video"]["height"]), "style": sub_cfg.get("style", "youtube_standard")} if frame_aware else {}
        cues = build_cues(
            pairs,
            max_chars_per_line=int(sub_cfg.get("max_chars_per_line", 42)),
            max_lines=int(sub_cfg.get("max_lines", 2)),
            **layout,
        )
        srt_file = self.p.path("subtitles", "subtitles.srt")
        ass_file = self.p.path("subtitles", "subtitles.ass")
        write_srt(cues, srt_file)
        # Check if fOx Hsiao style motion graphics callouts are enabled (toggleable)
        enabled_motion_callouts = bool(
            callouts_allowed and sub_cfg.get("motion_graphics_callouts", True)
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
            ai_watermark=bool(sub_cfg.get("ai_watermark", watermark_default)),
        )
        elapsed = round(max(0.1, time.perf_counter() - t0), 1)
        callouts_info = f" with {len(callouts)} motion graphic cards" if callouts else " (motion callouts disabled)"
        self.p.set_stage("subtitles", Status.COMPLETED, done=len(cues), total=len(cues), duration_override=elapsed)
        log.info("Subtitles generated in %.1fs: %d dialogue cues%s", elapsed, len(cues), callouts_info)

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
                self.p.data.settings.setdefault("rendering", {})["encoder"] = render_model
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
            if isinstance(e, PipelineCancelled) or self._cancel_flag or "cancelled" in str(e).lower():
                self.p.set_stage("render", Status.PENDING)
                raise PipelineCancelled()
            self.p.set_stage("render", Status.FAILED, error=str(e))
            raise

