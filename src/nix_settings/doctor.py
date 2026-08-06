from __future__ import annotations

import os
import shutil
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
            gi.require_version("Gtk", "4.0")
            from gi.repository import Gtk  # noqa: F401

            checks.append(Check("GTK 4", True, "typelib available"))
        except (ImportError, ValueError) as exc:
            checks.append(Check("GTK 4", False, str(exc)))
        try:
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell  # noqa: F401

            checks.append(Check("Gtk4LayerShell", True, "typelib available", required=False))
        except (ImportError, ValueError) as exc:
            checks.append(Check("Gtk4LayerShell", False, str(exc), required=False))
    except ImportError as exc:
        checks.extend(
            [
                Check("PyGObject", False, str(exc)),
                Check("GTK 4", False, "PyGObject unavailable"),
                Check("Gtk4LayerShell", False, "PyGObject unavailable", required=False),
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


def _wireplumber_available(runtime: str | None) -> tuple[bool, str]:
    if not runtime:
        return False, "XDG_RUNTIME_DIR is not set"
    candidates = [Path(runtime) / "wireplumber", Path(runtime) / "pipewire-0-manager"]
    for candidate in candidates:
        if candidate.exists():
            return True, str(candidate)
    return (shutil.which("wpctl") is not None, "wpctl available; runtime marker not found")


def collect_checks() -> list[Check]:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    pipewire_ok, pipewire_detail = _socket_available(runtime)
    wireplumber_ok, wireplumber_detail = _wireplumber_available(runtime)
    display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    session_type = os.environ.get("XDG_SESSION_TYPE", "unknown")
    checks = _gi_checks()
    checks.extend(
        [
            Check("XDG runtime directory", bool(runtime and Path(runtime).is_dir()), runtime or "not set"),
            Check("PipeWire socket", pipewire_ok, pipewire_detail),
            Check("WirePlumber", wireplumber_ok, wireplumber_detail),
            Check("wpctl", shutil.which("wpctl") is not None, shutil.which("wpctl") or "not found"),
            Check("pw-dump", shutil.which("pw-dump") is not None, shutil.which("pw-dump") or "not found"),
            Check("Display session", bool(display), display or "WAYLAND_DISPLAY and DISPLAY are not set"),
            Check(
                "Wayland session",
                bool(os.environ.get("WAYLAND_DISPLAY")) or session_type == "wayland",
                f"session type: {session_type}",
                required=False,
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
    output.write(
        "\nResult: " + ("ready\n" if not required_failures else f"{len(required_failures)} required check(s) failed\n")
    )
    return 0 if not required_failures else 1
