"""Application logging with optional GUI sink."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Optional


class GuiLogHandler(logging.Handler):
    """Forwards log records to a callback (e.g. Qt signal emitter)."""

    def __init__(self, emit_fn) -> None:
        super().__init__()
        self._emit_fn = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._emit_fn(msg)
        except Exception:  # noqa: BLE001
            self.handleError(record)


def setup_root_logger(
    level: int = logging.DEBUG,
    gui_handler: Optional[GuiLogHandler] = None,
) -> logging.Logger:
    """Configure root logger once; idempotent for repeated calls."""
    log = logging.getLogger()
    if log.handlers:
        if gui_handler:
            log.addHandler(gui_handler)
        return log
    log.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    if gui_handler:
        gui_handler.setFormatter(fmt)
        log.addHandler(gui_handler)
    return log


def timestamp_message(message: str) -> str:
    """User-facing log line with wall-clock prefix."""
    return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
