"""Best-effort Wi-Fi control and IP discovery via ADB (Android 7+ aware)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from services.adb_service import AdbResult, AdbService
from utils.parsers import (
    best_lan_ipv4,
    parse_ipv4_from_dumpsys_wifi,
    parse_ipv4_from_text,
    parse_ipv4_route_src,
)

log = logging.getLogger(__name__)

MANUAL_WIFI_MESSAGE = (
    "Direct Wi-Fi joining is not supported on this Android build through standard ADB commands. "
    "Please connect the device to Wi-Fi manually, then click Read IP."
)


@dataclass
class WifiJoinCapability:
    """Result of probing whether automated join is plausible."""

    supported: bool
    detail: str


@dataclass
class WifiJoinResult:
    ok: bool
    message: str
    raw_stdout: str = ""
    raw_stderr: str = ""


class WifiService:
    def __init__(self, adb: AdbService) -> None:
        self._adb = adb

    def enable_wifi_radio(self, serial: str) -> AdbResult:
        return self._adb.shell_line(serial, "svc wifi enable")

    def probe_join_support(self, serial: str) -> tuple[WifiJoinCapability, AdbResult]:
        """
        Probe `cmd wifi` availability and whether connect-network appears in help.
        """
        res = self._adb.shell_line(serial, "cmd wifi help")
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        combined = out.lower()

        if res.returncode != 0 and "unknown" in combined and "cmd" in combined:
            return (
                WifiJoinCapability(False, "cmd wifi not available on this build."),
                res,
            )

        if "error" in combined and "wifi" in combined and len(out.strip()) < 200:
            if "unknown" in combined or "not found" in combined:
                return WifiJoinCapability(False, "cmd wifi not found."), res

        if "connect-network" not in out and "connectNetwork" not in out:
            # Some devices use different help text; try `cmd wifi` alone
            res2 = self._adb.shell_line(serial, "cmd wifi")
            out2 = (res2.stdout or "") + (res2.stderr or "")
            if "connect-network" not in out2 and "connectNetwork" not in out2:
                return (
                    WifiJoinCapability(
                        False,
                        "connect-network subcommand not advertised in cmd wifi help.",
                    ),
                    res,
                )

        return WifiJoinCapability(True, "cmd wifi connect-network appears available."), res

    def try_join_network(self, serial: str, ssid: str, password: str) -> WifiJoinResult:
        """
        Best-effort join using `cmd wifi connect-network` when probe says OK.
        Does not require root. May fail on Android 7 even if help lists command.
        """
        cap, probe_res = self.probe_join_support(serial)
        if not cap.supported:
            return WifiJoinResult(
                False,
                MANUAL_WIFI_MESSAGE,
                probe_res.stdout,
                probe_res.stderr,
            )

        ssid = ssid.strip()
        if not ssid:
            return WifiJoinResult(False, "SSID is empty.")

        # WPA2-PSK is most common for lab networks
        # Syntax: cmd wifi connect-network <ssid> wpa2 <pass>
        esc = _shell_single_quote(ssid)
        if password:
            pesc = _shell_single_quote(password)
            cmd = f"cmd wifi connect-network {esc} wpa2 {pesc}"
        else:
            cmd = f"cmd wifi connect-network {esc} open"

        res = self._adb.shell_line(serial, cmd)
        ok = res.ok and "fail" not in (res.stdout + res.stderr).lower()
        if not ok:
            return WifiJoinResult(
                False,
                "Wi-Fi join command ran but may have failed. "
                "If the device did not connect, use manual Wi-Fi and Read IP.",
                res.stdout,
                res.stderr,
            )
        return WifiJoinResult(True, "Join command completed.", res.stdout, res.stderr)

    def read_wifi_ipv4(self, serial: str) -> tuple[Optional[str], list[AdbResult]]:
        """
        Discover the device's Wi-Fi / LAN IPv4 for adb connect.
        Wearables often use non-standard interface names or hide wlan0 from toybox;
        we try many paths and fall back to dumpsys / routing / dhcp props.
        """
        attempts: list[AdbResult] = []

        ifaces = (
            "wlan0",
            "wlan1",
            "wlan2",
            "p2p0",
            "ap0",
            "softap0",
            "wifi-aware0",
            "mlan0",
            "tiwlan0",
        )
        for iface in ifaces:
            r = self._adb.shell_line(serial, f"ip addr show {iface}")
            attempts.append(r)
            ip = best_lan_ipv4(r.stdout) or parse_ipv4_from_text(r.stdout)
            if ip:
                return ip, attempts
            r2 = self._adb.shell_line(serial, f"ifconfig {iface}")
            attempts.append(r2)
            ip = best_lan_ipv4(r2.stdout) or parse_ipv4_from_text(r2.stdout)
            if ip:
                return ip, attempts

        # Source IP for default IPv4 route (often the active Wi-Fi address)
        r_route = self._adb.shell_line(serial, "ip -4 route get 1.1.1.1 2>/dev/null")
        attempts.append(r_route)
        ip = parse_ipv4_route_src(r_route.stdout)
        if ip:
            return ip, attempts

        r_all = self._adb.shell_line(serial, "ip -4 addr")
        attempts.append(r_all)
        ip = best_lan_ipv4(r_all.stdout)
        if ip:
            return ip, attempts

        r_dump = self._adb.shell_line(serial, "dumpsys wifi")
        attempts.append(r_dump)
        ip = parse_ipv4_from_dumpsys_wifi(r_dump.stdout)
        if ip:
            return ip, attempts

        for prop in (
            "dhcp.wlan0.ipaddress",
            "dhcp.wlan1.ipaddress",
            "wlan0.ipv4_address",
        ):
            r_prop = self._adb.shell_line(serial, f"getprop {prop}")
            attempts.append(r_prop)
            ip = parse_ipv4_from_text(r_prop.stdout)
            if ip:
                return ip, attempts

        return None, attempts

    def read_wlan0_ip(self, serial: str) -> tuple[Optional[str], list[AdbResult]]:
        """Backward-compatible alias for :meth:`read_wifi_ipv4`."""
        return self.read_wifi_ipv4(serial)


def _shell_single_quote(s: str) -> str:
    """Wrap for use inside adb shell single-quoted segment."""
    return "'" + s.replace("'", "'\\''") + "'"
