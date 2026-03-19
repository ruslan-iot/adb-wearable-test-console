"""Unit tests for parsing utilities."""

from __future__ import annotations

from utils.parsers import (
    battery_current_raw_to_display_ma,
    best_lan_ipv4,
    parse_adb_devices,
    parse_battery_current_ua_to_ma_display,
    parse_dumpsys_battery_level,
    parse_ipv4_from_dumpsys_wifi,
    parse_ipv4_from_text,
    parse_ipv4_route_src,
    parse_thermal_zone_temp_mc_to_c,
)


def test_parse_adb_devices_basic() -> None:
    out = """List of devices attached
R3CN30ABCD\tdevice
192.168.0.5:5555\tdevice
"""
    devs = parse_adb_devices(out)
    assert devs == [("R3CN30ABCD", "device"), ("192.168.0.5:5555", "device")]


def test_parse_adb_devices_unauthorized() -> None:
    out = "List of devices attached\nXYZ\tunauthorized\n"
    devs = parse_adb_devices(out)
    assert devs == [("XYZ", "unauthorized")]


def test_parse_ipv4() -> None:
    text = "inet 192.168.4.22/24 brd 192.168.4.255"
    assert parse_ipv4_from_text(text) == "192.168.4.22"
    assert parse_ipv4_from_text("no ip here") is None
    assert parse_ipv4_from_text("127.0.0.1") is None
    assert parse_ipv4_from_text("169.254.12.3") is None


def test_best_lan_ipv4_prefers_private() -> None:
    blob = "inet 10.0.0.2 peer 203.0.113.1"
    assert best_lan_ipv4(blob) == "10.0.0.2"


def test_parse_ipv4_route_src() -> None:
    out = "1.1.1.1 via 192.168.88.1 dev wlan0 src 192.168.88.54 uid 0"
    assert parse_ipv4_route_src(out) == "192.168.88.54"


def test_parse_ipv4_from_dumpsys_wifi() -> None:
    blob = "LinkAddresses: [ fe80::1/64,192.168.88.54/24 ]"
    assert parse_ipv4_from_dumpsys_wifi(blob) == "192.168.88.54"


def test_thermal_mc() -> None:
    assert parse_thermal_zone_temp_mc_to_c("45234\n") == 45.234


def test_current_sysfs() -> None:
    raw, ma = parse_battery_current_ua_to_ma_display("-1250000")
    assert raw == -1_250_000
    assert ma == 1250.0


def test_battery_current_oem_milliamps_small_int() -> None:
    """Some devices report 144 meaning 144 mA, not 144 µA."""
    r, ma = battery_current_raw_to_display_ma(-144)
    assert r == -144
    assert ma == 144.0
    _, ma2 = parse_battery_current_ua_to_ma_display("-144")
    assert ma2 == 144.0


def test_battery_current_standard_microamps() -> None:
    _, ma = battery_current_raw_to_display_ma(-144000)
    assert ma == 144.0


def test_dumpsys_level() -> None:
    blob = "  level: 87\n  scale: 100\n"
    assert parse_dumpsys_battery_level(blob) == 87.0
