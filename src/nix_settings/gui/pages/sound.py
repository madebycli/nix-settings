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
        self._refresh_again = False
        self._destroyed = False
        self._debounce_id: int | None = None
        self._interaction_count = 0
        self._pending_snapshot: AudioSnapshot | None = None
        self.monitor = PipeWireMonitor(self._monitor_changed, self._monitor_disconnected)

        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.widget.get_style_context().add_class("content")

        self.error = ErrorBanner(Gtk)
        self.widget.pack_start(self.error.widget, False, False, 0)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroller.set_overlay_scrolling(False)
        self.scroller.set_vexpand(True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.content.set_margin_right(8)
        self.content.set_margin_bottom(16)
        self.scroller.add_with_viewport(self.content)
        self.widget.pack_start(self.scroller, True, True, 0)
        self._render_loading()

    def start(self) -> None:
        self.refresh()
        self.monitor.start()

    def refresh(self) -> None:
        if self._destroyed:
            return
        if not self._refresh_lock.acquire(blocking=False):
            self._refresh_again = True
            return
        threading.Thread(target=self._load_snapshot, name="sound-refresh", daemon=True).start()

    def _load_snapshot(self) -> None:
        try:
            try:
                snapshot = self.backend.snapshot()
            except Exception as exc:  # noqa: BLE001 - backend boundary
                self.GLib.idle_add(self._show_error, str(exc), True)
            else:
                self.GLib.idle_add(self._apply_snapshot, snapshot)
        finally:
            self._refresh_lock.release()
        if self._refresh_again and not self._destroyed:
            self._refresh_again = False
            self.GLib.idle_add(self.refresh)

    def _apply_snapshot(self, snapshot: AudioSnapshot) -> bool:
        if self._destroyed:
            return False
        if self._interaction_count > 0:
            self._pending_snapshot = snapshot
            return False

        adjustment = self.scroller.get_vadjustment()
        previous_scroll = adjustment.get_value() if adjustment is not None else 0.0
        self.snapshot = snapshot
        self.error.hide()
        self._clear_content()
        if not snapshot.outputs and not snapshot.inputs:
            self._render_state("No audio devices", "PipeWire returned an empty device graph.")
        else:
            outputs = self._unique_devices(snapshot.outputs)
            inputs = self._unique_devices(snapshot.inputs)
            devices = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
            devices.set_homogeneous(True)
            devices.pack_start(
                self._device_card("OUTPUT", outputs, snapshot.default_output_id),
                True,
                True,
                0,
            )
            devices.pack_start(
                self._device_card("INPUT", inputs, snapshot.default_input_id),
                True,
                True,
                0,
            )
            self.content.pack_start(devices, False, False, 0)
            self.content.pack_start(
                self._streams_card(
                    "PLAYBACK",
                    snapshot.playback_streams,
                    outputs,
                    "No applications are playing audio.",
                ),
                False,
                False,
                0,
            )
            self.content.pack_start(
                self._streams_card(
                    "RECORDING",
                    snapshot.recording_streams,
                    inputs,
                    "No applications are recording audio.",
                ),
                False,
                False,
                0,
            )
        self.content.show_all()
        self.error.hide()
        self.GLib.idle_add(self._restore_scroll, previous_scroll)
        return False

    @staticmethod
    def _unique_devices(devices: Sequence[AudioDevice]) -> tuple[AudioDevice, ...]:
        unique: dict[tuple[str, str], AudioDevice] = {}
        for device in devices:
            key = (device.description.casefold(), (device.active_port or "").casefold())
            current = unique.get(key)
            if current is None or (device.is_default and not current.is_default):
                unique[key] = device
        return tuple(unique.values())

    def _restore_scroll(self, value: float) -> bool:
        adjustment = self.scroller.get_vadjustment()
        if adjustment is not None:
            upper = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
            adjustment.set_value(min(value, upper))
        return False

    def _device_card(
        self,
        heading: str,
        devices: Sequence[AudioDevice],
        selected_id: int | None,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=9)
        card.get_style_context().add_class("card")
        label = self.Gtk.Label(label=heading, xalign=0)
        label.get_style_context().add_class("section-title")
        card.pack_start(label, False, False, 0)
        if not devices:
            empty = self.Gtk.Label(label="No device available", xalign=0)
            empty.get_style_context().add_class("state-detail")
            card.pack_start(empty, False, False, 0)
            return card

        selected = next((device for device in devices if device.id == selected_id), devices[0])
        selector = DeviceSelector(
            self.Gtk,
            devices,
            selected.id,
            lambda device_id: self._operation(lambda: self.backend.set_default(device_id)),
            self._scroll_from_selector,
        )
        card.pack_start(selector.widget, False, False, 0)

        detail_parts: list[str] = []
        if selected.active_port:
            detail_parts.append(selected.active_port)
        if selected.active_profile:
            detail_parts.append(selected.active_profile)
        if detail_parts:
            detail_text = "  •  ".join(detail_parts)
            detail = self.Gtk.Label(label=detail_text, xalign=0)
            detail.get_style_context().add_class("device-detail")
            detail.set_ellipsize(3)
            detail.set_tooltip_text(detail_text)
            card.pack_start(detail, False, False, 0)

        controls = VolumeControl(
            self.Gtk,
            self.GLib,
            selected.volume,
            selected.is_muted,
            lambda value: self._operation(lambda: self.backend.set_volume(selected.id, value)),
            lambda muted: self._operation(lambda: self.backend.set_muted(selected.id, muted)),
            self._interaction_changed,
        )
        card.pack_start(controls.widget, False, False, 0)
        return card

    def _streams_card(
        self,
        heading: str,
        streams: Sequence[AudioStream],
        devices: Sequence[AudioDevice],
        empty_text: str,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        card.get_style_context().add_class("card")
        label = self.Gtk.Label(label=heading, xalign=0)
        label.get_style_context().add_class("section-title")
        card.pack_start(label, False, False, 0)
        if not streams:
            empty = self.Gtk.Label(label=empty_text, xalign=0)
            empty.get_style_context().add_class("state-detail")
            card.pack_start(empty, False, False, 0)
            return card
        for stream in streams:
            row = StreamRow(
                self.Gtk,
                self.GLib,
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
                self._interaction_changed,
                self._scroll_from_selector,
            )
            card.pack_start(row.widget, False, False, 0)
        return card

    def _interaction_changed(self, active: bool) -> None:
        if active:
            self._interaction_count += 1
            return
        self._interaction_count = max(0, self._interaction_count - 1)
        if self._interaction_count == 0 and self._pending_snapshot is not None:
            pending = self._pending_snapshot
            self._pending_snapshot = None
            self.GLib.timeout_add(120, self._apply_deferred_snapshot, pending)

    def _apply_deferred_snapshot(self, snapshot: AudioSnapshot) -> bool:
        if self._interaction_count == 0:
            return self._apply_snapshot(snapshot)
        self._pending_snapshot = snapshot
        return False

    def _scroll_from_selector(self, event: Any) -> None:
        adjustment = self.scroller.get_vadjustment()
        if adjustment is None:
            return
        direction = int(getattr(event, "direction", 4))
        delta = 0.0
        if direction == 0:
            delta = -1.0
        elif direction == 1:
            delta = 1.0
        else:
            try:
                success, _delta_x, delta_y = event.get_scroll_deltas()
                delta = float(delta_y) if success else 0.0
            except (AttributeError, TypeError, ValueError):
                delta = 0.0
        step = max(48.0, adjustment.get_step_increment() * 3.0)
        upper = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
        adjustment.set_value(max(0.0, min(upper, adjustment.get_value() + delta * step)))

    def _operation(self, operation: Callable[[], None]) -> None:
        def worker() -> None:
            try:
                operation()
            except Exception as exc:  # noqa: BLE001 - action boundary
                self.GLib.idle_add(self._show_error, str(exc), False)
            else:
                self.GLib.idle_add(self._queue_monitor_refresh)

        threading.Thread(target=worker, name="sound-operation", daemon=True).start()

    def _show_error(self, message: str, disconnected: bool) -> bool:
        if self._destroyed:
            return False
        self.error.show(message, disconnected=disconnected)
        if disconnected and not self.snapshot.outputs and not self.snapshot.inputs:
            self._clear_content()
            self._render_state(
                "Audio service disconnected",
                "Nix Settings will retry automatically.",
            )
            self.content.show_all()
            self.error.show(message, disconnected=True)
        return False

    def _monitor_changed(self) -> None:
        self.GLib.idle_add(self._queue_monitor_refresh)

    def _queue_monitor_refresh(self) -> bool:
        if self._destroyed:
            return False
        if self._interaction_count > 0:
            self._refresh_again = True
            return False
        if self._debounce_id is not None:
            self.GLib.source_remove(self._debounce_id)
        self._debounce_id = self.GLib.timeout_add(450, self._run_monitor_refresh)
        return False

    def _run_monitor_refresh(self) -> bool:
        self._debounce_id = None
        self.refresh()
        return False

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
        box.pack_start(spinner, False, False, 0)
        box.pack_start(self.Gtk.Label(label="Loading audio devices…"), False, False, 0)
        self.content.pack_start(box, True, True, 0)

    def _render_state(self, title: str, detail: str) -> None:
        box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        box.set_halign(self.Gtk.Align.CENTER)
        box.set_valign(self.Gtk.Align.CENTER)
        box.set_vexpand(True)
        heading = self.Gtk.Label(label=title)
        heading.get_style_context().add_class("state-title")
        message = self.Gtk.Label(label=detail)
        message.get_style_context().add_class("state-detail")
        box.pack_start(heading, False, False, 0)
        box.pack_start(message, False, False, 0)
        self.content.pack_start(box, True, True, 0)

    def _clear_content(self) -> None:
        for child in list(self.content.get_children()):
            self.content.remove(child)

    def stop(self) -> None:
        self._destroyed = True
        if self._debounce_id is not None:
            self.GLib.source_remove(self._debounce_id)
            self._debounce_id = None
        self.monitor.stop()
