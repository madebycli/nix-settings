from __future__ import annotations

from collections.abc import Callable
from typing import Any


class VolumeControl:
    def __init__(
        self,
        Gtk: Any,
        value: float,
        muted: bool,
        on_volume: Callable[[float], None],
        on_mute: Callable[[bool], None],
        *,
        allow_100: bool = False,
    ) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.scale.set_value(max(0.0, min(100.0, value * 100.0)))
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(True)
        self.scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.scale.connect("value-changed", lambda scale: on_volume(float(scale.get_value()) / 100.0))
        self.mute = Gtk.ToggleButton(label="Muted" if muted else "Mute")
        self.mute.add_css_class("pill")
        self.mute.set_active(muted)
        self.mute.connect("toggled", self._mute_changed, on_mute)
        self.widget.append(self.scale)
        self.widget.append(self.mute)
        if allow_100:
            full = Gtk.Button(label="100%")
            full.add_css_class("pill")
            full.connect("clicked", lambda *_: self.scale.set_value(100.0))
            self.widget.append(full)

    @staticmethod
    def _mute_changed(button: Any, callback: Callable[[bool], None]) -> None:
        muted = bool(button.get_active())
        button.set_label("Muted" if muted else "Mute")
        callback(muted)
