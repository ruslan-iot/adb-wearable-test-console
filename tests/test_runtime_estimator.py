"""Runtime estimator (3300 mAh, 0.85 usable, rolling primary)."""

from __future__ import annotations

import math

from utils.runtime_estimator import (
    NOMINAL_BATTERY_CAPACITY_MAH,
    USABLE_CAPACITY_FACTOR,
    compute_runtime_estimate,
    estimate_remaining_capacity_mah,
    format_duration_hours,
    get_effective_capacity_mah,
    normalize_current_to_ma,
)


def test_effective_capacity() -> None:
    assert get_effective_capacity_mah() == NOMINAL_BATTERY_CAPACITY_MAH * USABLE_CAPACITY_FACTOR


def test_normalize_current_to_ma() -> None:
    assert normalize_current_to_ma(177.0) == 177.0
    assert normalize_current_to_ma(0.177) == 177.0
    assert normalize_current_to_ma(None) is None
    assert normalize_current_to_ma(float("nan")) is None


def test_format_duration_hours() -> None:
    assert format_duration_hours(None) == "--"
    assert format_duration_hours(-1) == "--"
    assert format_duration_hours(0.005) == "<1 min"
    assert format_duration_hours(0.02) == "1 min"
    assert format_duration_hours(0.75) == "45 min"
    assert format_duration_hours(3.58) == "about 3 h 35 min"


def test_example_1_user_spec() -> None:
    eff = 3300 * 0.85
    assert math.isclose(eff, 2805.0)
    rem_mah = estimate_remaining_capacity_mah(95.0, eff)
    assert math.isclose(rem_mah, 2664.75)
    t_rem = rem_mah / 177.0
    assert math.isclose(t_rem, 15.055, rel_tol=1e-3)
    t_full = eff / 177.0
    assert math.isclose(t_full, 15.847, rel_tol=1e-3)


def test_compute_uses_rolling_first() -> None:
    r = compute_runtime_estimate(
        95.0,
        4.0,
        current_ma=50.0,
        rolling_avg_ma=177.0,
    )
    assert r.is_valid
    assert "rolling" in r.mode_label.lower()
    assert r.remaining_runtime != "--"


def test_compute_fallback_instant() -> None:
    r = compute_runtime_estimate(
        50.0,
        4.0,
        current_ma=600.0,
        rolling_avg_ma=None,
    )
    assert r.is_valid
    assert "instantaneous" in r.mode_label.lower()


def test_low_current_invalid_runtime() -> None:
    # Values < 1 are treated as amperes → still sub-1 mA after ×1000
    r = compute_runtime_estimate(80.0, 4.0, 0.00015, 0.0002)
    assert not r.is_valid
    assert r.remaining_runtime == "--"
