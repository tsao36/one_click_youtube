"""Minimal ComfyUI HTTP API client (shared by image and video providers)."""
from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import requests


class ComfyError(RuntimeError):
    pass


def fill_placeholders(obj: Any, values: dict[str, Any]) -> Any:
    """Replace "{{KEY}}" strings in a workflow. Exact matches keep the value's type."""
    if isinstance(obj, dict):
        return {k: fill_placeholders(v, values) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [fill_placeholders(v, values) for v in obj]
    if isinstance(obj, str) and "{{" in obj:
        stripped = obj.strip()
        if stripped.startswith("{{") and stripped.endswith("}}") and stripped.count("{{") == 1:
            key = stripped[2:-2]
            if key in values:
                return values[key]
        for k, v in values.items():
            obj = obj.replace("{{" + k + "}}", str(v))
        return obj
    return obj


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def available(self) -> tuple[bool, str]:
        try:
            r = requests.get(f"{self.base_url}/system_stats", timeout=3)
            r.raise_for_status()
            dev = (r.json().get("devices") or [{}])[0]
            return True, f"{dev.get('name', 'device')} ({dev.get('type', '?')})"
        except Exception:
            return False, (f"ComfyUI not reachable at {self.base_url}. Start it with "
                           f"'C:\\ComfyUI\\Launch ComfyUI AMD.bat' (or your own launcher).")

    def object_info(self, node: str) -> dict:
        r = requests.get(f"{self.base_url}/object_info/{node}", timeout=10)
        r.raise_for_status()
        return r.json().get(node, {})

    def list_checkpoints(self) -> list[str]:
        try:
            info = self.object_info("CheckpointLoaderSimple")
            return list(info["input"]["required"]["ckpt_name"][0])
        except Exception:
            return []

    def load_workflow(self, path: Path, values: dict[str, Any]) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            wf = json.load(f)
        return fill_placeholders(copy.deepcopy(wf), values)

    def upload_image(self, path: Path) -> str:
        with open(path, "rb") as f:
            r = requests.post(f"{self.base_url}/upload/image", files={"image": (path.name, f, "image/png")},
                              data={"overwrite": "true"}, timeout=60)
        r.raise_for_status()
        return r.json()["name"]

    def queue(self, workflow: dict) -> str:
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": self.client_id}, timeout=30)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI rejected workflow: HTTP {r.status_code} {r.text[:500]}")
        return r.json()["prompt_id"]

    def wait(
        self,
        prompt_id: str,
        timeout: float,
        cancel: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        start = time.time()
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={self.client_id}"

        ws = None
        try:
            from websockets.sync.client import connect
            ws = connect(ws_url)
        except Exception:
            ws = None

        try:
            while time.time() - start < timeout:
                if cancel and cancel():
                    self.interrupt()
                    raise ComfyError("cancelled")

                if ws is not None:
                    try:
                        while True:
                            msg_raw = ws.recv(timeout=0.2)
                            if not msg_raw:
                                break
                            msg = json.loads(msg_raw) if isinstance(msg_raw, str) else {}
                            m_type = msg.get("type")
                            m_data = msg.get("data", {})
                            if m_type == "progress":
                                val = m_data.get("value", 0)
                                max_v = m_data.get("max", 0)
                                if progress_callback and max_v > 0:
                                    progress_callback(val, max_v, "sampling")
                            elif m_type == "execution_error":
                                if m_data.get("prompt_id") == prompt_id:
                                    err_msg = m_data.get("exception_message", "ComfyUI execution error")
                                    raise ComfyError(err_msg)
                    except TimeoutError:
                        pass
                    except Exception:
                        try:
                            ws.close()
                        except Exception:
                            pass
                        ws = None

                try:
                    r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=5)
                    hist = r.json() if r.status_code == 200 else {}
                except requests.RequestException:
                    hist = {}
                if prompt_id in hist:
                    entry = hist[prompt_id]
                    status = entry.get("status", {})
                    if status.get("status_str") == "error":
                        msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                        detail = msgs[0][1].get("exception_message", "") if msgs else ""
                        raise ComfyError(f"ComfyUI execution error: {detail[:400]}")
                    if status.get("completed", True):
                        return entry.get("outputs", {})
                if ws is None:
                    time.sleep(0.8)
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        raise ComfyError(f"ComfyUI timed out after {int(timeout)}s")

    def download_outputs(self, outputs: dict, kinds: tuple[str, ...] = ("images",)) -> list[bytes]:
        files = []
        for node_out in outputs.values():
            for kind in kinds:
                for item in node_out.get(kind, []) or []:
                    if not isinstance(item, dict) or "filename" not in item:
                        continue
                    r = requests.get(f"{self.base_url}/view", params={
                        "filename": item["filename"], "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output")}, timeout=120)
                    r.raise_for_status()
                    files.append((item["filename"], r.content))
        return files

    def free(self) -> None:
        """Ask ComfyUI to unload models and release VRAM."""
        try:
            requests.post(f"{self.base_url}/free", json={"unload_models": True, "free_memory": True}, timeout=15)
        except Exception:
            pass

    def interrupt(self) -> None:
        try:
            requests.post(f"{self.base_url}/interrupt", timeout=5)
        except Exception:
            pass
