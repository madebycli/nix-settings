from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from typing import Any

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.models import AudioDevice, AudioSnapshot, AudioStream
from nix_settings.audio.monitor import PipeWireMonitor
from nix_settings.gui.widgets.device_selector import DeviceSelector
from nix_settings.gui.widgets.error_banner import ErrorBanner
from nix_settings.gui.widgets.stream_row import StreamRow
from nix_settings.gui.widgets.volume_control import VolumeControl


class SoundPage:
    def __init__(
        self,
        Gtk: Any,
        GLib: Any,
        backend: AudioBackend,
        initial_snapshot: AudioSnapshot,
        initial_error: str | None = None,
    ) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.backend = backend
        self.snapshot = initial_snapshot
        self._refresh_lock = threading.Lock()
        self._refresh_again = False
        self._destroyed = False
        self._debounce_id: int | None = None
        self._interaction_count = 0
        self._pending_snapshot: AudioSnapshot | None = None
        self._structure: tuple[object, ...] | None = None
        self._volume_controls: dict[int, VolumeControl] = {}
        self.monitor = PipeWireMonitor(self._monitor_changed, self._monitor_disconnected)

        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.widget.get_style_context().add_class("content")

        self.error = ErrorBanner(Gtk)
        self.widget.pack_start(self.error.widget, False, False, 0)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_column_spacing(10)
        self.grid.set_row_spacing(10)
        self.grid.set_hexpand(True)
        self.grid.set_vexpand(True)
        self.widget.pack_start(self.grid, True, True, 0)

        self.has_error = bool(initial_error)
        if initial_error:
            self.error.show(initial_error, disconnected=True)
        self._render_snapshot(initial_snapshot)

    def start(self) -> None:
        self.monitor.start()

    def refresh(self) -> None:
        if self._destroyed:
            return
        if self._interaction_count > 0:
            self._refresh_again = True
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
            self._refresh_again = True
            return False

        self.snapshot = snapshot
        self.has_error = False
        self.error.hide()
        structure = self._snapshot_structure(snapshot)
        if structure == self._structure:
            self._sync_control_state(snapshot)
            return False

        self._render_snapshot(snapshot)
        return False

    def _render_snapshot(self, snapshot: AudioSnapshot) -> None:
        self._clear_grid()
        self._volume_controls.clear()
        self._structure = self._snapshot_structure(snapshot)

        outputs = self._unique_devices(snapshot.outputs)
        inputs = self._unique_devices(snapshot.inputs)

        output_card = self._device_card("OUTPUT", outputs, snapshot.default_output_id)
        input_card = self._device_card("INPUT", inputs, snapshot.default_input_id)
        playback_card = self._streams_card(
            "PLAYBACK",
            snapshot.playback_streams,
            outputs,
            "No applications are playing audio.",
        )
        recording_card = self._streams_card(
            "RECORDING",
            snapshot.recording_streams,
            inputs,
            "No applications are recording audio.",
        )

        self.grid.attach(output_card, 0, 0, 1, 1)
        self.grid.attach(input_card, 1, 0, 1, 1)
        self.grid.attach(playback_card, 0, 1, 1, 1)
        self.grid.attach(recording_card, 1, 1, 1, 1)
        playback_card.set_vexpand(True)
        recording_card.set_vexpand(True)
        self.grid.show_all()
        if not self.has_error:
            self.error.hide()

    @staticmethod
    def _unique_devices(devices: Sequence[AudioDevice]) -> tuple[AudioDevice, ...]:
        unique: dict[tuple[str, str], AudioDevice] = {}
        for device in devices:
            key = (device.description.casefold(), (device.active_port or "").casefold())
            current = unique.get(key)
            if current is None or (device.is_default and not current.is_default):
                unique[key] = device
        return tuple(unique.values())

    def _snapshot_structure(self, snapshot: AudioSnapshot) -> tuple[object, ...]:
        def device_key(device: AudioDevice) -> tuple[object, ...]:
            return (
                device.id,
                device.description,
                device.active_port,
                device.active_profile,
            )

        def stream_key(stream: AudioStream) -> tuple[object, ...]:
            return (
                stream.id,
                stream.application_name,
                stream.application_icon,
                stream.media_name,
                stream.device_id,
            )

        return (
            tuple(device_key(item) for item in self._unique_devices(snapshot.outputs)),
            tuple(device_key(item) for item in self._unique_devices(snapshot.inputs)),
            snapshot.default_output_id,
            snapshot.default_input_id,
            tuple(stream_key(item) for item in snapshot.playback_streams),
            tuple(stream_key(item) for item in snapshot.recording_streams),
        )

    def _sync_control_state(self, snapshot: AudioSnapshot) -> None:
        nodes: list[AudioDevice | AudioStream] = [
            *snapshot.outputs,
            *snapshot.inputs,
            *snapshot.playback_streams,
            *snapshot.recording_streams,
        ]
        for node in nodes:
            control = self._volume_controls.get(node.id)
            if control is not None:
                control.set_state(node.volume, node.is_muted)

    def _device_card(
        self,
        heading: str,
        devices: Sequence[AudioDevice],
        selected_id: int | None,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        card.get_style_context().add_class("card")
        card.get_style_context().add_class("device-card")
        card.set_hexpand(True)

        label = self.Gtk.Label(label=heading, xalign=0)
        label.get_style_context().add_class("section-title")
        card.pack_start(label, False, False, 0)

        if not devices:
            empty = self.Gtk.Label(label="No device available", xalign=0)
            empty.get_style_context().add_class("state-detail")
            card.pack_start(empty, False, False, 0)
            return card

        selected = next((device for device in devices if device.id == selected_id), devices[0])
        body = self.Gtk.Grid()
        body.set_column_spacing(14)
        body.set_row_spacing(3)
        body.set_hexpand(True)
        body.set_valign(self.Gtk.Align.CENTER)

        selector = DeviceSelector(
            self.Gtk,
            devices,
            selected.id,
            lambda device_id: self._operation(lambda: self.backend.set_default(device_id)),
            width=420,
        )
        selector.widget.set_halign(self.Gtk.Align.START)
        selector.widget.set_valign(self.Gtk.Align.CENTER)

        controls = VolumeControl(
            self.Gtk,
            self.GLib,
            selected.volume,
            selected.is_muted,
            lambda value: self._operation(lambda: self.backend.set_volume(selected.id, value)),
            lambda muted: self._operation(lambda: self.backend.set_muted(selected.id, muted)),
            self._interaction_changed,
        )
        controls.widget.set_hexpand(True)
        controls.widget.set_valign(self.Gtk.Align.CENTER)
        self._volume_controls[selected.id] = controls

        body.attach(selector.widget, 0, 0, 1, 1)
        body.attach(controls.widget, 1, 0, 1, 1)

        detail_parts: list[str] = []
        if selected.active_port:
            detail_parts.append(selected.active_port)
        if selected.active_profile:
            detail_parts.append(selected.active_profile)
        if detail_parts:
            detail_text = "  •  ".join(detail_parts)
            detail = self.Gtk.Label(label=detail_text, xalign=0)
            detail.set_single_line_mode(True)
            detail.set_ellipsize(3)
            detail.set_tooltip_text(detail_text)
            detail.get_style_context().add_class("device-detail")
            body.attach(detail, 0, 1, 1, 1)

        card.pack_start(body, False, False, 0)
        return card

    def _streams_card(
        self,
        heading: str,
        streams: Sequence[AudioStream],
        devices: Sequence[AudioDevice],
        empty_text: str,
    ) -> Any:
        card = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("card")
        card.get_style_context().add_class("streams-card")
        card.set_hexpand(True)
        card.set_vexpand(True)

        label = self.Gtk.Label(label=heading, xalign=0)
        label.get_style_context().add_class("section-title")
        card.pack_start(label, False, False, 0)

        scroller = self.Gtk.ScrolledWindow()
        scroller.set_policy(self.Gtk.PolicyType.NEVER, self.Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(self.Gtk.ShadowType.NONE)
        scroller.set_overlay_scrolling(False)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        rows = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=9)
        rows.set_margin_right(8)
        rows.set_margin_bottom(4)

        if not streams:
            empty = self.Gtk.Label(label=empty_text, xalign=0)
            empty.get_style_context().add_class("state-detail")
            empty.set_margin_top(16)
            rows.pack_start(empty, False, False, 0)
        else:
            on_scroll = lambda event: self._scroll_scroller(scroller, event)
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
                    on_scroll,
                )
                control = row.volume_control
                if control is not None:
                    self._volume_controls[stream.id] = control
                rows.pack_start(row.widget, False, False, 0)

        scroller.add_with_viewport(rows)
        card.pack_start(scroller, True, True, 0)
        return card

    def _interaction_changed(self, active: bool) -> None:
        if active:
            self._interaction_count += 1
            return
        self._interaction_count = max(0, self._interaction_count - 1)
        if self._interaction_count == 0:
            self._pending_snapshot = None
            self._refresh_again = False
            self.GLib.timeout_add(40, self._refresh_after_interaction)

    def _refresh_after_interaction(self) -> bool:
        if not self._destroyed and self._interaction_count == 0:
            self.refresh()
        return False

    @staticmethod
    def _scroll_scroller(scroller: Any, event: Any) -> None:
        adjustment = scroller.get_vadjustment()
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
        step = max(52.0, adjustment.get_step_increment() * 3.0)
        upper = max(0.0, adjustment.get_upper() - adjustment.get_page_size())
        adjustment.set_value(
            max(0.0, min(upper, adjustment.get_value() + delta * step))
        )

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
        self.has_error = True
        self.error.show(message, disconnected=disconnected)
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
        self._debounce_id = self.GLib.timeout_add(350, self._run_monitor_refresh)
        return False

    def _run_monitor_refresh(self) -> bool:
        self._debounce_id = None
        self.refresh()
        return False

    def _monitor_disconnected(self, message: str) -> None:
        self.GLib.idle_add(self._show_error, message, True)

    def _clear_grid(self) -> None:
        for child in list(self.grid.get_children()):
            self.grid.remove(child)

    def stop(self) -> None:
        self._destroyed = True
        if self._debounce_id is not None:
            self.GLib.source_remove(self._debounce_id)
            self._debounce_id = None
        self.monitor.stop()
