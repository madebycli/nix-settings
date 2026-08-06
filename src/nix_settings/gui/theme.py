from __future__ import annotations

from importlib.resources import files
from typing import Any


def install_css(Gtk: Any, Gdk: Any) -> None:
    provider = Gtk.CssProvider()
    css = files("nix_settings.gui").joinpath("style.css").read_text(encoding="utf-8")
    provider.load_from_data(css.encode())
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
