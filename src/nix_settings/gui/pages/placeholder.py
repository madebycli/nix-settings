from __future__ import annotations

from typing import Any


def build_placeholder(Gtk: Any, title: str) -> Any:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)
    heading = Gtk.Label(label=title)
    heading.add_css_class("page-title")
    message = Gtk.Label(label="Not implemented yet")
    message.add_css_class("state-detail")
    box.append(heading)
    box.append(message)
    return box
