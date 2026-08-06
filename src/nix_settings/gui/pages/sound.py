from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from typing import Any

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.models import AudioDevice, AudioDirection, AudioSnapshot, AudioStream
from nix_settings.audio.monitor import PipeWireMonitor
from nix_settings.gui.widgets.device_selector import DeviceSelector
from nix_settings.gui.widgets.error_banner import ErrorBanner
from nix_settings.gui.widgets.stream_row import StreamRow
from nix_settings.gui.widgets.volume_control import VolumeControl

LOGGER = logging.getLogger(__name__)


class SoundPage:
    def __init__(self, Gtk: Any, GLib: Any, backend: AudioBackend) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.backend = backend
        self.snapshot = AudioSnapshot.empty()
        self._refresh_lock = threading.Lock()
        self._destroyed = False
        self.monitor = PipeWireMonitor(self._monitor_changed, self._monitor_disconnected)

        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.widget.add_css_class("content")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Sound", xalign=0)
        title.add_css_class("page-title")
        title.set_hexpand(True)
        refresh = Gtk.Button(label="Refresh")
        refresh.add_css_class("pill")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.append(title)
        header.append(refresh)
        self.widget.append(header)

        self.error = ErrorBanner(Gtk)
        self.widget.append(self.error.widget)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_vexpand(True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.scroller.set_child(self.content)
        self.widget.append(self.scroller)
        self._render_loading()

    def start(self) -> None:
        self.refresh()
        self.monitor.start()

    def refresh(self) -> None:
        if self._destroyed or self._refresh_lock.locked():
            return
        threading.Thread(target=self._load_snapshot, name="sound-refresh", daemon=True).start()

    def _load_snapshot(self) -> None:
        with self._refresh_lock:
            try:
                snapshot = self.backend.snapshot()
            except Exception as exc:  # noqa: BLE001 - backend boundary
                self.GLib.idle_add(self._show_error, str(exc), True)
                return
            self.GLib.idle_add(self._apply_snapshot, snapshot)

    def _apply_snapshot(self, snapshot: AudioSnapshot) -> bool:
        if self._destroyed:
            return False
        self.snapshot = snapshot
        self.error.hide()
        self._clear_content()
        if not snapshot.outputs and not snapshot.inputs:
            self._render_state("No audio devices", "PipeWire returned an empty device graph.")
            return False
        self.content.append(
            self._device_card(
                "DEFAULT OUTPUT",
                snapshot.outputs,
                snapshot.default_output_id,
                AudioDirection.OUTPUT,
            )
        )
        self.content.append(
            self._device_card(
                "DEFAULT MICROPHONE",
                snapshot.inputs,
                snapshot.default_input_id,
                AudioDirection.INPUT,
            )
        )
        self.content.append(
            self._streams_card(
                "RECORDING / MICROPHONE STREAMS",
                snapshot.recording_streams,
                snapshot.inputs,
                "No applications are recording audio.",
            )
        )
        self.content.append(
            self._streams_card(
                "PLAYBACK / APPLICATION STREAMS",
                snapshot.playback_streams,
                snapshot.outputs,
                "No applications are playing audio.",
            )
        )
        return False

    def _device_card(
        self,
        heading: str,
        devices: Sequence[AudioDevice],
        selected_id: int | None,
        direction: AudioDirection,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        label = self.Gtk.Label(label=heading, xalign=0)
        label.add_css_class("section-title")
        card.append(label)
        if not devices:
            empty = self.Gtk.Label(label="No device available", xalign=0)
            empty.add_css_class("state-detail")
            card.append(empty)
            return card
        selected = next((device for device in devices if device.id == selected_id), devices[0])
        selector = DeviceSelector(
            self.Gtk,
            devices,
            selected.id,
            lambda device_id: self._operation(lambda: self.backend.set_default(device_id)),
        )
        card.append(selector.widget)
        title = self.Gtk.Label(label=selected.description, xalign=0)
        title.add_css_class("device-title")
        title.set_ellipsize(3)
        title.set_tooltip_text(selected.description)
        details = [selected.name]
        if selected.active_port:
            details.append(f"Port: {selected.active_port}")
        if selected.active_profile:
            details.append(f"Profile: {selected.active_profile}")
        detail = self.Gtk.Label(label="  •  ".join(details), xalign=0)
        detail.add_css_class("device-detail")
        detail.set_ellipsize(3)
        detail.set_tooltip_text("  •  ".join(details))
        card.append(title)
        card.append(detail)
        controls = VolumeControl(
            self.Gtk,
            selected.volume,
            selected.is_muted,
            lambda value: self._operation(lambda: self.backend.set_volume(selected.id, value)),
            lambda muted: self._operation(lambda: self.backend.set_muted(selected.id, muted)),
            allow_100=direction is AudioDirection.OUTPUT,
        )
        card.append(controls.widget)
        meter = self.Gtk.LevelBar()
        meter.set_min_value(0)
        meter.set_max_value(1)
        meter.set_value(0)
        meter.set_tooltip_text("Live level is shown when PipeWire exposes it")
        card.append(meter)
        return card

    def _streams_card(
        self,
        heading: str,
        streams: Sequence[AudioStream],
        devices: Sequence[AudioDevice],
        empty_text: str,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("card")
        label = self.Gtk.Label(label=heading, xalign=0)
        label.add_css_class("section-title")
        card.append(label)
        if not streams:
            empty = self.Gtk.Label(label=empty_text, xalign=0)
            empty.add_css_class("state-detail")
            card.append(empty)
            return card
        for stream in streams:
            row = StreamRow(
                self.Gtk,
                stream,
                devices,
                lambda stream_id, value: self._operation(
                    lambda: self.backend.set_volume(stream_id, value)
                ),
                lambda stream_id, muted: self._operation(
                    lambda: self.backend.set_muted(stream_id, muted)
                ),
                lambda stream_id, device_id: self._operation(
                    lambda: self.backend.move_stream(stream_id, device_id)
                ),
            )
            card.append(row.widget)
        return card

    def _operation(self, operation: Callable[[], None]) -> None:
        def worker() -> None:
            try:
                operation()
            except Exception as exc:  # noqa: BLE001 - action boundary
                self.GLib.idle_add(self._show_error, str(exc), False)
            finally:
                self.GLib.idle_add(self.refresh)

        threading.Thread(target=worker, name="sound-operation", daemon=True).start()

    def _show_error(self, message: str, disconnected: bool) -> bool:
        if self._destroyed:
            return False
        self.error.show(message, disconnected=disconnected)
        if disconnected and not self.snapshot.outputs and not self.snapshot.inputs:
            self._clear_content()
            self._render_state("Audio service disconnected", "Nix Settings will retry automatically.")
        return False

    def _monitor_changed(self) -> None:
        self.GLib.idle_add(self.refresh)

    def _monitor_disconnected(self, message: str) -> None:
        self.GLib.idle_add(self._show_error, message, True)

    def _render_loading(self) -> None:
        self._clear_content()
        spinner = self.Gtk.Spinner()
        spinner.start()
        box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=10)
        box.set_halign(self.Gtk.Align.CENTER)
        box.set_valign(self.Gtk.Align.CENTER)
        box.set_vexpand(True)
        box.append(spinner)
        box.append(self.Gtk.Label(label="Loading audio devices…"))
        self.content.append(box)

    def _render_state(self, title: str, detail: str) -> None:
        box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        box.set_halign(self.Gtk.Align.CENTER)
        box.set_valign(self.Gtk.Align.CENTER)
        box.set_vexpand(True)
        heading = self.Gtk.Label(label=title)
        heading.add_css_class("state-title")
        message = self.Gtk.Label(label=detail)
        message.add_css_class("state-detail")
        box.append(heading)
        box.append(message)
        self.content.append(box)

    def _clear_content(self) -> None:
        child = self.content.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.content.remove(child)
            child = next_child

    def stop(self) -> None:
        self._destroyed = True
        self.monitor.stop()
