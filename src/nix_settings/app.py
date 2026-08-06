from __future__ import annotations

import os
import sys
from typing import Any

from nix_settings.gui.window import SettingsWindow
from nix_settings.ipc.instance import APPLICATION_ID


def run_gui(page: str = "sound") -> int:
    if not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "Nix Settings requires a Wayland session with layer-shell support.",
            file=sys.stderr,
        )
        return 1

    try:
        import gi

        gi.require_version("Gdk", "3.0")
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell
    except (ImportError, ValueError) as exc:
        print(f"Nix Settings cannot load GTK3 Layer Shell: {exc}", file=sys.stderr)
        return 1

    class Application(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.settings_window: SettingsWindow | None = None

        def do_activate(self) -> None:
            if self.settings_window is None:
                self.settings_window = SettingsWindow(
                    Gtk,
                    Gdk,
                    GLib,
                    GtkLayerShell,
                    self,
                    page,
                )
            self.settings_window.present()

    application: Any = Application()
    return int(application.run(["nix-settings"]))
