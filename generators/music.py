"""Background music selection (local royalty-free folder only; nothing is downloaded)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from core.config import ROOT

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}


def list_tracks(directory: str) -> list[Path]:
    d = ROOT / directory
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT)


def pick_track(directory: str, key: str, preferred: str | None = None) -> Path | None:
    tracks = list_tracks(directory)
    if not tracks:
        return None
    if preferred:
        for t in tracks:
            if t.name == preferred:
                return t
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(tracks)
    return tracks[idx]
