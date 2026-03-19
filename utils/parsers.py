"""Robust parsing helpers for ADB / shell output."""

from __future__ import annotations

import re
from typing import Optional


def parse_adb_devices(output: str) -> list[tuple[str, str]]:
    """
    Parse `adb devices` output into (serial, state) pairs.
    Skips header line and empty lines.
    """
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    devices: list[tuple[str, str]] = []
    for line in lines:
        if line.startswith("List of devices"):
            continue
        if "\t" in line:
            parts = line.split("\t", 1)
        else:
            parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        serial, state = parts[0].strip(), parts[1].strip().lower()
        if serial:
            devices.append((serial, state))
    return devices


# IPv4 pattern (not 0.0.0.0)
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)


def parse_ipv4_from_text(text: str) -> Optional[str]:
    """Extract first plausible non-loopback IPv4 from free-form text."""
    for m in _IPV4_RE.finditer(text or ""):
        ip = m.group(0)
        if ip.startswith("127."):
            continue
        if ip == "0.0.0.0":
            continue
        if ip.startswith("169.254."):
            continue
        return ip
    return None


def _is_rfc1918(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


def best_lan_ipv4(text: str) -> Optional[str]:
    """
    Pick a sensible LAN IPv4 from messy command output.
    Prefers RFC1918 addresses; skips loopback, zero, and link-local (169.254.x).
    """
    uniq: list[str] = []
    seen: set[str] = set()
    for m in _IPV4_RE.finditer(text or ""):
        ip = m.group(0)
        if ip.startswith("127.") or ip == "0.0.0.0" or ip.startswith("169.254."):
            continue
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    if not uniq:
        return None
    for ip in uniq:
        if _is_rfc1918(ip):
            return ip
    return uniq[0]


_ROUTE_SRC_RE = re.compile(
    r"\bsrc\s+((?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3})\b"
)


def parse_ipv4_route_src(text: str) -> Optional[str]:
    """
    Parse `src x.x.x.x` from `ip -4 route get 1.1.1.1` (default route source IP).
    """
    m = _ROUTE_SRC_RE.search(text or "")
    if not m:
        return None
    ip = m.group(1)
    if ip.startswith("127.") or ip.startswith("169.254."):
        return None
    return ip


_LINK_ADDR_RE = re.compile(
    r"LinkAddresses:\s*\[([^\]]+)\]",
    re.IGNORECASE | re.MULTILINE,
)


def parse_ipv4_from_dumpsys_wifi(text: str) -> Optional[str]:
    """
    Extract IPv4 from `dumpsys wifi` LinkAddresses / ipAddress lines (Android varies by version).
    """
    if not text:
        return None
    # LinkAddresses: [ fe80::/64,192.168.88.54/24 ]
    for m in _LINK_ADDR_RE.finditer(text):
        block = m.group(1)
        ip = best_lan_ipv4(block)
        if ip:
            return ip
    for pat in (
        r"ipAddress[=:\s]+(\d{1,3}(?:\.\d{1,3}){3})\b",
        r"mIpAddress[=:\s]+(\d{1,3}(?:\.\d{1,3}){3})\b",
        r"Wi-Fi IP address:\s*(\d{1,3}(?:\.\d{1,3}){3})\b",
    ):
        mm = re.search(pat, text, re.IGNORECASE)
        if mm:
            ip = mm.group(1)
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    return None


def parse_int_file_content(content: str) -> Optional[int]:
    """Parse integer from sysfs-style single-line file content."""
    s = content.strip().split()[0] if content.strip() else ""
    if not s or not re.match(r"^-?\d+$", s):
        return None
    return int(s)


def parse_thermal_zone_temp_mc_to_c(content: str) -> Optional[float]:
    """
    thermal_zoneN/temp is typically millidegrees Celsius.
    """
    v = parse_int_file_content(content)
    if v is None:
        return None
    return v / 1000.0


def battery_current_raw_to_display_ma(raw: int) -> tuple[int, float]:
    """
    sysfs `current_now` is usually **microamps**, but some OEMs expose **milliamps**
    as a small integer (e.g. 144 meaning 144 mA). If dividing by 1000 yields < 1 mA
    while |raw| >= 100, treat **raw as milliamps** (absolute display value).
    """
    a = abs(raw)
    if a == 0:
        return raw, 0.0
    ma_from_microamps = a / 1000.0
    if ma_from_microamps < 1.0 and a >= 100:
        return raw, float(a)
    return raw, ma_from_microamps


def parse_battery_current_ua_to_ma_display(content: str) -> tuple[Optional[int], Optional[float]]:
    """
    Returns (raw integer from sysfs, display milliamps, positive magnitude).
    Raw is typically microamps; see :func:`battery_current_raw_to_display_ma`.
    """
    raw = parse_int_file_content(content)
    if raw is None:
        return None, None
    r, ma = battery_current_raw_to_display_ma(raw)
    return r, ma


def parse_dumpsys_battery_level(text: str) -> Optional[float]:
    m = re.search(r"level:\s*(\d+)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def parse_dumpsys_battery_voltage_mv(text: str) -> Optional[float]:
    """Voltage in mV from dumpsys battery -> volts."""
    m = re.search(r"(?:voltage|Voltage):\s*(\d+)", text)
    if m:
        return float(m.group(1)) / 1000.0
    return None


def parse_dumpsys_battery_current_ua(text: str) -> tuple[Optional[int], Optional[float]]:
    """
    Try to read current from dumpsys (microamps in some builds).
    Returns (raw_ua, display_ma_abs).
    """
    for pat in (
        r"current now:\s*(-?\d+)",
        r"Current now:\s*(-?\d+)",
        r"current_now:\s*(-?\d+)",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                raw = int(m.group(1))
                _, ma = battery_current_raw_to_display_ma(raw)
                return raw, ma
            except ValueError:
                continue
    return None, None
