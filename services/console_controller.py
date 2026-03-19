"""Orchestrates tester workflows; no Qt widgets. Called from UI (often via background thread)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from services.adb_service import AdbResult, AdbService
from services.wifi_service import MANUAL_WIFI_MESSAGE, WifiService


@dataclass
class StepLog:
    title: str
    command: list[str]
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool


@dataclass
class WorkflowResult:
    ok: bool
    user_message: str
    technical_steps: List[StepLog] = field(default_factory=list)
    ip: Optional[str] = None
    devices: Optional[list[tuple[str, str]]] = None


def _result_to_step(title: str, res: AdbResult) -> StepLog:
    return StepLog(
        title=title,
        command=res.command,
        stdout=res.stdout,
        stderr=res.stderr,
        returncode=res.returncode,
        timed_out=res.timed_out,
    )


def discover_adb_candidates() -> list[str]:
    """Common install locations on Windows (non-exhaustive)."""
    out: list[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        p = Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        if p.is_file():
            out.append(str(p))
    prog = os.environ.get("ProgramFiles", "C:\\Program Files")
    p2 = Path(prog) / "Android" / "android-sdk" / "platform-tools" / "adb.exe"
    if p2.is_file():
        out.append(str(p2))
    from shutil import which

    w = which("adb")
    if w:
        out.append(w)
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


class ConsoleController:
    """High-level operations for the main window."""

    def __init__(self, adb_path: str) -> None:
        self.adb_path = adb_path
        self._last_usb_serial: str = ""

    def set_adb_path(self, path: str) -> None:
        self.adb_path = path

    def last_usb_serial(self) -> str:
        return self._last_usb_serial

    def adb(self) -> AdbService:
        return AdbService(self.adb_path)

    def refresh_devices(self) -> tuple[list[tuple[str, str]], WorkflowResult]:
        adb = self.adb()
        devices, res = adb.devices()
        steps = [_result_to_step("adb devices -l", res)]
        if not res.ok:
            return [], WorkflowResult(
                False,
                "Could not list devices. Check ADB path and USB connection.",
                steps,
                devices=[],
            )
        return devices, WorkflowResult(
            True, f"Found {len(devices)} device(s).", steps, devices=devices
        )

    def read_device_ip(self, serial: str) -> WorkflowResult:
        adb = self.adb()
        wifi = WifiService(adb)
        ip, attempts = wifi.read_wlan0_ip(serial)
        steps = [_result_to_step(f"read IP attempt {i + 1}", a) for i, a in enumerate(attempts)]
        if not ip:
            return WorkflowResult(
                False,
                "Could not read a Wi-Fi IPv4 address. On the device, open Settings and "
                "confirm Wi‑Fi is connected to your lab network. Then try Read IP again. "
                "If it still fails, find the IP on the router (DHCP clients) or on the device "
                "status screen and use Connect to device via IP.",
                steps,
                None,
            )
        return WorkflowResult(True, f"Device IP: {ip}", steps, ip)

    def enable_adb_over_wifi(
        self,
        usb_serial: str,
        port: int,
        ssid: str,
        password: str,
    ) -> WorkflowResult:
        """tcpip -> enable Wi-Fi -> optional join -> read IP -> adb connect."""
        adb = self.adb()
        wifi = WifiService(adb)
        steps: list[StepLog] = []

        if not usb_serial:
            return WorkflowResult(False, "Select a USB device first.", steps)

        if ":" not in usb_serial:
            self._last_usb_serial = usb_serial

        r_tcp = adb.tcpip(usb_serial, port)
        steps.append(_result_to_step("adb tcpip", r_tcp))
        if not r_tcp.ok:
            return WorkflowResult(
                False,
                "ADB tcpip mode failed. Check device authorization and try again.",
                steps,
            )

        r_w = wifi.enable_wifi_radio(usb_serial)
        steps.append(_result_to_step("svc wifi enable", r_w))

        if ssid.strip():
            join = wifi.try_join_network(usb_serial, ssid, password)
            steps.append(
                StepLog(
                    title="Wi-Fi join probe / attempt",
                    command=["shell", "cmd", "wifi", "…"],
                    stdout=join.raw_stdout,
                    stderr=join.message if not join.ok else join.raw_stderr,
                    returncode=0 if join.ok else 1,
                    timed_out=False,
                )
            )
        else:
            steps.append(
                StepLog(
                    "Wi-Fi join",
                    [],
                    "",
                    "SSID empty — skipped automated join. Connect manually if needed.",
                    0,
                    False,
                )
            )

        ip_res = self.read_device_ip(usb_serial)
        steps.extend(ip_res.technical_steps)
        if not ip_res.ok or not ip_res.ip:
            msg = ip_res.user_message
            if MANUAL_WIFI_MESSAGE not in msg:
                msg = f"{msg} {MANUAL_WIFI_MESSAGE}"
            return WorkflowResult(False, msg.strip(), steps, None)

        ip = ip_res.ip
        r_conn = adb.connect(ip, port)
        steps.append(_result_to_step("adb connect", r_conn))
        out = (r_conn.stdout + r_conn.stderr).lower()
        if not r_conn.ok or "unable" in out or "failed" in out:
            return WorkflowResult(
                False,
                f"Could not connect to {ip}:{port}. Verify network and device listening.",
                steps,
                ip,
            )

        return WorkflowResult(
            True,
            f"ADB over Wi-Fi active at {ip}:{port}. You may unplug USB.",
            steps,
            ip,
        )

    def disable_adb_over_wifi(
        self,
        target_for_usb: str,
        ip: Optional[str],
        port: int,
    ) -> WorkflowResult:
        """Disconnect TCP; ask device to prefer USB when possible."""
        adb = self.adb()
        steps: list[StepLog] = []

        if ip:
            d1 = adb.disconnect(f"{ip}:{port}")
            steps.append(_result_to_step("adb disconnect", d1))

        usb_target = target_for_usb or self._last_usb_serial
        if usb_target and ":" not in usb_target:
            r_usb = adb.usb(usb_target)
            steps.append(_result_to_step("adb usb", r_usb))
        else:
            steps.append(
                StepLog(
                    "adb usb",
                    [],
                    "",
                    "No USB serial available — disconnected TCP only. Reconnect USB and refresh.",
                    0,
                    False,
                )
            )

        return WorkflowResult(
            True,
            "ADB over Wi-Fi disabled. Reconnect USB if needed and click Refresh Devices.",
            steps,
        )

    def connect_tcp_manual(self, ip: str, port: int) -> WorkflowResult:
        adb = self.adb()
        if not ip.strip():
            return WorkflowResult(False, "Enter an IP address.")
        r = adb.connect(ip.strip(), port)
        steps = [_result_to_step("adb connect", r)]
        out = (r.stdout + r.stderr).lower()
        if not r.ok or "unable" in out:
            return WorkflowResult(False, "adb connect failed — see diagnostics.", steps, None)
        return WorkflowResult(
            True,
            f"Connected to {ip.strip()}:{port}. Refresh devices and select the network device.",
            steps,
            ip.strip(),
        )

    def disconnect_tcp(self, ip: Optional[str], port: int) -> WorkflowResult:
        adb = self.adb()
        steps: list[StepLog] = []
        if ip:
            d = adb.disconnect(f"{ip}:{port}")
            steps.append(_result_to_step("adb disconnect", d))
        else:
            d = adb.disconnect(None)
            steps.append(_result_to_step("adb disconnect (all)", d))
        return WorkflowResult(True, "TCP session disconnected.", steps)

    def run_manual_shell(self, target: str, command: str) -> WorkflowResult:
        adb = self.adb()
        if not target.strip():
            return WorkflowResult(False, "No target device selected.")
        res = adb.shell_line(target, command)
        steps = [_result_to_step("manual shell", res)]
        msg = "Command finished." if res.ok else "Command finished with errors — see raw output."
        return WorkflowResult(res.ok, msg, steps)
