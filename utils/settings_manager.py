"""Persist application settings via QSettings (Windows registry / native)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QByteArray, QSettings

ORG = "WearableTest"
APP = "ADBWearableConsole"


class SettingsManager:
    """Thin wrapper around QSettings for typed keys."""

    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    def adb_path(self) -> str:
        return str(self._s.value("adb_path", "", type=str) or "")

    def set_adb_path(self, path: str) -> None:
        self._s.setValue("adb_path", path)

    def tcp_port(self) -> int:
        v = self._s.value("tcp_port", 5555, type=int)
        return int(v) if v else 5555

    def set_tcp_port(self, port: int) -> None:
        self._s.setValue("tcp_port", port)

    def last_ssid(self) -> str:
        return str(self._s.value("last_ssid", "", type=str) or "")

    def set_last_ssid(self, ssid: str) -> None:
        self._s.setValue("last_ssid", ssid)

    def last_export_folder(self) -> str:
        return str(self._s.value("last_export_folder", "", type=str) or "")

    def set_last_export_folder(self, folder: str) -> None:
        self._s.setValue("last_export_folder", folder)

    def battery_capacity_mah(self) -> int:
        """Nominal pack capacity in mAh (runtime estimation input)."""
        v = self._s.value("battery_capacity_mah", 3300, type=int)
        return int(v) if v else 3300

    def set_battery_capacity_mah(self, mah: int) -> None:
        self._s.setValue("battery_capacity_mah", int(mah))

    def window_geometry(self) -> Optional[bytes]:
        raw = self._s.value("window_geometry")
        if raw is None:
            return None
        if isinstance(raw, QByteArray):
            return raw.data()
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        return None

    def set_window_geometry(self, geometry: bytes) -> None:
        self._s.setValue("window_geometry", QByteArray(geometry))

    def sync(self) -> None:
        self._s.sync()
