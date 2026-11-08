"""Remotion Motion Graphics Renderer for Documentary Mode.

Executes local-first Remotion rendering for validated MotionGraphicsTimeline scenes.
Composites animations over the scene's background image or renders transparent overlay clips.
Guarantees zero-crash fallback: any card failure gracefully falls back to Ken Burns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status
from core.motion_graphics_schema import MotionGraphicScene, MotionGraphicsTimeline

REMOTION_DIR = ROOT / "remotion-video"


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
    from rendering.remotion_cli import render_composition
    return render_composition(
        REMOTION_DIR, scene_type, props, out_path, duration_frames,
        bg_image=bg_image, dim=dim, use_gpu_gl=use_gpu_gl, timeout=timeout,
    )


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

        # In modern tech explainer / dark obsidian mode, never pass background image
        rem_cfg = (project.settings.get("remotion") or {})
        data_settings = getattr(project, "data", None) and getattr(project.data, "settings", None) or {}
        data_rem_cfg = (data_settings.get("remotion") or {})
        cur_style = rem_cfg.get("style") or data_rem_cfg.get("style") or ""
        cur_theme = rem_cfg.get("theme") or data_rem_cfg.get("theme") or ""
        cur_density = rem_cfg.get("density") or data_rem_cfg.get("density") or ""
        is_standalone_canvas = (
            cur_style in ("modern_tech_explainer", "coordinate_zero", "finance_market", "archival_history", "vox_journalism")
            or cur_theme in ("dark_obsidian", "green_cutting_mat", "finance_grid", "parchment_paper", "vox_charcoal")
            or cur_density == "full"
        )
        bg = None if is_standalone_canvas else (project.abs(sc.image.path) if sc.image.status == Status.COMPLETED and sc.image.path else None)
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
