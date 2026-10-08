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

from core.config import PROJECTS_DIR, deep_merge, load_settings
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
                    out.append({k: data.get(k) for k in (
                        "id", "topic", "title", "created_at", "updated_at", "started_at", "completed_at",
                        "total_duration_seconds", "stage_durations", "state", "activity", "outputs"
                    )})
                except Exception:  # corrupt file should not break listing
                    continue
        return out

    # ---------- settings ----------
    @property
    def settings(self) -> dict:
        return deep_merge(load_settings(), self.data.settings)

    # ---------- paths ----------
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

    def set_scenes(self, scenes: list[Scene]) -> None:
        with self.lock:
            self._scenes = scenes
            self.save_scenes()

    def save_scenes(self) -> None:
        with self.lock:
            atomic_write_json(self.path("scenes", "scenes.json"), [s.model_dump(mode="json") for s in self.scenes])

    def scene(self, scene_id: int) -> Scene:
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        raise KeyError(f"scene {scene_id} not found")

    def active_scenes(self) -> list[Scene]:
        return [s for s in self.scenes if s.enabled]

    # ---------- stage state ----------
    def stage(self, name: str) -> StageState:
        return self.data.stages.setdefault(name, StageState())

    def set_stage(self, name: str, status: Status, error: str | None = None, done: int | None = None, total: int | None = None) -> None:
        with self.lock:
            st = self.stage(name)
            current_time = now()
            if status == Status.RUNNING and not st.started_at:
                st.started_at = current_time
            elif status == Status.COMPLETED:
                st.completed_at = current_time
                if st.started_at:
                    try:
                        t_start = datetime.fromisoformat(st.started_at)
                        t_end = datetime.fromisoformat(current_time)
                        st.duration_seconds = max(0.0, round((t_end - t_start).total_seconds(), 1))
                    except Exception:
                        pass
                self.data.stage_durations[name] = st.duration_seconds
                self.data.total_duration_seconds = round(sum(self.data.stage_durations.values()), 1)

            st.status = status
            st.error = error
            if done is not None:
                st.done = done
            if total is not None:
                st.total = total
            st.updated_at = current_time
            self.save()

    def progress(self, name: str, done: int, total: int) -> None:
        with self.lock:
            st = self.stage(name)
            st.done, st.total = done, total
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

        def _remove_readonly(func, path, exc_info):
            import stat
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        for _ in range(3):
            try:
                shutil.rmtree(self.dir, onerror=_remove_readonly)
                break
            except Exception:
                import time
                time.sleep(0.2)
        if self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)
        log.info("Project deleted: %s", self.id)

    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """Completely delete the project directory and its content files."""
        pdir = PROJECTS_DIR / project_id
        if not pdir.exists():
            return False
        cls._locks.pop(project_id, None)
        try:
            p = cls(project_id)
            p.delete()
        except Exception:
            def _remove_readonly(func, path, exc_info):
                import stat
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(pdir, onerror=_remove_readonly)
            if pdir.exists():
                shutil.rmtree(pdir, ignore_errors=True)
        return not pdir.exists()
