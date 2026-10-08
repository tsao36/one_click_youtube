"""Independent Stage Versioning & Iteration Management.
Allows generating multiple versions per stage and cycling through them
before stringing everything together into the final video.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.logging_setup import log
from core.models import Scene, Status
from core.project_manager import Project, now

STAGE_FILES: dict[str, list[str]] = {
    "research": ["research.json"],
    "script": ["script.json", "script.md"],
    "scenes": ["scenes.json", "visual_bible.json"],
    "prompts": ["image_prompts.json"],
    "subtitles": ["subtitles.srt", "subtitles.ass"],
}


def _versions_meta_path(project: Project, stage_name: str) -> Path:
    return project.path(stage_name, "versions.json")


def _read_meta(project: Project, stage_name: str) -> dict[str, Any]:
    meta_p = _versions_meta_path(project, stage_name)
    if meta_p.exists():
        try:
            return json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"active_version": 1, "versions": []}


def _save_meta(project: Project, stage_name: str, meta: dict[str, Any]) -> None:
    meta_p = _versions_meta_path(project, stage_name)
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def get_stage_versions(project: Project, stage_name: str) -> dict[str, Any]:
    """Retrieve version list and currently active version for a stage."""
    meta = _read_meta(project, stage_name)
    files = STAGE_FILES.get(stage_name, [])

    # If versions list is empty but active files exist on disk, register v1 retroactively
    if not meta["versions"] and files:
        has_files = any(project.path(stage_name, f).exists() for f in files)
        if has_files:
            record_stage_version(project, stage_name, summary="Initial generation")
            meta = _read_meta(project, stage_name)

    return {
        "stage": stage_name,
        "active_version": meta.get("active_version", 1),
        "total_versions": len(meta.get("versions", [])),
        "versions": meta.get("versions", []),
    }


def record_stage_version(project: Project, stage_name: str, summary: str = "") -> dict[str, Any]:
    """Snapshot the current files of a stage as a new version."""
    files = STAGE_FILES.get(stage_name, [])
    if not files:
        return {"status": "no_files_tracked"}

    existing_files = [f for f in files if project.path(stage_name, f).exists()]
    if not existing_files:
        return {"status": "no_existing_files"}

    meta = _read_meta(project, stage_name)
    versions = meta.get("versions", [])
    next_ver = len(versions) + 1

    ver_dir = project.path(stage_name, "versions", f"v{next_ver}")
    ver_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for f in existing_files:
        src = project.path(stage_name, f)
        dst = ver_dir / f
        shutil.copy2(src, dst)
        copied.append(f)

    # Generate quick summary if not provided
    if not summary:
        if stage_name == "script":
            scr_md = project.read_text("script/script.md", "")
            summary = f"{len(scr_md)} chars" if scr_md else f"Version {next_ver}"
        elif stage_name == "scenes":
            scenes = project.scenes
            summary = f"{len(scenes)} scenes"
        elif stage_name == "prompts":
            prompts = project.read_json("prompts/image_prompts.json", [])
            summary = f"{len(prompts)} prompts"
        else:
            summary = f"Version {next_ver}"

    ver_record = {
        "version": next_ver,
        "created_at": now(),
        "summary": summary,
        "files": copied,
    }
    versions.append(ver_record)
    meta["versions"] = versions
    meta["active_version"] = next_ver
    _save_meta(project, stage_name, meta)

    log.info("Recorded %s stage version v%d for project %s", stage_name, next_ver, project.id)
    return {"status": "recorded", "version": next_ver, "summary": summary}


def switch_stage_version(project: Project, stage_name: str, target_version: int) -> dict[str, Any]:
    """Switch active content of a stage to a previously generated version."""
    meta = _read_meta(project, stage_name)
    versions = meta.get("versions", [])
    ver_entry = next((v for v in versions if v["version"] == target_version), None)
    if not ver_entry:
        return {"status": "error", "message": f"Version {target_version} not found"}

    ver_dir = project.path(stage_name, "versions", f"v{target_version}")
    if not ver_dir.exists():
        return {"status": "error", "message": f"Version folder v{target_version} missing"}

    files = ver_entry.get("files", [])
    for f in files:
        src = ver_dir / f
        if src.exists():
            dst = project.path(stage_name, f)
            shutil.copy2(src, dst)

    meta["active_version"] = target_version
    _save_meta(project, stage_name, meta)

    if stage_name == "scenes":
        project.reload()
    elif stage_name == "prompts":
        prompts = project.read_json("prompts/image_prompts.json", [])
        if prompts and isinstance(prompts, list):
            prompt_map = {p.get("scene_id"): p for p in prompts if isinstance(p, dict)}
            for s in project.scenes:
                if s.scene_id in prompt_map:
                    s.prompt = prompt_map[s.scene_id].get("prompt", s.prompt)
                    s.negative_prompt = prompt_map[s.scene_id].get("negative_prompt", s.negative_prompt)
            project.save_scenes()

    log.info("Switched project %s %s to version v%d", project.id, stage_name, target_version)
    return {"status": "switched", "active_version": target_version}


# =========================================================================
# Per-Scene Image Takes & Versioning
# =========================================================================
# Per-Scene Image Takes & Versioning
# =========================================================================

def ensure_initial_image_take(project: Project, scene_id: int) -> None:
    """Ensure that all existing image takes on disk are registered and synchronized into metadata."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return
    meta = s.image.meta or {}
    takes = meta.get("takes", [])
    if not isinstance(takes, list):
        takes = []

    takes_dir = project.path("images", "takes")
    takes_dir.mkdir(parents=True, exist_ok=True)

    # 1. First: if active scene image exists on disk, but images/takes has no take files at all,
    # seed take 1 from active image
    active_path = project.path(s.image.path) if s.image.path else project.path("images", f"{s.tag}.png")
    take1_path = takes_dir / f"scene_{scene_id:03d}_take1.png"
    if active_path.exists() and not take1_path.exists():
        shutil.copy2(active_path, take1_path)

    # 2. Inspect all take files on disk for this scene
    pattern = re.compile(rf"^scene_{scene_id:03d}_take(\d+)\.png$")
    disk_takes: dict[int, Path] = {}
    for df in sorted(takes_dir.glob(f"scene_{scene_id:03d}_take*.png")):
        m = pattern.match(df.name)
        if m:
            t_num = int(m.group(1))
            disk_takes[t_num] = df

    # Map existing takes in meta by take number
    existing_by_num: dict[int, dict[str, Any]] = {}
    for t in takes:
        if isinstance(t, dict) and "take" in t:
            try:
                t_n = int(t["take"])
                existing_by_num[t_n] = t
            except (ValueError, TypeError):
                pass

    # Ensure every disk file has a take record
    updated = False
    for t_num, df in disk_takes.items():
        if t_num not in existing_by_num:
            mtime_str = datetime.fromtimestamp(df.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            new_entry = {
                "take": t_num,
                "path": project.rel(df),
                "created_at": mtime_str,
                "model": meta.get("model", ""),
                "style": s.visual_style or meta.get("visual_style", ""),
                "prompt": s.prompt or s.visual_description,
            }
            existing_by_num[t_num] = new_entry
            updated = True
        else:
            rel_p = project.rel(df)
            if existing_by_num[t_num].get("path") != rel_p:
                existing_by_num[t_num]["path"] = rel_p
                updated = True

    all_takes = [existing_by_num[k] for k in sorted(existing_by_num.keys())]
    if updated or len(all_takes) != len(takes):
        meta["takes"] = all_takes
        if not meta.get("active_take") or meta.get("active_take") not in existing_by_num:
            meta["active_take"] = max(existing_by_num.keys()) if existing_by_num else 1
        s.image.meta = meta
        project.save_scenes()


def record_scene_image_take(project: Project, scene_id: int, active_rel_path: str, model_used: str = "", prompt: str = "", style_used: str = "") -> dict[str, Any]:
    """Save an image take into the scene's takes archive with safe non-colliding numbering."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "scene_not_found"}

    # Sync first to ensure we have the up-to-date state of all takes
    ensure_initial_image_take(project, scene_id)

    meta = s.image.meta or {}
    takes = meta.get("takes", [])
    if not isinstance(takes, list):
        takes = []

    takes_dir = project.path("images", "takes")
    takes_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"^scene_{scene_id:03d}_take(\d+)\.png$")
    disk_nums = [int(m.group(1)) for df in takes_dir.glob(f"scene_{scene_id:03d}_take*.png") if (m := pattern.match(df.name))]
    meta_nums = [int(t["take"]) for t in takes if isinstance(t, dict) and "take" in t]

    highest = max(disk_nums + meta_nums + [0])
    next_take_num = highest + 1

    archive_name = f"scene_{scene_id:03d}_take{next_take_num}.png"
    archive_path = takes_dir / archive_name

    src = project.path(active_rel_path)
    if src.exists():
        shutil.copy2(src, archive_path)
        take_rel = project.rel(archive_path)
    else:
        take_rel = active_rel_path

    new_take = {
        "take": next_take_num,
        "path": take_rel,
        "created_at": now(),
        "model": model_used or meta.get("model", ""),
        "style": style_used or meta.get("visual_style", ""),
        "prompt": prompt or s.prompt or "",
    }
    takes.append(new_take)
    # Sort takes by take number
    takes.sort(key=lambda t: int(t.get("take", 1)))
    meta["takes"] = takes
    meta["active_take"] = next_take_num
    meta["visual_style"] = style_used or meta.get("visual_style", "")
    s.image.meta = meta
    if style_used:
        s.visual_style = style_used
    project.save_scenes()
    log.info("Recorded scene %d image take %d (total: %d)", scene_id, next_take_num, len(takes))
    return {"status": "recorded", "active_take": next_take_num, "total_takes": len(takes)}


def switch_scene_image_take(project: Project, scene_id: int, target_take: int) -> dict[str, Any]:
    """Switch active image for a specific scene to a previously generated take."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "scene_not_found"}

    ensure_initial_image_take(project, scene_id)
    meta = s.image.meta or {}
    takes = meta.get("takes", [])
    take_entry = next((t for t in takes if int(t.get("take", -1)) == target_take), None)

    if not take_entry:
        return {"status": "error", "message": f"Take {target_take} not found"}

    take_file = project.abs(take_entry["path"])
    if take_file and take_file.exists():
        active_dest = project.path("images", f"{s.tag}.png")
        shutil.copy2(take_file, active_dest)
        s.image.path = project.rel(active_dest)
        meta["active_take"] = target_take
        if take_entry.get("style"):
            s.visual_style = take_entry.get("style")
            meta["visual_style"] = take_entry.get("style")
        if take_entry.get("prompt"):
            s.prompt = take_entry.get("prompt")
        s.image.meta = meta
        project.save_scenes()
        log.info("Switched scene %d to image take %d", scene_id, target_take)
        return {"status": "switched", "active_take": target_take, "path": s.image.path, "style": s.visual_style or "", "prompt": s.prompt or ""}

    return {"status": "error", "message": "Take file not found on disk"}


def delete_scene_image_take(project: Project, scene_id: int, target_take: int | None = None) -> dict[str, Any]:
    """Delete a specific image take or the active scene image, preserving remaining takes."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "error", "message": f"Scene {scene_id} not found"}

    ensure_initial_image_take(project, scene_id)
    meta = s.image.meta or {}
    takes = list(meta.get("takes", []))
    active_take = meta.get("active_take")

    if target_take is None:
        target_take = active_take

    deleted_entry = None
    if target_take is not None:
        deleted_entry = next((t for t in takes if int(t.get("take", -1)) == target_take), None)

    if deleted_entry:
        if deleted_entry.get("path"):
            take_path = project.abs(deleted_entry["path"])
            if take_path and take_path.exists():
                try:
                    take_path.unlink()
                except Exception as ex:
                    log.warning("Could not unlink take file %s: %s", take_path, ex)

        takes = [t for t in takes if int(t.get("take", -1)) != target_take]
        meta["takes"] = takes

        if active_take == target_take:
            if takes:
                new_take = int(takes[-1]["take"])
                new_take_entry = takes[-1]
                new_file = project.abs(new_take_entry["path"])
                if new_file and new_file.exists():
                    active_dest = project.path("images", f"{s.tag}.png")
                    shutil.copy2(new_file, active_dest)
                    s.image.path = project.rel(active_dest)
                    meta["active_take"] = new_take
                    if new_take_entry.get("style"):
                        s.visual_style = new_take_entry.get("style")
                    if new_take_entry.get("prompt"):
                        s.prompt = new_take_entry.get("prompt")
            else:
                active_dest = project.path("images", f"{s.tag}.png")
                if active_dest.exists():
                    active_dest.unlink(missing_ok=True)
                s.image.path = None
                s.image.status = Status.PENDING
                meta["active_take"] = None
                meta["takes"] = []
    else:
        active_dest = project.path("images", f"{s.tag}.png")
        if active_dest.exists():
            active_dest.unlink(missing_ok=True)
        s.image.path = None
        s.image.status = Status.PENDING
        meta["active_take"] = None
        meta["takes"] = []

    s.image.meta = meta
    project.save_scenes()
    project.set_stage("render", Status.PENDING)
    log.info("Deleted scene %d image take %s (remaining takes: %d)", scene_id, target_take, len(takes))
    return {
        "status": "deleted",
        "scene_id": scene_id,
        "deleted_take": target_take,
        "remaining_takes": len(takes),
        "active_take": meta.get("active_take"),
        "has_image": bool(s.image.path),
        "path": s.image.path,
    }


# =========================================================================
# Per-Scene Voice Takes & Versioning
# =========================================================================

def ensure_initial_voice_take(project: Project, scene_id: int) -> None:
    """Ensure that all existing voice clips on disk are registered and synchronized into metadata."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return
    meta = s.audio.meta or {}
    takes = meta.get("takes", [])
    if not isinstance(takes, list):
        takes = []

    takes_dir = project.path("audio", "takes")
    takes_dir.mkdir(parents=True, exist_ok=True)

    active_path = project.path(s.audio.path) if s.audio.path else project.path("audio", f"{s.tag}.wav")
    take1_path = takes_dir / f"scene_{scene_id:03d}_take1.wav"
    if active_path.exists() and not take1_path.exists():
        shutil.copy2(active_path, take1_path)

    pattern = re.compile(rf"^scene_{scene_id:03d}_take(\d+)\.wav$")
    disk_takes: dict[int, Path] = {}
    for df in sorted(takes_dir.glob(f"scene_{scene_id:03d}_take*.wav")):
        m = pattern.match(df.name)
        if m:
            t_num = int(m.group(1))
            disk_takes[t_num] = df

    existing_by_num: dict[int, dict[str, Any]] = {}
    for t in takes:
        if isinstance(t, dict) and "take" in t:
            try:
                t_n = int(t["take"])
                existing_by_num[t_n] = t
            except (ValueError, TypeError):
                pass

    updated = False
    for t_num, df in disk_takes.items():
        if t_num not in existing_by_num:
            mtime_str = datetime.fromtimestamp(df.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            new_entry = {
                "take": t_num,
                "path": project.rel(df),
                "created_at": mtime_str,
                "voice": meta.get("voice", ""),
                "duration_seconds": s.audio_duration or s.estimated_duration,
            }
            existing_by_num[t_num] = new_entry
            updated = True
        else:
            rel_p = project.rel(df)
            if existing_by_num[t_num].get("path") != rel_p:
                existing_by_num[t_num]["path"] = rel_p
                updated = True

    all_takes = [existing_by_num[k] for k in sorted(existing_by_num.keys())]
    if updated or len(all_takes) != len(takes):
        meta["takes"] = all_takes
        if not meta.get("active_take") or meta.get("active_take") not in existing_by_num:
            meta["active_take"] = max(existing_by_num.keys()) if existing_by_num else 1
        s.audio.meta = meta
        project.save_scenes()


def record_scene_voice_take(project: Project, scene_id: int, active_rel_path: str, voice_used: str = "") -> dict[str, Any]:
    """Save a voice synthesis take into the scene's voice archive with safe non-colliding numbering."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "scene_not_found"}

    ensure_initial_voice_take(project, scene_id)

    meta = s.audio.meta or {}
    takes = meta.get("takes", [])
    if not isinstance(takes, list):
        takes = []

    takes_dir = project.path("audio", "takes")
    takes_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"^scene_{scene_id:03d}_take(\d+)\.wav$")
    disk_nums = [int(m.group(1)) for df in takes_dir.glob(f"scene_{scene_id:03d}_take*.wav") if (m := pattern.match(df.name))]
    meta_nums = [int(t["take"]) for t in takes if isinstance(t, dict) and "take" in t]

    highest = max(disk_nums + meta_nums + [0])
    next_take_num = highest + 1

    archive_name = f"scene_{scene_id:03d}_take{next_take_num}.wav"
    archive_path = takes_dir / archive_name

    src = project.path(active_rel_path)
    if src.exists():
        shutil.copy2(src, archive_path)
        take_rel = project.rel(archive_path)
    else:
        take_rel = active_rel_path

    new_take = {
        "take": next_take_num,
        "path": take_rel,
        "created_at": now(),
        "voice": voice_used or meta.get("voice", ""),
        "duration_seconds": s.audio_duration or (s.audio.meta or {}).get("duration", 0.0),
    }
    takes.append(new_take)
    takes.sort(key=lambda t: int(t.get("take", 1)))
    meta["takes"] = takes
    meta["active_take"] = next_take_num
    s.audio.meta = meta
    project.save_scenes()
    log.info("Recorded scene %d voice take %d (total: %d)", scene_id, next_take_num, len(takes))
    return {"status": "recorded", "active_take": next_take_num, "total_takes": len(takes)}


def switch_scene_voice_take(project: Project, scene_id: int, target_take: int) -> dict[str, Any]:
    """Switch active voice clip for a specific scene to a previously synthesized take."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "scene_not_found"}

    ensure_initial_voice_take(project, scene_id)
    meta = s.audio.meta or {}
    takes = meta.get("takes", [])
    take_entry = next((t for t in takes if int(t.get("take", -1)) == target_take), None)

    if not take_entry:
        return {"status": "error", "message": f"Take {target_take} not found"}

    take_file = project.abs(take_entry["path"])
    if take_file and take_file.exists():
        active_dest = project.path("audio", f"{s.tag}.wav")
        shutil.copy2(take_file, active_dest)
        s.audio.path = project.rel(active_dest)
        if "duration_seconds" in take_entry:
            s.audio_duration = float(take_entry["duration_seconds"] or 0.0)
            meta["duration"] = s.audio_duration
        if take_entry.get("voice"):
            s.voice_profile = take_entry.get("voice")
            meta["voice"] = take_entry.get("voice")
        meta["active_take"] = target_take
        s.audio.meta = meta
        project.save_scenes()
        project.set_stage("subtitles", Status.PENDING)
        project.set_stage("render", Status.PENDING)
        log.info("Switched scene %d to voice take %d", scene_id, target_take)
        return {"status": "switched", "active_take": target_take, "path": s.audio.path}

    return {"status": "error", "message": "Take file not found on disk"}


def delete_scene_voice_take(project: Project, scene_id: int, target_take: int | None = None) -> dict[str, Any]:
    """Delete a specific voice take or the active scene voice clip, preserving remaining takes."""
    try:
        s = project.scene(scene_id)
    except KeyError:
        return {"status": "error", "message": f"Scene {scene_id} not found"}

    ensure_initial_voice_take(project, scene_id)
    meta = s.audio.meta or {}
    takes = list(meta.get("takes", []))
    active_take = meta.get("active_take")

    if target_take is None:
        target_take = active_take

    deleted_entry = None
    if target_take is not None:
        deleted_entry = next((t for t in takes if int(t.get("take", -1)) == target_take), None)

    if deleted_entry:
        if deleted_entry.get("path"):
            take_path = project.abs(deleted_entry["path"])
            if take_path and take_path.exists():
                try:
                    take_path.unlink()
                except Exception as ex:
                    log.warning("Could not unlink voice take file %s: %s", take_path, ex)

        takes = [t for t in takes if int(t.get("take", -1)) != target_take]
        meta["takes"] = takes

        if active_take == target_take:
            if takes:
                new_take = int(takes[-1]["take"])
                new_take_entry = takes[-1]
                new_file = project.abs(new_take_entry["path"])
                if new_file and new_file.exists():
                    active_dest = project.path("audio", f"{s.tag}.wav")
                    shutil.copy2(new_file, active_dest)
                    s.audio.path = project.rel(active_dest)
                    meta["active_take"] = new_take
                    if "duration_seconds" in new_take_entry:
                        s.audio_duration = float(new_take_entry["duration_seconds"] or 0.0)
                        meta["duration"] = s.audio_duration
                    if new_take_entry.get("voice"):
                        s.voice_profile = new_take_entry.get("voice")
            else:
                active_dest = project.path("audio", f"{s.tag}.wav")
                if active_dest.exists():
                    active_dest.unlink(missing_ok=True)
                s.audio.path = None
                s.audio.status = Status.PENDING
                s.audio_duration = 0.0
                meta["active_take"] = None
                meta["takes"] = []
    else:
        active_dest = project.path("audio", f"{s.tag}.wav")
        if active_dest.exists():
            active_dest.unlink(missing_ok=True)
        s.audio.path = None
        s.audio.status = Status.PENDING
        s.audio_duration = 0.0
        meta["active_take"] = None
        meta["takes"] = []

    s.audio.meta = meta
    project.save_scenes()
    project.set_stage("subtitles", Status.PENDING)
    project.set_stage("render", Status.PENDING)
    log.info("Deleted scene %d voice take %s (remaining takes: %d)", scene_id, target_take, len(takes))
    return {
        "status": "deleted",
        "scene_id": scene_id,
        "deleted_take": target_take,
        "remaining_takes": len(takes),
        "active_take": meta.get("active_take"),
        "has_audio": bool(s.audio.path),
    }

