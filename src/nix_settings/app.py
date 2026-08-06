from __future__ import annotations

import os
import sys
import threading
from typing import Any

from nix_settings.audio.models import AudioSnapshot
from nix_settings.audio.wireplumber import WirePlumberBackend
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

    window: SettingsWindow | None = None
    loading = False
    backend = WirePlumberBackend()

    def finish_initial_load(
        application: Any,
        snapshot: AudioSnapshot,
        error: str | None,
    ) -> bool:
        nonlocal window, loading
        window = SettingsWindow(
            Gtk,
            Gdk,
            GLib,
            GtkLayerShell,
            application,
            backend,
            snapshot,
            error,
            page,
        )
        loading = False
        window.present()
        application.release()
        return False

    def load_initial(application: Any) -> None:
        try:
            snapshot = backend.snapshot()
            error: str | None = None
        except Exception as exc:  # noqa: BLE001 - startup boundary
            snapshot = AudioSnapshot.empty()
            error = str(exc)
        GLib.idle_add(finish_initial_load, application, snapshot, error)

    def activate(application: Any) -> None:
        nonlocal loading
        if window is not None:
            window.present()
            return
        if loading:
            return
        loading = True
        application.hold()
        threading.Thread(
            target=load_initial,
            args=(application,),
            name="sound-initial-snapshot",
            daemon=True,
        ).start()

    application = Gtk.Application(
        application_id=APPLICATION_ID,
        flags=Gio.ApplicationFlags.FLAGS_NONE,
    )
    application.connect("activate", activate)
    return int(application.run(["nix-settings"]))
