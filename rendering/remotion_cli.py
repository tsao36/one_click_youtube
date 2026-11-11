"""Single Remotion CLI execution path shared by cards and timeline graphics."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from core.logging_setup import log


def render_composition(remotion_dir: Path, composition: str, props: dict[str, Any],
                       out_path: Path, frames: int, bg_image: Path | None = None,
                       dim: float = 0.7, use_gpu_gl: bool = True,
                       timeout: int = 300) -> Path:
    if not remotion_dir.exists():
        raise RuntimeError(f"Remotion project not found at {remotion_dir}")
    run_id = uuid.uuid4().hex[:10]
    public_bg = remotion_dir / "public" / "bg"
    bg_copy: Path | None = None
    bg_src = ""
    if bg_image and Path(bg_image).exists():
        public_bg.mkdir(parents=True, exist_ok=True)
        bg_copy = public_bg / f"bg_{run_id}{Path(bg_image).suffix.lower() or '.png'}"
        shutil.copy2(bg_image, bg_copy)
        bg_src = f"bg/{bg_copy.name}"

    props_file = remotion_dir / f"props_{run_id}.json"
    props_file.write_text(
        json.dumps({**props, "bgSrc": bg_src, "dim": dim}, ensure_ascii=False),
        encoding="utf-8",
    )
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(30, int(frames))
    remotion_concurrency = str(max(2, min(6, (os.cpu_count() or 4) // 4)))
    command = [
        "npx.cmd" if sys.platform == "win32" else "npx", "remotion", "render",
        composition, str(out_path), f"--props={props_file.name}",
        f"--duration={frames}", f"--frames=0-{frames - 1}",
        f"--concurrency={remotion_concurrency}", "--overwrite",
    ]
    if use_gpu_gl:
        command.append("--gl=angle")

    def run():
        return subprocess.run(
            command, cwd=str(remotion_dir), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            shell=(sys.platform == "win32"),
        )

    try:
        result = run()
        if result.returncode != 0 and "--gl=angle" in command:
            log.warning("Remotion render with --gl=angle failed; retrying with default GL: %s",
                        (result.stderr or result.stdout)[-300:])
            command.remove("--gl=angle")
            result = run()
        if result.returncode != 0 or not out_path.exists():
            raise RuntimeError(
                f"Remotion render failed ({result.returncode}): "
                f"{(result.stderr or result.stdout)[-400:]}"
            )
        return out_path
    finally:
        props_file.unlink(missing_ok=True)
        if bg_copy:
            bg_copy.unlink(missing_ok=True)
