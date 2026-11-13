"""Safe media-file serving routes."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.config import DATA_DIR, PROJECTS_DIR
from core.logging_setup import log
from generators.voice_generator import generate_voice_sample


router = APIRouter()


def resolve_under(base_dir: Path, relative_path: str) -> Path:
    """Resolve a relative path without allowing traversal outside ``base_dir``."""
    base = base_dir.resolve()
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    return target


def serve_voice_file_from(voice_name: str, file_name: str, data_dir: Path):
    target_dir = data_dir / "voices" / voice_name
    if not (target_dir / "voice.json").exists():
        for candidate in (data_dir / "voices").iterdir():
            if candidate.is_dir() and candidate.name.lower() == voice_name.lower():
                voice_name = candidate.name
                target_dir = candidate
                break

    path = resolve_under(target_dir, file_name)
    if not path.exists() and file_name in ("test_sample.wav", "sample.wav"):
        try:
            generate_voice_sample(voice_name)
        except Exception as exc:
            log.warning("Auto-synthesizing voice sample for '%s' failed: %s", voice_name, exc)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "audio/wav" if path.suffix == ".wav" else "audio/mpeg"
    return FileResponse(path, media_type=media_type)


def serve_project_file_from(project_id: str, file_path: str, projects_dir: Path):
    target_path = None
    p_dir = projects_dir / project_id

    # 1. Resolve strictly under project directory (raises 403 Forbidden on traversal outside p_dir)
    cand = resolve_under(p_dir, file_path)
    if cand.exists() and cand.is_file():
        target_path = cand

    # 2. If not found locally, check if project has an external archive path or absolute final video
    if not target_path and (p_dir / "project.json").exists():
        try:
            import json
            with open(p_dir / "project.json", "r", encoding="utf-8") as f:
                p_data = json.load(f)
            outputs = p_data.get("outputs") or {}
            ext_candidates = [outputs.get("final"), outputs.get("external_archive_path")]
            for ext_candidate in ext_candidates:
                if not ext_candidate:
                    continue
                ext_file = Path(ext_candidate)
                if ext_file.is_absolute() and ext_file.exists() and ext_file.is_file():
                    req_name = Path(file_path).name.lower()
                    if (
                        "final" in file_path.lower()
                        or "video" in file_path.lower()
                        or req_name == ext_file.name.lower()
                        or str(ext_file).replace("\\", "/").endswith(file_path.replace("\\", "/"))
                    ):
                        target_path = ext_file
                        break
        except Exception as e:
            log.warning("External media lookup failed for %s: %s", project_id, e)

    if not target_path or not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = target_path.suffix.lower()
    if ext == ".mp4":
        media_type = "video/mp4"
    elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
        media_type = f"image/{'jpeg' if ext in {'.jpg', '.jpeg'} else ext.lstrip('.')}"
    elif ext in {".wav", ".mp3"}:
        media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"
    else:
        media_type = "application/octet-stream"

    no_cache = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(target_path, media_type=media_type, headers=no_cache)


@router.get("/media/voices/{voice_name}/{file_name}")
def serve_voice_file(voice_name: str, file_name: str):
    return serve_voice_file_from(voice_name, file_name, DATA_DIR)


@router.get("/media/{project_id}/{file_path:path}")
def serve_project_file(project_id: str, file_path: str):
    return serve_project_file_from(project_id, file_path, PROJECTS_DIR)
