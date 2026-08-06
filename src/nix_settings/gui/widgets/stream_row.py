from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from nix_settings.audio.models import AudioDevice, AudioDirection, AudioStream
from nix_settings.gui.widgets.device_selector import DeviceSelector
from nix_settings.gui.widgets.volume_control import VolumeControl


class StreamRow:
    def __init__(
        self,
        Gtk: Any,
        GLib: Any,
        stream: AudioStream,
        devices: Sequence[AudioDevice],
        on_volume: Callable[[int, float], None],
        on_mute: Callable[[int, bool], None],
        on_move: Callable[[int, int], None],
    ) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.widget.get_style_context().add_class("stream-row")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name(
            stream.application_icon or "audio-x-generic-symbolic",
            Gtk.IconSize.BUTTON,
        )
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=stream.application_name, xalign=0)
        title.get_style_context().add_class("stream-title")
        title.set_ellipsize(3)
        title.set_tooltip_text(stream.application_name)
        default_detail = (
            "Microphone capture"
            if stream.direction is AudioDirection.RECORDING
            else "Audio playback"
        )
        detail_text = stream.media_name or default_detail
        detail = Gtk.Label(label=detail_text, xalign=0)
        detail.get_style_context().add_class("stream-detail")
        detail.set_ellipsize(3)
        detail.set_tooltip_text(detail_text)
        text.pack_start(title, False, False, 0)
        text.pack_start(detail, False, False, 0)
        text.set_hexpand(True)
        header.pack_start(icon, False, False, 0)
        header.pack_start(text, True, True, 0)
        self.widget.pack_start(header, False, False, 0)

        route_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        route_label = Gtk.Label(label="Route", xalign=0)
        route_label.set_size_request(72, -1)
        route_label.get_style_context().add_class("control-label")
        routing = DeviceSelector(
            Gtk,
            devices,
            stream.device_id,
            lambda device_id: on_move(stream.id, device_id),
        )
        route_row.pack_start(route_label, False, False, 0)
        route_row.pack_start(routing.widget, True, True, 0)
        self.widget.pack_start(route_row, False, False, 0)

        if stream.volume_is_writable:
            controls = VolumeControl(
                Gtk,
                GLib,
                stream.volume,
                stream.is_muted,
                lambda value: on_volume(stream.id, value),
                lambda muted: on_mute(stream.id, muted),
            )
            self.widget.pack_start(controls.widget, False, False, 0)
        else:
            mute = Gtk.ToggleButton(label="Block capture")
            mute.set_active(stream.is_muted)
            mute.set_size_request(120, 34)
            mute.get_style_context().add_class("pill")
            mute.connect("toggled", lambda button: on_mute(stream.id, bool(button.get_active())))
            self.widget.pack_start(mute, False, False, 0)
