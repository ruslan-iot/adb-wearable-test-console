"""Telemetry sample model for session logging and CSV export."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TelemetrySample:
    """One telemetry reading with metadata for QA export."""

    timestamp: datetime
    device_target: str
    zone3_temp_c: Optional[float]
    current_ma: Optional[float]
    current_raw_ua: Optional[int]
    rolling_avg_100_ma: Optional[float]
    battery_percent: Optional[float]
    battery_voltage_v: Optional[float]
    success: bool
    notes: str = ""

    def as_csv_row(self) -> list[str]:
        """Flatten for CSV writing."""
        return [
            self.timestamp.isoformat(timespec="seconds"),
            self.device_target,
            "" if self.zone3_temp_c is None else f"{self.zone3_temp_c:.3f}",
            "" if self.current_ma is None else f"{self.current_ma:.3f}",
            "" if self.current_raw_ua is None else str(self.current_raw_ua),
            "" if self.rolling_avg_100_ma is None else f"{self.rolling_avg_100_ma:.3f}",
            "" if self.battery_percent is None else f"{self.battery_percent:.1f}",
            "" if self.battery_voltage_v is None else f"{self.battery_voltage_v:.4f}",
            "1" if self.success else "0",
            self.notes.replace("\n", " ").replace("\r", ""),
        ]
