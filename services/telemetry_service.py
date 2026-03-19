"""Telemetry polling: sysfs + dumpsys via ADB; rolling averages; QThread worker."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Callable, Deque, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from models.telemetry_sample import TelemetrySample
from services.adb_service import AdbService
from utils.parsers import (
    parse_battery_current_ua_to_ma_display,
    parse_dumpsys_battery_current_ua,
    parse_dumpsys_battery_level,
    parse_dumpsys_battery_voltage_mv,
    parse_int_file_content,
    parse_thermal_zone_temp_mc_to_c,
)
from utils.runtime_estimator import normalize_current_to_ma

log = logging.getLogger(__name__)

ROLLING_WINDOW = 100


class TelemetryReader:
    """Stateless reads; safe to call from worker thread."""

    def __init__(self, adb: AdbService) -> None:
        self._adb = adb

    def read_zone3_c(self, target: str) -> tuple[Optional[float], str]:
        r = self._adb.shell_line(target, "cat /sys/class/thermal/thermal_zone3/temp")
        if not r.ok:
            return None, f"thermal_zone3: {r.stderr or r.stdout or 'read failed'}"
        t = parse_thermal_zone_temp_mc_to_c(r.stdout)
        if t is None:
            return None, "Could not parse thermal zone temperature."
        return t, ""

    def read_current(self, target: str) -> tuple[Optional[int], Optional[float], str]:
        r = self._adb.shell_line(
            target, "cat /sys/class/power_supply/battery/current_now"
        )
        if r.ok:
            raw, ma = parse_battery_current_ua_to_ma_display(r.stdout)
            if raw is not None:
                return raw, ma, ""
        # Fallback dumpsys
        d = self._adb.shell_line(target, "dumpsys battery")
        if not d.ok:
            return None, None, (r.stderr or r.stdout or "") + " | " + (d.stderr or "")
        raw, ma = parse_dumpsys_battery_current_ua(d.stdout)
        if raw is None:
            return None, None, "current_now not available from sysfs or dumpsys."
        return raw, ma, ""

    def read_capacity_percent(self, target: str) -> tuple[Optional[float], str]:
        r = self._adb.shell_line(
            target, "cat /sys/class/power_supply/battery/capacity"
        )
        if r.ok:
            v = parse_int_file_content(r.stdout)
            if v is not None:
                return float(v), ""
        d = self._adb.shell_line(target, "dumpsys battery")
        if not d.ok:
            return None, d.stderr or "dumpsys battery failed"
        lv = parse_dumpsys_battery_level(d.stdout)
        if lv is None:
            return None, "Could not parse battery level."
        return lv, ""

    def read_voltage_v(self, target: str) -> tuple[Optional[float], str]:
        r = self._adb.shell_line(target, "cat /sys/class/power_supply/battery/batt_vol")
        if r.ok:
            v = parse_int_file_content(r.stdout)
            if v is not None:
                # Typically mV on many Qualcomm builds
                return v / 1000.0, ""
        d = self._adb.shell_line(target, "dumpsys battery")
        if not d.ok:
            return None, d.stderr or "dumpsys battery failed"
        vv = parse_dumpsys_battery_voltage_mv(d.stdout)
        if vv is None:
            return None, "Could not parse battery voltage."
        return vv, ""


class TelemetryWorker(QObject):
    """
    Lives on a dedicated QThread; QTimer fires on that thread.
    """

    sample_ready = Signal(object)  # TelemetrySample
    status_changed = Signal(str)
    sig_start = Signal()
    sig_stop = Signal()

    def __init__(self, get_adb_path: Callable[[], str], get_target: Callable[[], str]) -> None:
        super().__init__()
        self._get_adb_path = get_adb_path
        self._get_target = get_target
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._running = False
        self._currents: Deque[float] = deque(maxlen=ROLLING_WINDOW)

    @Slot()
    def start_polling(self) -> None:
        if self._running:
            return
        self._running = True
        self._currents.clear()
        self._timer.start()
        self.status_changed.emit("Running")
        self._tick()

    @Slot()
    def stop_polling(self) -> None:
        self._running = False
        self._timer.stop()
        self.status_changed.emit("Stopped")

    def _tick(self) -> None:
        if not self._running:
            return
        target = self._get_target().strip()
        if not target:
            sample = TelemetrySample(
                timestamp=datetime.now(),
                device_target="",
                zone3_temp_c=None,
                current_ma=None,
                current_raw_ua=None,
                rolling_avg_100_ma=None,
                battery_percent=None,
                battery_voltage_v=None,
                success=False,
                notes="No device target selected.",
            )
            self.sample_ready.emit(sample)
            return

        adb = AdbService(self._get_adb_path())
        reader = TelemetryReader(adb)
        notes_parts: list[str] = []
        z3, e1 = reader.read_zone3_c(target)
        if e1:
            notes_parts.append(e1)
        raw_i, cur_ma, e2 = reader.read_current(target)
        if e2:
            notes_parts.append(e2)
        pct, e3 = reader.read_capacity_percent(target)
        if e3:
            notes_parts.append(e3)
        volt, e4 = reader.read_voltage_v(target)
        if e4:
            notes_parts.append(e4)

        cur_ma_norm = normalize_current_to_ma(cur_ma) if cur_ma is not None else None

        rolling: Optional[float] = None
        if cur_ma_norm is not None:
            self._currents.append(cur_ma_norm)
            rolling = sum(self._currents) / len(self._currents)

        success = (
            z3 is not None
            and cur_ma_norm is not None
            and pct is not None
            and volt is not None
        )
        notes = "; ".join(notes_parts) if notes_parts else ""

        sample = TelemetrySample(
            timestamp=datetime.now(),
            device_target=target,
            zone3_temp_c=z3,
            current_ma=cur_ma_norm,
            current_raw_ua=raw_i,
            rolling_avg_100_ma=rolling,
            battery_percent=pct,
            battery_voltage_v=volt,
            success=success,
            notes=notes,
        )
        self.sample_ready.emit(sample)


class TelemetrySession:
    """In-memory session log for CSV export."""

    def __init__(self) -> None:
        self.samples: list[TelemetrySample] = []

    def clear(self) -> None:
        self.samples.clear()

    def add(self, s: TelemetrySample) -> None:
        self.samples.append(s)

    @staticmethod
    def csv_header() -> list[str]:
        return [
            "timestamp_iso",
            "device_target",
            "zone3_temp_c",
            "current_ma_abs",
            "current_raw_ua",
            "rolling_avg_100_ma",
            "battery_percent",
            "battery_voltage_v",
            "success",
            "notes",
        ]
