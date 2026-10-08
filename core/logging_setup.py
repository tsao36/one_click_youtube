"""Application logging -> logs/app.log (+ console). Secrets are never logged."""
from __future__ import annotations

import logging
import re
from collections import deque
from logging.handlers import RotatingFileHandler

from core.config import LOGS_DIR

RECENT: deque[str] = deque(maxlen=400)
_SECRET_RE = re.compile(r"(key|token|secret|authorization)(\"?\s*[:=]\s*\"?)([^\s\",&]+)", re.I)


class _RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        red = _SECRET_RE.sub(lambda m: m.group(1) + m.group(2) + "***", msg)
        if red != msg:
            record.msg, record.args = red, ()
        return True


class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        RECENT.append(self.format(record))


_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(level)
    fh = RotatingFileHandler(LOGS_DIR / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    ch = logging.StreamHandler()
    mh = _MemoryHandler()
    for h in (fh, ch, mh):
        h.setFormatter(fmt)
        h.addFilter(_RedactFilter())
        root.addHandler(h)
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio", "PIL", "comtypes", "multipart", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


log = logging.getLogger("aivc")
