"""Run blocking controller methods off the GUI thread."""

from __future__ import annotations

from typing import Callable, TypeVar

from PySide6.QtCore import QThread, Signal

T = TypeVar("T")


class FunctionRunnerThread(QThread):
    """Execute a callable and emit the return value."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], T], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.finished_ok.emit(result)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
