#!/usr/bin/env python3
"""
ADB Wearable Test Console — entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.logger import setup_root_logger
from utils.settings_manager import SettingsManager


def main() -> int:
    setup_root_logger()
    app = QApplication(sys.argv)
    app.setApplicationName("ADB Wearable Test Console")
    app.setOrganizationName("WearableTest")

    settings = SettingsManager()
    w = MainWindow()
    w.apply_stylesheet()

    geo = settings.window_geometry()
    if geo:
        w.restoreGeometry(QByteArray(geo))

    w.show()

    rc = app.exec()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
