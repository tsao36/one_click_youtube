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
    target_path = resolve_under(projects_dir / project_id, file_path)
    if not target_path.exists() or not target_path.is_file():
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
