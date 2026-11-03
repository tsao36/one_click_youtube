"""Remotion Motion Graphics Renderer for Documentary Mode.

Executes local-first Remotion rendering for validated MotionGraphicsTimeline scenes.
Composites animations over the scene's background image or renders transparent overlay clips.
Guarantees zero-crash fallback: any card failure gracefully falls back to Ken Burns.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status
from core.motion_graphics_schema import MotionGraphicScene, MotionGraphicsTimeline

REMOTION_DIR = ROOT / "remotion-video"
PUBLIC_BG_DIR = REMOTION_DIR / "public" / "bg"


def _npx() -> str:
    return "npx.cmd" if sys.platform == "win32" else "npx"


def render_motion_graphic_clip(
    scene_type: str,
    props: Dict[str, Any],
    out_path: Path,
    duration_frames: int,
    bg_image: Optional[Path] = None,
    fps: int = 30,
    dim: float = 0.75,
    use_gpu_gl: bool = True,
    timeout: int = 300,
) -> Path:
    """Render a single Remotion motion graphic scene clip."""
    if not REMOTION_DIR.exists():
        raise RuntimeError(f"Remotion directory not found at {REMOTION_DIR}")

    run_id = uuid.uuid4().hex[:10]
    bg_rel = ""
    bg_copy: Optional[Path] = None

    if bg_image and Path(bg_image).exists():
        PUBLIC_BG_DIR.mkdir(parents=True, exist_ok=True)
        bg_copy = PUBLIC_BG_DIR / f"bg_{run_id}{Path(bg_image).suffix.lower() or '.png'}"
        shutil.copy2(bg_image, bg_copy)
        bg_rel = f"bg/{bg_copy.name}"

    full_props = {**props, "bgSrc": bg_rel, "dim": dim}
    props_file = REMOTION_DIR / f"props_{run_id}.json"
    props_file.write_text(json.dumps(full_props, ensure_ascii=False), encoding="utf-8")

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = max(30, duration_frames)
    cmd = [
        _npx(), "remotion", "render", scene_type, str(out_path),
        f"--props={props_file.name}",
        f"--duration={frames}", f"--frames=0-{frames - 1}",
        "--concurrency=1",
        "--overwrite",
    ]
    if use_gpu_gl:
        cmd.append("--gl=angle")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=(sys.platform == "win32"),
        )
        if proc.returncode != 0 and use_gpu_gl:
            log.warning("Remotion render with --gl=angle failed; retrying without angle: %s", (proc.stderr or proc.stdout)[-300:])
            cmd.remove("--gl=angle")
            proc = subprocess.run(
                cmd,
                cwd=str(REMOTION_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=(sys.platform == "win32"),
            )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"Remotion render failed ({proc.returncode}): {(proc.stderr or proc.stdout)[-400:]}")
        return out_path
    finally:
        props_file.unlink(missing_ok=True)
        if bg_copy and bg_copy.exists():
            bg_copy.unlink(missing_ok=True)


def render_timeline_motion_graphics(
    project,
    scenes: List[Scene],
    timeline: MotionGraphicsTimeline,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> List[int]:
    """Renders all scenes planned in the timeline and links them to scene animation assets."""
    rendered_scene_ids: List[int] = []
    total = len(timeline.scenes)
    if total == 0:
        return rendered_scene_ids

    scene_map = {s.scene_id: s for s in scenes}

    for idx, mg in enumerate(timeline.scenes):
        if cancel_check and cancel_check():
            break

        sc = scene_map.get(mg.scene_id)
        if not sc:
            continue

        bg = project.abs(sc.image.path) if sc.image.status == Status.COMPLETED and sc.image.path else None
        out_clip = project.path("animation", f"{sc.tag}.mp4")

        try:
            log.info("Rendering Motion Graphic [%s] for Scene %d (%d frames)...", mg.scene_type.value, sc.scene_id, mg.duration_in_frames)
            render_motion_graphic_clip(
                scene_type=mg.scene_type.value,
                props=mg.props,
                out_path=out_clip,
                duration_frames=mg.duration_in_frames,
                bg_image=bg,
                fps=timeline.fps,
                dim=0.75 if mg.layout.value == "fullScreen" else 0.8,
            )
            sc.animation.status = Status.COMPLETED
            sc.animation.path = project.rel(out_clip)
            sc.animation.error = None
            sc.animation.meta = {
                "provider": "remotion",
                "sceneType": mg.scene_type.value,
                "layout": mg.layout.value,
                "props": mg.props,
                "reason": mg.reason,
                "background": sc.image.path,
            }
            rendered_scene_ids.append(sc.scene_id)
        except Exception as ex:
            log.warning("Motion graphic render failed for Scene %d (%s); falling back to Ken Burns", sc.scene_id, ex)
            sc.animation.status = Status.SKIPPED
            sc.animation.error = f"Motion graphic render failed: {ex}"

        if progress_callback:
            progress_callback(idx + 1, total)

    # Persist motion graphics plan
    project.write_json("scenes/motion_graphics.json", timeline.model_dump(by_alias=True))
    project.save_scenes()
    return rendered_scene_ids
