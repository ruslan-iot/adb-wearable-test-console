"""
Battery runtime estimates (mAh / mA model) for the telemetry panel.

Primary load metric: rolling average current (fallback: instantaneous).
Energy in Wh is auxiliary only (terminal voltage × remaining mAh).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# --- Product constants (adjust for your pack / policy) ---

NOMINAL_BATTERY_CAPACITY_MAH: float = 3300.0
USABLE_CAPACITY_FACTOR: float = 0.85
MIN_ESTIMATE_CURRENT_MA: float = 1.0


def get_effective_capacity_mah(
    nominal_capacity_mah: float = NOMINAL_BATTERY_CAPACITY_MAH,
    usable_factor: float = USABLE_CAPACITY_FACTOR,
) -> float:
    return nominal_capacity_mah * usable_factor


def normalize_current_to_ma(value: Optional[float]) -> Optional[float]:
    """
    Internal standard: **milliamps** (positive = consumption magnitude).

    - Values already in mA (e.g. 144, 177) pass through (absolute value).
    - Values in **amperes** (0 < |x| < 1) are multiplied by 1000.
    - None / NaN / ~0 → None.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    a = abs(x)
    if a < 1e-12:
        return None
    if a < 1.0:
        return a * 1000.0
    return a


def estimate_remaining_capacity_mah(
    battery_percent: float, effective_capacity_mah: float
) -> float:
    pct = max(0.0, min(100.0, float(battery_percent)))
    return effective_capacity_mah * (pct / 100.0)


def estimate_runtime_hours(
    remaining_capacity_mah: float,
    current_ma: float,
    min_current_ma: float = MIN_ESTIMATE_CURRENT_MA,
) -> Optional[float]:
    if current_ma <= min_current_ma:
        return None
    if remaining_capacity_mah <= 0:
        return None
    return remaining_capacity_mah / current_ma


def estimate_full_runtime_hours(
    effective_capacity_mah: float,
    current_ma: float,
    min_current_ma: float = MIN_ESTIMATE_CURRENT_MA,
) -> Optional[float]:
    if current_ma <= min_current_ma:
        return None
    return effective_capacity_mah / current_ma


def format_duration_hours(hours: Optional[float]) -> str:
    """
    Human-friendly duration from decimal hours.

    - invalid / non-positive → "--"
    - < 1 minute total → "<1 min"
    - < 1 hour → "N min"
    - >= 1 hour → "about H h M min"
    """
    if hours is None or (isinstance(hours, float) and math.isnan(hours)) or hours <= 0:
        return "--"
    total_minutes = int(round(hours * 60.0))
    if total_minutes < 1:
        return "<1 min"
    if total_minutes < 60:
        return f"{total_minutes} min"
    H = total_minutes // 60
    M = total_minutes % 60
    return f"about {H} h {M} min"


def remaining_energy_wh(
    remaining_capacity_mah: float, battery_voltage_v: float
) -> Optional[float]:
    if battery_voltage_v <= 0:
        return None
    return (remaining_capacity_mah / 1000.0) * battery_voltage_v


def full_effective_energy_wh(
    effective_capacity_mah: float, battery_voltage_v: float
) -> Optional[float]:
    if battery_voltage_v <= 0:
        return None
    return (effective_capacity_mah / 1000.0) * battery_voltage_v


MODE_ROLLING = "Using rolling average current"
MODE_INSTANT = "Using instantaneous current fallback"
MODE_NONE = "No estimate (need current > 1 mA or missing data)"


@dataclass(frozen=True)
class RuntimeEstimateResult:
    remaining_runtime: str
    full_runtime: str
    remaining_energy_wh: str
    full_energy_wh: str
    mode_label: str
    is_valid: bool


def _all_invalid(mode: str) -> RuntimeEstimateResult:
    return RuntimeEstimateResult(
        remaining_runtime="--",
        full_runtime="--",
        remaining_energy_wh="--",
        full_energy_wh="--",
        mode_label=mode,
        is_valid=False,
    )


def compute_runtime_estimate(
    battery_percent: Optional[float],
    battery_voltage_v: Optional[float],
    current_ma: Optional[float],
    rolling_avg_ma: Optional[float],
    *,
    nominal_capacity_mah: Optional[float] = None,
    min_current_ma: float = MIN_ESTIMATE_CURRENT_MA,
) -> RuntimeEstimateResult:
    """
    Build all display strings. Returns is_valid=False when core inputs missing
    or current too small (still fills energy with "--" where needed).
    """
    nominal = (
        float(nominal_capacity_mah)
        if nominal_capacity_mah is not None
        else NOMINAL_BATTERY_CAPACITY_MAH
    )
    if math.isnan(nominal) or nominal <= 0:
        nominal = NOMINAL_BATTERY_CAPACITY_MAH
    eff = get_effective_capacity_mah(
        nominal_capacity_mah=nominal, usable_factor=USABLE_CAPACITY_FACTOR
    )

    v = battery_voltage_v
    pct = battery_percent

    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return _all_invalid(MODE_NONE)

    pct_clamped = max(0.0, min(100.0, float(pct)))
    rem_mah = estimate_remaining_capacity_mah(pct_clamped, eff)

    n_roll = normalize_current_to_ma(rolling_avg_ma)
    n_inst = normalize_current_to_ma(current_ma)

    mode = MODE_NONE
    est_ma: Optional[float] = None
    if n_roll is not None and n_roll > min_current_ma:
        est_ma = n_roll
        mode = MODE_ROLLING
    elif n_inst is not None and n_inst > min_current_ma:
        est_ma = n_inst
        mode = MODE_INSTANT

    rem_wh_s = "--"
    full_wh_s = "--"
    if v is not None and not (isinstance(v, float) and math.isnan(v)) and v > 0:
        rw = remaining_energy_wh(rem_mah, float(v))
        fw = full_effective_energy_wh(eff, float(v))
        if rw is not None:
            rem_wh_s = f"{rw:.2f} Wh"
        if fw is not None:
            full_wh_s = f"{fw:.2f} Wh"

    if est_ma is None:
        return RuntimeEstimateResult(
            remaining_runtime="--",
            full_runtime="--",
            remaining_energy_wh=rem_wh_s,
            full_energy_wh=full_wh_s,
            mode_label=mode,
            is_valid=False,
        )

    rem_h = estimate_runtime_hours(rem_mah, est_ma, min_current_ma)
    full_h = estimate_full_runtime_hours(eff, est_ma, min_current_ma)

    return RuntimeEstimateResult(
        remaining_runtime=format_duration_hours(rem_h),
        full_runtime=format_duration_hours(full_h),
        remaining_energy_wh=rem_wh_s,
        full_energy_wh=full_wh_s,
        mode_label=mode,
        is_valid=True,
    )
