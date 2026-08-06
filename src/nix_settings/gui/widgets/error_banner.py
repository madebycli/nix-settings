from __future__ import annotations

from typing import Any


class ErrorBanner:
    def __init__(self, Gtk: Any) -> None:
        self._Gtk = Gtk
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.widget.add_css_class("error-banner")
        self.label = Gtk.Label(xalign=0)
        self.label.set_hexpand(True)
        self.label.set_wrap(True)
        dismiss = Gtk.Button(label="Dismiss")
        dismiss.add_css_class("pill")
        dismiss.connect("clicked", lambda *_: self.hide())
        self.widget.append(self.label)
        self.widget.append(dismiss)
        self.hide()

    def show(self, message: str, *, disconnected: bool = False) -> None:
        self.widget.remove_css_class("error-banner")
        self.widget.remove_css_class("disconnected-banner")
        self.widget.add_css_class("disconnected-banner" if disconnected else "error-banner")
        self.label.set_text(message)
        self.widget.set_visible(True)

    def hide(self) -> None:
        self.widget.set_visible(False)
