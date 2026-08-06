from __future__ import annotations

APPLICATION_ID = "com.madebycli.NixSettings"


def application_flags() -> int:
    """Return Gio flags lazily so CLI-only commands do not require GTK."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    return int(Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
