"""Subprocess-based ADB execution with timeouts and structured results."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from utils.parsers import parse_adb_devices

log = logging.getLogger(__name__)


@dataclass
class AdbResult:
    """Outcome of one ADB invocation."""

    stdout: str
    stderr: str
    returncode: int
    command: list[str]
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class AdbService:
    """Run `adb` with consistent error handling (no UI)."""

    def __init__(self, adb_path: str, default_timeout_s: float = 35.0) -> None:
        self.adb_path = adb_path or "adb"
        self.default_timeout_s = default_timeout_s

    def set_adb_path(self, path: str) -> None:
        self.adb_path = path or "adb"

    def resolve_executable(self) -> Optional[str]:
        """Return usable adb path or None if missing."""
        p = self.adb_path.strip()
        if not p:
            p = "adb"
        expanded = Path(p).expanduser()
        if expanded.is_file():
            return str(expanded.resolve())
        which = shutil.which(p)
        return which

    def run(
        self,
        adb_args: Sequence[str],
        serial: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AdbResult:
        exe = self.resolve_executable()
        if not exe:
            cmd = self._build_command("adb", list(adb_args), serial)
            return AdbResult(
                "",
                "ADB executable not found. Set path or install platform-tools.",
                127,
                cmd,
            )

        cmd = self._build_command(exe, list(adb_args), serial)
        t = timeout if timeout is not None else self.default_timeout_s
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=t,
                creationflags=creationflags,
            )
            return AdbResult(
                proc.stdout or "",
                proc.stderr or "",
                proc.returncode,
                cmd,
            )
        except subprocess.TimeoutExpired:
            log.warning("ADB timeout: %s", cmd)
            return AdbResult(
                "",
                f"Command timed out after {t}s",
                124,
                cmd,
                timed_out=True,
            )
        except FileNotFoundError:
            return AdbResult("", f"File not found: {exe}", 127, cmd)
        except OSError as e:
            return AdbResult("", str(e), 126, cmd)

    @staticmethod
    def _build_command(exe: str, adb_args: list[str], serial: Optional[str]) -> list[str]:
        cmd = [exe]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(adb_args)
        return cmd

    def devices(self) -> tuple[list[tuple[str, str]], AdbResult]:
        res = self.run(["devices", "-l"])
        if not res.ok:
            return [], res
        return parse_adb_devices(res.stdout), res

    def tcpip(self, serial: str, port: int) -> AdbResult:
        return self.run(["tcpip", str(port)], serial=serial)

    def usb(self, target: str) -> AdbResult:
        return self.run(["usb"], serial=target)

    def connect(self, host: str, port: int) -> AdbResult:
        return self.run(["connect", f"{host}:{port}"], serial=None)

    def disconnect(self, endpoint: Optional[str] = None) -> AdbResult:
        if endpoint:
            return self.run(["disconnect", endpoint], serial=None)
        return self.run(["disconnect"], serial=None)

    def shell(self, serial: str, shell_args: Sequence[str]) -> AdbResult:
        return self.run(["shell", *shell_args], serial=serial)

    def shell_line(self, serial: str, shell_command: str) -> AdbResult:
        return self.run(["shell", shell_command], serial=serial)
