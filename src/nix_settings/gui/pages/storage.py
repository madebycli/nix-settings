from __future__ import annotations

from typing import Any

from nix_settings.backend.models import CleanPreview, SystemStatus, format_bytes
from nix_settings.backend.process import BackendCommands, JsonRunner, StreamingProcess
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.widgets.common import action_button, card, page_scroller, stat_row, styled_label
from nix_settings.gui.widgets.log_view import LogView


class StoragePage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=120.0)
        self.status_gate: RequestGate[SystemStatus] = RequestGate()
        self.clean_gate: RequestGate[CleanPreview] = RequestGate()
        self.operation: StreamingProcess | None = None
        self.values: dict[str, Any] = {}
        self._started = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._usage_card(), False, False, 0)
        content.pack_start(self._actions_card(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _usage_card(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(styled_label(self.Gtk, "STORAGE", "section-title"), True, True, 0)
        header.pack_start(
            action_button(self.Gtk, "Refresh", lambda *_: self.refresh(), width=96),
            False,
            False,
            0,
        )
        box.pack_start(header, False, False, 0)
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(16)
        left = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        right = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        for index, (key, title) in enumerate(
            (
                ("store", "Nix Store size"),
                ("closure", "Current closure"),
                ("disk_used", "Disk used"),
                ("disk_free", "Disk free"),
                ("disk_total", "Disk total"),
                ("generations", "Generations"),
                ("reclaimable", "Potentially reclaimable"),
                ("status", "Status"),
            )
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            (left if index < 4 else right).pack_start(row, False, False, 0)
        grid.attach(left, 0, 0, 1, 1)
        grid.attach(right, 1, 0, 1, 1)
        box.pack_start(grid, False, False, 0)
        self.disk = self.Gtk.ProgressBar()
        self.disk.set_show_text(True)
        self.disk.get_style_context().add_class("deck-progress")
        box.pack_start(self.disk, False, False, 0)
        return box

    def _actions_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "MAINTENANCE", "section-title"), False, False, 0)
        row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        row.pack_start(styled_label(self.Gtk, "Keep rollback generations", "card-detail"), False, False, 0)
        adjustment = self.Gtk.Adjustment(value=5, lower=1, upper=20, step_increment=1, page_increment=1)
        self.backups = self.Gtk.SpinButton(adjustment=adjustment, climb_rate=1, digits=0)
        self.backups.set_size_request(72, 32)
        row.pack_start(self.backups, False, False, 0)
        spacer = self.Gtk.Box()
        spacer.set_hexpand(True)
        row.pack_start(spacer, True, True, 0)
        self.preview_button = action_button(
            self.Gtk, "Preview cleanup", self._preview_clicked, width=138
        )
        self.clean_button = action_button(
            self.Gtk, "Clean generations", self._clean_clicked, width=148, primary=True
        )
        self.optimize_button = action_button(
            self.Gtk, "Optimize store", self._optimize_clicked, width=132
        )
        row.pack_start(self.preview_button, False, False, 0)
        row.pack_start(self.clean_button, False, False, 0)
        row.pack_start(self.optimize_button, False, False, 0)
        box.pack_start(row, False, False, 0)
        note = styled_label(
            self.Gtk,
            "Cleanup always performs and verifies a dry-run first. Optimize never deletes generations.",
            "card-detail",
        )
        box.pack_start(note, False, False, 0)
        self.preview_text = styled_label(self.Gtk, "No cleanup preview", "state-title")
        box.pack_start(self.preview_text, False, False, 0)
        return box

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.refresh()

    def refresh(self) -> None:
        generation = self.status_gate.begin()
        self.values["status"].set_text("Loading…")
        self.status_gate.run(
            generation,
            lambda: SystemStatus.from_json(
                self.runner.run(BackendCommands.status(online=False)).json()
            ),
            self._status_finished,
        )

    def _status_finished(self, value: SystemStatus | None, error: Exception | None) -> None:
        self.GLib.idle_add(self._apply_status, value, error)

    def _apply_status(self, value: SystemStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.values["status"].set_text("Failed")
            self.log.append(str(error or "Unknown storage status error"), error=True)
            return False
        self.values["store"].set_text(format_bytes(value.store_bytes))
        self.values["closure"].set_text(format_bytes(value.closure_bytes))
        self.values["disk_used"].set_text(format_bytes(value.disk_used_bytes))
        self.values["disk_free"].set_text(format_bytes(value.disk_free_bytes))
        self.values["disk_total"].set_text(format_bytes(value.disk_total_bytes))
        self.values["generations"].set_text(str(value.generation_count))
        self.values["reclaimable"].set_text("Requires cleanup preview")
        self.values["status"].set_text("Ready")
        self.disk.set_fraction(max(0.0, min(1.0, value.disk_used_percent / 100.0)))
        self.disk.set_text(f"{value.disk_used_percent}% used")
        return False

    def _preview_clicked(self, _button: Any) -> None:
        self._request_preview(confirm=False)

    def _clean_clicked(self, _button: Any) -> None:
        self._request_preview(confirm=True)

    def _request_preview(self, *, confirm: bool) -> None:
        backups = self.backups.get_value_as_int()
        self.preview_text.set_text("Calculating safe cleanup preview…")
        generation = self.clean_gate.begin()
        self.clean_gate.run(
            generation,
            lambda: CleanPreview.from_json(
                self.runner.run(BackendCommands.clean_preview(backups)).json()
            ),
            lambda value, error: self._preview_finished(value, error, confirm),
        )

    def _preview_finished(
        self,
        value: CleanPreview | None,
        error: Exception | None,
        confirm: bool,
    ) -> None:
        self.GLib.idle_add(self._apply_preview, value, error, confirm)

    def _apply_preview(
        self,
        value: CleanPreview | None,
        error: Exception | None,
        confirm: bool,
    ) -> bool:
        if error is not None or value is None:
            self.preview_text.set_text("Cleanup preview failed")
            self.log.append(str(error or "Unknown cleanup preview error"), error=True)
            return False
        if not value.safe:
            self.preview_text.set_text("Cleanup preview was not declared safe")
            self.log.append(
                "Cleanup was blocked because the backend did not confirm safety", error=True
            )
            return False
        remove = ", ".join(str(item) for item in value.delete_generations) or "none"
        self.preview_text.set_text(
            f"Keep current {value.current_generation} + {value.keep_backups} backups · remove {remove}"
        )
        if confirm:
            self._confirm_clean(value)
        return False

    def _confirm_clean(self, preview: CleanPreview) -> None:
        remove = ", ".join(str(item) for item in preview.delete_generations) or "none"
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.WARNING,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text="Clean selected system generations?",
        )
        dialog.format_secondary_text(
            f"Verified dry-run: keep {preview.keep_backups} rollback generations; remove {remove}."
        )
        dialog.add_button("Clean", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response != self.Gtk.ResponseType.OK:
            return
        self._start_operation(BackendCommands.privileged("clean", str(preview.keep_backups)))

    def _optimize_clicked(self, _button: Any) -> None:
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.QUESTION,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text="Optimize the Nix Store?",
        )
        dialog.format_secondary_text(
            "This deduplicates store paths and does not delete system generations."
        )
        dialog.add_button("Optimize", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response == self.Gtk.ResponseType.OK:
            self._start_operation(BackendCommands.privileged("optimize"))

    def _start_operation(self, argv: list[str]) -> None:
        self._set_actions(False)
        self.operation = StreamingProcess(argv, self._event, self._done)
        self.operation.start()

    def _set_actions(self, enabled: bool) -> None:
        self.preview_button.set_sensitive(enabled)
        self.clean_button.set_sensitive(enabled)
        self.optimize_button.set_sensitive(enabled)
        self.backups.set_sensitive(enabled)

    def _event(self, payload: dict[str, Any]) -> None:
        self.GLib.idle_add(
            self._append_operation_log,
            str(payload.get("message", payload.get("event", ""))),
            str(payload.get("stream", "")) == "stderr",
        )

    def _append_operation_log(self, message: str, error: bool) -> bool:
        self.log.append(message, error=error)
        return False

    def _done(self, code: int, error: str | None) -> None:
        self.GLib.idle_add(self._finish, code, error)

    def _finish(self, code: int, error: str | None) -> bool:
        self.operation = None
        self._set_actions(True)
        if error:
            self.log.append(error, error=True)
        if code == 0:
            self.refresh()
        return False
