from __future__ import annotations

from collections.abc import Callable
from typing import Any


class VolumeControl:
    def __init__(
        self,
        Gtk: Any,
        GLib: Any,
        value: float,
        muted: bool,
        on_volume: Callable[[float], None],
        on_mute: Callable[[bool], None],
    ) -> None:
        self._GLib = GLib
        self._on_volume = on_volume
        self._volume_timeout: int | None = None
        self._dragging = False

        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(False)
        self.scale.set_value(max(0.0, min(100.0, value * 100.0)))

        self.percent = Gtk.Label(label=self._percent_text(value * 100.0))
        self.percent.set_size_request(48, -1)
        self.percent.set_xalign(1.0)
        self.percent.get_style_context().add_class("volume-value")

        self.mute = Gtk.ToggleButton(label="Mute")
        self.mute.set_active(muted)
        self.mute.set_size_request(72, 34)
        self.mute.set_tooltip_text("Mute this audio source")
        self.mute.get_style_context().add_class("pill")

        self.widget.pack_start(self.scale, True, True, 0)
        self.widget.pack_start(self.percent, False, False, 0)
        self.widget.pack_end(self.mute, False, False, 0)

        self.scale.connect("button-press-event", self._drag_started)
        self.scale.connect("button-release-event", self._drag_finished)
        self.scale.connect("value-changed", self._volume_changed)
        self.mute.connect("toggled", self._mute_changed, on_mute)

    @staticmethod
    def _percent_text(value: float) -> str:
        return f"{int(round(max(0.0, min(100.0, value))))}%"

    def _volume_changed(self, scale: Any) -> None:
        value = float(scale.get_value())
        self.percent.set_text(self._percent_text(value))
        if self._dragging:
            return
        self._schedule_emit(140)

    def _drag_started(self, _scale: Any, _event: Any) -> bool:
        self._dragging = True
        if self._volume_timeout is not None:
            self._GLib.source_remove(self._volume_timeout)
            self._volume_timeout = None
        return False

    def _drag_finished(self, _scale: Any, _event: Any) -> bool:
        self._dragging = False
        self._schedule_emit(40)
        return False

    def _schedule_emit(self, delay_ms: int) -> None:
        if self._volume_timeout is not None:
            self._GLib.source_remove(self._volume_timeout)
        self._volume_timeout = self._GLib.timeout_add(delay_ms, self._emit_volume)

    def _emit_volume(self) -> bool:
        self._volume_timeout = None
        self._on_volume(float(self.scale.get_value()) / 100.0)
        return False

    @staticmethod
    def _mute_changed(button: Any, callback: Callable[[bool], None]) -> None:
        callback(bool(button.get_active()))
