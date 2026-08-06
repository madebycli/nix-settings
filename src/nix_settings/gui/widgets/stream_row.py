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
        self.widget = Gtk.Grid()
        self.widget.set_column_spacing(12)
        self.widget.set_row_spacing(8)
        self.widget.set_hexpand(True)
        self.widget.set_size_request(-1, 108)
        self.widget.get_style_context().add_class("stream-row")

        app = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        app.set_size_request(230, 40)
        app.set_valign(Gtk.Align.CENTER)
        app.get_style_context().add_class("stream-app")

        icon = Gtk.Image.new_from_icon_name(
            stream.application_icon or "audio-x-generic-symbolic",
            Gtk.IconSize.BUTTON,
        )
        icon.set_size_request(22, 22)
        icon.set_valign(Gtk.Align.CENTER)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text.set_size_request(195, 40)
        text.set_hexpand(False)
        text.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label=stream.application_name, xalign=0)
        title.set_single_line_mode(True)
        title.set_ellipsize(3)
        title.set_tooltip_text(stream.application_name)
        title.get_style_context().add_class("stream-title")

        default_detail = (
            "Recording" if stream.direction is AudioDirection.RECORDING else "Playback"
        )
        detail_text = stream.media_name or default_detail
        detail = Gtk.Label(label=detail_text, xalign=0)
        detail.set_single_line_mode(True)
        detail.set_ellipsize(3)
        detail.set_tooltip_text(detail_text)
        detail.get_style_context().add_class("stream-detail")

        text.pack_start(title, False, False, 0)
        text.pack_start(detail, False, False, 0)
        app.pack_start(icon, False, False, 0)
        app.pack_start(text, False, False, 0)

        route_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        route_row.set_hexpand(True)
        route_row.set_valign(Gtk.Align.CENTER)
        route_label = Gtk.Label(label="ROUTE", xalign=0)
        route_label.set_size_request(46, 34)
        route_label.set_valign(Gtk.Align.CENTER)
        route_label.get_style_context().add_class("control-label")
        routing = DeviceSelector(
            Gtk,
            devices,
            stream.device_id,
            lambda device_id: on_move(stream.id, device_id),
            on_scroll,
            width=300,
        )
        route_row.pack_start(route_label, False, False, 0)
        route_row.pack_start(routing.widget, True, True, 0)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_row.set_hexpand(True)
        volume_row.set_valign(Gtk.Align.CENTER)
        volume_label = Gtk.Label(label="VOLUME", xalign=0)
        volume_label.set_size_request(52, 30)
        volume_label.set_valign(Gtk.Align.CENTER)
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
        volume_row.pack_start(volume_label, False, False, 0)
        volume_row.pack_start(controls.widget, True, True, 0)

        self.widget.attach(app, 0, 0, 1, 1)
        self.widget.attach(route_row, 1, 0, 1, 1)
        self.widget.attach(volume_row, 0, 1, 2, 1)
