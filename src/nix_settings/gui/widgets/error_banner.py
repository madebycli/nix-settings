from __future__ import annotations

from typing import Any


class ErrorBanner:
    def __init__(self, Gtk: Any) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.widget.get_style_context().add_class("error-banner")
        self.widget.set_no_show_all(True)
        self.label = Gtk.Label(xalign=0)
        self.label.set_hexpand(True)
        self.label.set_line_wrap(True)
        dismiss = Gtk.Button(label="Dismiss")
        dismiss.get_style_context().add_class("pill")
        dismiss.connect("clicked", lambda *_: self.hide())
        self.widget.pack_start(self.label, True, True, 0)
        self.widget.pack_end(dismiss, False, False, 0)
        self.hide()

    def show(self, message: str, *, disconnected: bool = False) -> None:
        context = self.widget.get_style_context()
        context.remove_class("error-banner")
        context.remove_class("disconnected-banner")
        context.add_class("disconnected-banner" if disconnected else "error-banner")
        self.label.set_text(message)
        self.widget.show_all()

    def hide(self) -> None:
        self.widget.hide()
