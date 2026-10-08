"""LLM provider interface + JSON helpers."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"
    is_cloud: bool = False

    def __init__(self, cfg: dict, model: str | None = None):
        self.cfg = cfg
        self.model = model or cfg.get("model", "")

    @abstractmethod
    def generate(self, prompt: str, system: str = "", json_mode: bool = False,
                 temperature: float = 0.7, max_tokens: int = 4096) -> str:
        ...

    def generate_with_search(self, prompt: str, system: str = "") -> str:
        raise LLMError(f"{self.name} does not support web search grounding")

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        ...


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str) -> Any:
    """Parse JSON from an LLM reply, tolerating code fences, prose and <think> blocks."""
    text = _THINK_RE.sub("", text).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # find the outermost {...} or [...]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end > start:
            chunk = text[start:end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                # remove trailing commas, a common small-model mistake
                fixed = re.sub(r",\s*([}\]])", r"\1", chunk)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    continue
    raise LLMError("Could not parse JSON from model output: " + text[:300])


def strip_think(text: str) -> str:
    return _THINK_RE.sub("", text).strip()
