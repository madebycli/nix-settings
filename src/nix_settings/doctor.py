from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _gi_checks() -> list[Check]:
    checks: list[Check] = []
    try:
        import gi

        checks.append(Check("PyGObject", True, "available"))
        try:
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            checks.append(Check("GTK 3", True, "typelib available"))
        except (ImportError, ValueError) as exc:
            checks.append(Check("GTK 3", False, str(exc)))
        try:
            gi.require_version("GtkLayerShell", "0.1")
            from gi.repository import GtkLayerShell  # noqa: F401

            checks.append(Check("GTK Layer Shell", True, "typelib available"))
        except (ImportError, ValueError) as exc:
            checks.append(Check("GTK Layer Shell", False, str(exc)))
    except ImportError as exc:
        checks.extend(
            [
                Check("PyGObject", False, str(exc)),
                Check("GTK 3", False, "PyGObject unavailable"),
                Check("GTK Layer Shell", False, "PyGObject unavailable"),
            ]
        )
    return checks


def _socket_available(runtime: str | None) -> tuple[bool, str]:
    if not runtime:
        return False, "XDG_RUNTIME_DIR is not set"
    pipewire = Path(runtime) / "pipewire-0"
    if pipewire.exists():
        return True, str(pipewire)
    return False, f"missing {pipewire}"


def _runtime_command(args: list[str]) -> tuple[bool, str]:
    executable = shutil.which(args[0])
    if executable is None:
        return False, f"{args[0]} not found"
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    detail = completed.stderr.strip() or completed.stdout.strip().splitlines()[0:1]
    if isinstance(detail, list):
        detail = detail[0] if detail else "command completed"
    return completed.returncode == 0, str(detail or "command completed")


def collect_checks() -> list[Check]:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    pipewire_ok, pipewire_detail = _socket_available(runtime)
    audio_server_ok, audio_server_detail = _runtime_command(["pw-dump"])
    wireplumber_ok, wireplumber_detail = _runtime_command(["wpctl", "status"])
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    checks = _gi_checks()
    checks.extend(
        [
            Check(
                "XDG runtime directory",
                bool(runtime and Path(runtime).is_dir()),
                runtime or "not set",
            ),
            Check("PipeWire socket", pipewire_ok, pipewire_detail),
            Check("Active audio server", audio_server_ok, audio_server_detail),
            Check("WirePlumber", wireplumber_ok, wireplumber_detail),
            Check("wpctl", shutil.which("wpctl") is not None, shutil.which("wpctl") or "not found"),
            Check(
                "pw-dump",
                shutil.which("pw-dump") is not None,
                shutil.which("pw-dump") or "not found",
            ),
            Check(
                "Wayland display",
                bool(wayland_display),
                wayland_display or "WAYLAND_DISPLAY is not set",
            ),
            Check(
                "Wayland session",
                session_type == "wayland" or bool(wayland_display),
                f"session type: {session_type}",
            ),
        ]
    )
    return checks


def run_doctor(output: TextIO) -> int:
    output.write("Nix Settings doctor\n")
    output.write("===================\n")
    checks = collect_checks()
    for check in checks:
        status = "OK" if check.ok else ("WARN" if not check.required else "FAIL")
        output.write(f"[{status}] {check.name}: {check.detail}\n")
    required_failures = [check for check in checks if check.required and not check.ok]
    result = (
        "ready\n"
        if not required_failures
        else f"{len(required_failures)} required check(s) failed\n"
    )
    output.write(f"\nResult: {result}")
    return 0 if not required_failures else 1
