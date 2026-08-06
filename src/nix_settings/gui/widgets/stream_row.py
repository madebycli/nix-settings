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
        on_interaction: Callable[[bool], None],
        on_scroll: Callable[[Any], None],
    ) -> None:
        self.volume_control: VolumeControl | None = None
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.widget.get_style_context().add_class("stream-row")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        icon = Gtk.Image.new_from_icon_name(
            stream.application_icon or "audio-x-generic-symbolic",
            Gtk.IconSize.BUTTON,
        )
        icon.set_size_request(22, 22)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label=stream.application_name, xalign=0)
        title.get_style_context().add_class("stream-title")
        title.set_ellipsize(3)
        title.set_tooltip_text(stream.application_name)

        default_detail = "Recording" if stream.direction is AudioDirection.RECORDING else "Playback"
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

        controls_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        route_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        route_label = Gtk.Label(label="ROUTE", xalign=0)
        route_label.get_style_context().add_class("control-label")
        routing = DeviceSelector(
            Gtk,
            devices,
            stream.device_id,
            lambda device_id: on_move(stream.id, device_id),
            on_scroll,
        )
        route_box.pack_start(route_label, False, False, 0)
        route_box.pack_start(routing.widget, False, False, 0)

        volume_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        volume_label = Gtk.Label(label="VOLUME", xalign=0)
        volume_label.get_style_context().add_class("control-label")
        controls = VolumeControl(
            Gtk,
            GLib,
            stream.volume,
            stream.is_muted,
            lambda value: on_volume(stream.id, value),
            lambda muted: on_mute(stream.id, muted),
            on_interaction,
            on_scroll,
        )
        self.volume_control = controls
        volume_box.pack_start(volume_label, False, False, 0)
        volume_box.pack_start(controls.widget, False, False, 0)

        controls_row.pack_start(route_box, True, True, 0)
        controls_row.pack_end(volume_box, False, False, 0)
        self.widget.pack_start(controls_row, False, False, 0)
