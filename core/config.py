"""Configuration loading: settings.yaml, providers.yaml and .env secrets."""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
PROJECTS_DIR = ROOT / "projects"
LOGS_DIR = ROOT / "logs"
WORKFLOWS_DIR = ROOT / "workflows"
VOICES_DIR = DATA_DIR / "voices"
MUSIC_DIR = DATA_DIR / "music"
YOUTUBE_DIR = DATA_DIR / "youtube"
ENV_FILE = ROOT / ".env"

_lock = threading.RLock()


def deep_merge(base: dict, override: dict | None) -> dict:
    """Return a new dict = base recursively updated with override."""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings() -> dict:
    with _lock:
        return _read_yaml(CONFIG_DIR / "settings.yaml")


def load_providers() -> dict:
    with _lock:
        return _read_yaml(CONFIG_DIR / "providers.yaml")


def save_yaml(name: str, data: dict) -> None:
    with _lock:
        path = CONFIG_DIR / name
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        os.replace(tmp, path)


def load_env() -> None:
    load_dotenv(ENV_FILE, override=True)


def get_secret(name: str | None) -> str:
    if not name:
        return ""
    load_env()
    return os.environ.get(name, "").strip()


def set_secret(name: str, value: str) -> None:
    """Write/replace a key in .env (never logged)."""
    with _lock:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
        found = False
        for i, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == name:
                lines[i] = f"{name}={value}"
                found = True
        if not found:
            lines.append(f"{name}={value}")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ[name] = value


def mask(value: str) -> str:
    if not value:
        return ""
    return value[:3] + "…" + value[-2:] if len(value) > 8 else "••••"


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
