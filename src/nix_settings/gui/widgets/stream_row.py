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
        stream: AudioStream,
        devices: Sequence[AudioDevice],
        on_volume: Callable[[int, float], None],
        on_mute: Callable[[int, bool], None],
        on_move: Callable[[int, int], None],
    ) -> None:
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.widget.add_css_class("stream-row")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name(stream.application_icon or "audio-x-generic-symbolic")
        icon.set_pixel_size(24)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=stream.application_name, xalign=0)
        title.add_css_class("stream-title")
        title.set_ellipsize(3)
        title.set_tooltip_text(stream.application_name)
        detail_text = stream.media_name or (
            "Microphone capture" if stream.direction is AudioDirection.RECORDING else "Audio playback"
        )
        detail = Gtk.Label(label=detail_text, xalign=0)
        detail.add_css_class("stream-detail")
        detail.set_ellipsize(3)
        detail.set_tooltip_text(detail_text)
        text.append(title)
        text.append(detail)
        text.set_hexpand(True)
        activity = Gtk.Label(label="ACTIVE" if stream.is_active else "IDLE")
        activity.add_css_class("status-chip")
        header.append(icon)
        header.append(text)
        header.append(activity)
        self.widget.append(header)

        routing = DeviceSelector(
            Gtk,
            devices,
            stream.device_id,
            lambda device_id: on_move(stream.id, device_id),
        )
        self.widget.append(routing.widget)
        if stream.volume_is_writable:
            controls = VolumeControl(
                Gtk,
                stream.volume,
                stream.is_muted,
                lambda value: on_volume(stream.id, value),
                lambda muted: on_mute(stream.id, muted),
            )
            self.widget.append(controls.widget)
        else:
            mute = Gtk.ToggleButton(label="Capture blocked" if stream.is_muted else "Block capture")
            mute.add_css_class("pill")
            mute.set_active(stream.is_muted)
            mute.connect("toggled", lambda button: on_mute(stream.id, bool(button.get_active())))
            self.widget.append(mute)
