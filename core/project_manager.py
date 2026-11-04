"""Project persistence: one directory per video, atomic JSON writes, resumable state."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import PROJECTS_DIR, ROOT, deep_merge, load_settings
from core.logging_setup import log
from core.models import STAGES, ProjectData, Scene, StageState, Status

SUBDIRS = ["script", "scenes", "prompts", "images", "audio", "animation", "subtitles", "temp", "final", "research"]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def slugify(text: str, max_words: int = 5) -> str:
    stop = {"why", "how", "the", "a", "an", "in", "of", "to", "is", "are", "does", "do", "what", "and", "for", "on", "becomes"}
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    keep = [w for w in words if w not in stop] or words or ["project"]
    return "_".join(keep[:max_words])[:48]


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # file briefly locked by a reader on Windows
            import time
            time.sleep(0.1)
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class Project:
    """Wrapper around a project directory. Thread-safe for one writer + many readers."""

    _locks: dict[str, threading.RLock] = {}

    def __init__(self, project_id: str):
        self.id = project_id
        self.dir = PROJECTS_DIR / project_id
        self.lock = Project._locks.setdefault(project_id, threading.RLock())
        self.data = ProjectData(**read_json(self.dir / "project.json"))
        self._scenes: list[Scene] | None = None

    @property
    def project_id(self) -> str:
        return self.id

    # ---------- creation / listing ----------
    @classmethod
    def create(cls, topic: str, overrides: dict | None = None, project_id: str | None = None) -> "Project":
        base = project_id or slugify(topic)
        pid, n = base, 2
        while (PROJECTS_DIR / pid).exists():
            pid, n = f"{base}_{n}", n + 1
        pdir = PROJECTS_DIR / pid
        for sub in SUBDIRS:
            (pdir / sub).mkdir(parents=True, exist_ok=True)
        data = ProjectData(id=pid, topic=topic.strip(), created_at=now(), started_at=now(), settings=overrides or {})
        atomic_write_json(pdir / "project.json", data.model_dump(mode="json"))
        log.info("Project created: %s", pid)
        return cls(pid)

    @staticmethod
    def list_all() -> list[dict]:
        out = []
        if not PROJECTS_DIR.exists():
            return out
        for d in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            pj = d / "project.json"
            if pj.exists():
                try:
                    data = read_json(pj)
                    item = {k: data.get(k) for k in (
                        "id", "topic", "title", "created_at", "updated_at", "started_at", "completed_at",
                        "total_duration_seconds", "stage_durations", "state", "activity", "outputs"
                    )}
                    # Expose creation mode so each Stage Studio lists only its own projects.
                    item["project_mode"] = (
                        (data.get("settings") or {}).get("project_mode") or "documentary"
                    )
                    out.append(item)
                except Exception:  # corrupt file should not break listing
                    continue
        return out

    # ---------- settings ----------
    @property
    def settings(self) -> dict:
        """Effective settings snapshot. Persist edits through data.settings, then save()."""
        return deep_merge(load_settings(), self.data.settings)

    # ---------- paths ----------
    @property
    def root(self) -> Path:
        return self.dir

    def path(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.dir.resolve()).as_posix()

    def abs(self, rel: str | None) -> Path | None:
        return self.dir / rel if rel else None

    # ---------- persistence ----------
    def save(self) -> None:
        with self.lock:
            self.data.updated_at = now()
            atomic_write_json(self.path("project.json"), self.data.model_dump(mode="json"))

    def reload(self) -> None:
        with self.lock:
            self.data = ProjectData(**read_json(self.path("project.json")))
            self._scenes = None

    @property
    def scenes(self) -> list[Scene]:
        with self.lock:
            if self._scenes is None:
                raw = read_json(self.path("scenes", "scenes.json"), [])
                self._scenes = [Scene(**s) for s in raw]
            return self._scenes

    def is_avatar_enabled(self) -> bool:
        """Return True if avatar/presenter is enabled at project level."""
        settings = self.settings
        s1 = settings.get("avatar_enabled")
        p1 = settings.get("presenter_placement")
        data_s = getattr(self.data, "settings", {}) or {}
        s2 = data_s.get("avatar_enabled")
        p2 = data_s.get("presenter_placement")

        if s1 is False or s2 is False:
            return False
        if p1 in ("none", "off", "disabled", False) or p2 in ("none", "off", "disabled", False):
            return False
        return True

    def clear_clips_cache(self, scene_id: int | None = None) -> int:
        """Clear cached rendered clips in temp/clips_* so that re-renders are completely fresh.
        If scene_id is provided, only clears clips for that scene.
        """
        temp_dir = self.path("temp")
        if not temp_dir.exists():
            return 0
        pattern = f"scene_{scene_id:03d}_*.mp4" if scene_id is not None else "*.mp4"
        count = 0
        for clip_dir in temp_dir.glob("clips_*"):
            if clip_dir.is_dir():
                for clip in clip_dir.glob(pattern):
                    try:
                        clip.unlink(missing_ok=True)
                        count += 1
                    except Exception:
                        pass
        return count

    def sync_avatar_disabled_state(self) -> bool:
        """If avatar is disabled project-wide, enforce is_presenter=False on all scenes and clear avatar cache."""
        if self.is_avatar_enabled():
            return False

        changed = False
        with self.lock:
            if hasattr(self, "data") and isinstance(self.data.settings, dict):
                if self.data.settings.get("presenter_placement") != "none" or self.data.settings.get("avatar_enabled") is not False:
                    self.data.settings["presenter_placement"] = "none"
                    self.data.settings["auto_presenter"] = False
                    self.data.settings["avatar_enabled"] = False
                    changed = True

            scenes = self.scenes
            for sc in scenes:
                was_presenter = getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor") or bool(getattr(sc, "avatar_profile", None))
                if was_presenter:
                    sc.is_presenter = False
                    sc.visual_type = "image"
                    changed = True
                    av_name = getattr(sc, "avatar_profile", None)
                    if av_name:
                        try:
                            from generators.avatar_generator import load_avatar
                            av_obj = load_avatar(av_name)
                            if av_obj and sc.voice_profile == av_obj.get("voice_profile"):
                                proj_vp = (self.data.settings or {}).get("voice_profile") if hasattr(self, "data") else None
                                sc.voice_profile = proj_vp or None
                        except Exception:
                            pass
                        sc.avatar_profile = None
                    if sc.animation:
                        anim_meta = sc.animation.meta or {}
                        prov = str(anim_meta.get("provider", ""))
                        if sc.animation.error or prov in (
                            "fal-ai/latentsync", "fal-ai/sadtalker",
                            "fal-ai/kling-video/v1/standard/ai-avatar",
                            "fal-ai/kling-video/v1/pro/ai-avatar",
                            "local_fallback", "masked_speaker"
                        ):
                            if sc.animation.path:
                                old_vid = self.abs(sc.animation.path)
                                if old_vid and old_vid.exists():
                                    try:
                                        old_vid.unlink(missing_ok=True)
                                    except Exception:
                                        pass
                            sc.animation.status = Status.PENDING
                            sc.animation.path = None
                            sc.animation.meta = {}
                            sc.animation.error = None
                            sc.ai_video = False

            if changed:
                self.clear_clips_cache()
                atomic_write_json(self.path("scenes", "scenes.json"), [s.model_dump(mode="json") for s in scenes])
                self.save()
        return changed

    def set_scenes(self, scenes: list[Scene]) -> None:
        with self.lock:
            self._scenes = scenes
            self.save_scenes()

    def save_scenes(self) -> None:
        with self.lock:
            if not self.is_avatar_enabled():
                for s in self.scenes:
                    if getattr(s, "is_presenter", False) or s.visual_type in ("talking_head", "talking_actor") or bool(getattr(s, "avatar_profile", None)):
                        s.is_presenter = False
                        s.visual_type = "image"
                        av_name = getattr(s, "avatar_profile", None)
                        if av_name:
                            try:
                                from generators.avatar_generator import load_avatar
                                av_obj = load_avatar(av_name)
                                if av_obj and s.voice_profile == av_obj.get("voice_profile"):
                                    proj_vp = (self.data.settings or {}).get("voice_profile") if hasattr(self, "data") else None
                                    s.voice_profile = proj_vp or None
                            except Exception:
                                pass
                            s.avatar_profile = None
                        if s.animation and (s.animation.meta or {}).get("provider") in (
                            "fal-ai/latentsync", "fal-ai/sadtalker",
                            "fal-ai/kling-video/v1/standard/ai-avatar",
                            "fal-ai/kling-video/v1/pro/ai-avatar",
                            "local_fallback", "masked_speaker"
                        ):
                            s.animation.status = Status.PENDING
                            s.animation.path = None
                            s.animation.meta = {}
                            s.animation.error = None
                            s.ai_video = False
            atomic_write_json(self.path("scenes", "scenes.json"), [s.model_dump(mode="json") for s in self.scenes])

    def scene(self, scene_id: int) -> Scene:
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        raise KeyError(f"scene {scene_id} not found")

    def get_scene(self, scene_id: int) -> Optional[Scene]:
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        return None

    def active_scenes(self) -> list[Scene]:
        return [s for s in self.scenes if s.enabled]

    # ---------- stage state ----------
    def stage(self, name: str) -> StageState:
        return self.data.stages.setdefault(name, StageState())

    def set_stage(
        self,
        name: str,
        status: Status,
        error: str | None = None,
        done: int | None = None,
        total: int | None = None,
        duration_override: float | None = None,
    ) -> None:
        with self.lock:
            st = self.stage(name)
            current_dt = datetime.now()
            current_time = current_dt.isoformat(timespec="seconds")
            if status == Status.RUNNING:
                # Always reset started_at when transitioning into RUNNING from another state
                if st.status != Status.RUNNING or not st.started_at:
                    st.started_at = current_dt.isoformat(timespec="milliseconds")
            elif status == Status.COMPLETED:
                st.completed_at = current_time
                if duration_override is not None:
                    st.duration_seconds = max(0.1, round(float(duration_override), 1))
                elif st.started_at:
                    try:
                        t_start = datetime.fromisoformat(st.started_at)
                        elapsed = (current_dt - t_start).total_seconds()
                        # If started_at was from an earlier session (>6h gap) and stage was re-run without RUNNING reset, avoid bogus multi-hour wall-clock jump
                        if elapsed >= 0:
                            st.duration_seconds = max(0.1, round(elapsed, 1))
                    except Exception:
                        pass
                self.data.stage_durations[name] = st.duration_seconds
                # Keep stage_durations ordered by canonical STAGES sequence
                ordered = {s: self.data.stage_durations[s] for s in STAGES if s in self.data.stage_durations}
                for k, v in self.data.stage_durations.items():
                    if k not in ordered:
                        ordered[k] = v
                self.data.stage_durations = ordered
                self.data.total_duration_seconds = round(sum(self.data.stage_durations.values()), 1)

            st.status = status
            st.error = error
            if done is not None:
                st.done = done
            if total is not None:
                st.total = total
            st.updated_at = current_time
            self.save()

    def progress(self, name: str, done: int, total: int, activity: str | None = None) -> None:
        with self.lock:
            st = self.stage(name)
            st.done, st.total = done, total
            if activity is not None:
                self.data.activity = activity
            self.save()

    def invalidate(self, *stages: str) -> None:
        """Mark stages (and everything after the earliest) as PENDING."""
        with self.lock:
            idx = min(STAGES.index(s) for s in stages)
            for s in STAGES[idx:]:
                if self.stage(s).status != Status.SKIPPED or s in stages:
                    self.stage(s).status = Status.PENDING
                    self.stage(s).error = None
            self.save()

    def activity(self, text: str) -> None:
        with self.lock:
            self.data.activity = text
            self.save()

    # ---------- misc ----------
    def write_json(self, rel: str, data: Any) -> None:
        atomic_write_json(self.path(rel), data)

    def read_json(self, rel: str, default: Any = None) -> Any:
        return read_json(self.path(rel), default)

    def read_text(self, rel: str, default: str = "") -> str:
        p = self.path(rel)
        return p.read_text(encoding="utf-8") if p.exists() else default

    def write_text(self, rel: str, text: str) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def delete(self) -> None:
        """Delete this project directory and its content files."""
        Project._locks.pop(self.id, None)
        if not self.dir.exists():
            return

        import gc
        import stat
        import time

        gc.collect()

        def _force_remove_path(path: Path):
            try:
                if path.is_file() or path.is_symlink():
                    try:
                        os.chmod(path, stat.S_IWRITE)
                    except Exception:
                        pass
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    for sub in list(path.iterdir()):
                        _force_remove_path(sub)
                    try:
                        path.rmdir()
                    except Exception:
                        pass
            except Exception:
                pass

        # Step 1: Specifically wipe all cached video clips and temp video files first
        self.clear_video_cache()

        # Step 2: Recursive force wipe
        for attempt in range(5):
            gc.collect()
            _force_remove_path(self.dir)
            if not self.dir.exists():
                break
            time.sleep(0.2)

        # Step 3: If Windows still holds a lingering lock on some file, move to temp trash
        if self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)
        if self.dir.exists():
            try:
                trash_name = f".deleted_{int(time.time())}_{self.id}"
                trash_dir = self.dir.parent / trash_name
                self.dir.rename(trash_dir)
                shutil.rmtree(trash_dir, ignore_errors=True)
            except Exception:
                pass

        log.info("Project deleted: %s", self.id)

    def clear_video_cache(self) -> int:
        """Purge all intermediate rendered video clips and temporary video tracks to free disk space."""
        import gc
        import stat
        gc.collect()
        cleared_bytes = 0

        # Target temp clips, intermediate video tracks, and partial renders
        targets = [
            self.dir / "temp",
            self.dir / "animation",
        ]
        for tdir in targets:
            if not tdir.exists():
                continue
            for f in list(tdir.rglob("*")):
                if f.is_file() and (f.suffix.lower() in [".mp4", ".ts", ".mkv", ".mov", ".avi", ".tmp"] or "_clips_" in f.parent.name or "clips_" in f.parent.name):
                    try:
                        cleared_bytes += f.stat().st_size
                        os.chmod(f, stat.S_IWRITE)
                        f.unlink(missing_ok=True)
                    except Exception:
                        pass
            # Clean up empty subdirectories in temp
            for sub in sorted(list(tdir.glob("clips_*")), reverse=True):
                try:
                    shutil.rmtree(sub, ignore_errors=True)
                except Exception:
                    pass

        log.info("Cleared %d bytes of video cache for project %s", cleared_bytes, self.id)
        return cleared_bytes

    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """Completely delete the project directory and its content files."""
        pdir = PROJECTS_DIR / project_id
        if not pdir.exists():
            return False
        cls._locks.pop(project_id, None)

        # Also purge any Remotion renders associated with this project
        try:
            remotion_renders = ROOT / "remotion-video" / "out" / "renders"
            if remotion_renders.exists():
                for rf in remotion_renders.glob(f"*{project_id}*"):
                    try:
                        rf.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            p = cls(project_id)
            p.delete()
        except Exception as e:
            log.warning("Project delete exception for %s: %s; falling back to direct removal", project_id, e)
            import gc
            import stat
            import time
            gc.collect()

            def _remove_readonly(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            for _ in range(3):
                shutil.rmtree(pdir, onerror=_remove_readonly)
                if not pdir.exists():
                    break
                time.sleep(0.2)
            if pdir.exists():
                shutil.rmtree(pdir, ignore_errors=True)
            if pdir.exists():
                try:
                    trash_dir = pdir.parent / f".deleted_{int(time.time())}_{project_id}"
                    pdir.rename(trash_dir)
                    shutil.rmtree(trash_dir, ignore_errors=True)
                except Exception:
                    pass

        return not pdir.exists()
