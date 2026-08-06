from __future__ import annotations

from typing import Any

from nix_settings.gui.window import SettingsWindow
from nix_settings.ipc.instance import APPLICATION_ID


def run_gui(page: str = "sound") -> int:
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    class Application(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.settings_window: SettingsWindow | None = None

        def do_activate(self) -> None:
            if self.settings_window is None:
                self.settings_window = SettingsWindow(Gtk, Gdk, GLib, self, page)
            self.settings_window.present()

    application: Any = Application()
    return int(application.run(["nix-settings"]))
