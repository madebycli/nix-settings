from __future__ import annotations

import threading
from typing import Any

from nix_settings.backend.models import UPDATE_MODES, SystemStatus, UpdatePreview
from nix_settings.backend.process import (
    BackendCommands,
    JsonRunner,
    StreamingProcess,
    config_repo,
)
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.widgets.common import action_button, card, page_scroller, styled_label
from nix_settings.gui.widgets.log_view import LogView

MODE_LABELS = {
    "all": ("All", "All Flake inputs and personal profiles"),
    "base": ("Base", "Nixpkgs, Kernel/Core and personal profiles"),
    "packages": ("Packages", "Nixpkgs and personal profiles"),
    "kernel": ("Kernel/Core", "Only nix-cachyos-kernel"),
    "desktop": ("Desktop", "Home Manager, Mango, Noctalia and Greeter"),
    "profiles": ("Profiles", "Only personal Nix profile entries"),
}
SOURCE_ORDER = (
    "nixpkgs",
    "nix-cachyos-kernel",
    "home-manager",
    "mango",
    "noctalia",
    "noctalia-greeter",
    "profiles",
)
SOURCE_LABELS = {
    "nixpkgs": "Nixpkgs",
    "nix-cachyos-kernel": "Kernel/Core",
    "home-manager": "Home Manager",
    "mango": "Mango",
    "noctalia": "Noctalia",
    "noctalia-greeter": "Noctalia Greeter",
    "profiles": "Personal Profiles",
}


class UpdatesPage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=1800.0)
        self.gate: RequestGate[UpdatePreview] = RequestGate()
        self.preview: UpdatePreview | None = None
        self.operation: StreamingProcess | None = None
        self.source_labels: dict[str, tuple[Any, Any]] = {}

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._controls(), False, False, 0)
        content.pack_start(self._sources(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _controls(self) -> Any:
        box = card(self.Gtk)
        row = self.Gtk.Grid()
        row.set_column_spacing(10)
        row.set_hexpand(True)
        title = styled_label(self.Gtk, "NIX REFRESH", "section-title")
        row.attach(title, 0, 0, 1, 1)
        self.mode = self.Gtk.ComboBoxText()
        for key, (label, _detail) in MODE_LABELS.items():
            self.mode.append(key, label)
        self.mode.set_active_id("all")
        self.mode.set_size_request(164, 32)
        self.mode.connect("changed", self._mode_changed)
        row.attach(self.mode, 1, 0, 1, 1)
        self.full = self.Gtk.CheckButton(label="Detailed closure preview")
        row.attach(self.full, 2, 0, 1, 1)
        spacer = self.Gtk.Box()
        spacer.set_hexpand(True)
        row.attach(spacer, 3, 0, 1, 1)
        self.check = action_button(self.Gtk, "Check for updates", self._check_clicked, width=156)
        self.apply = action_button(
            self.Gtk, "Update", self._apply_clicked, width=110, primary=True
        )
        self.apply.set_sensitive(False)
        row.attach(self.check, 4, 0, 1, 1)
        row.attach(self.apply, 5, 0, 1, 1)
        box.pack_start(row, False, False, 0)
        self.mode_detail = styled_label(self.Gtk, MODE_LABELS["all"][1], "card-detail")
        box.pack_start(self.mode_detail, False, False, 0)
        self.summary = styled_label(self.Gtk, "Not checked", "state-title")
        box.pack_start(self.summary, False, False, 0)
        self.progress = self.Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Idle")
        self.progress.get_style_context().add_class("deck-progress")
        box.pack_start(self.progress, False, False, 0)
        return box

    def _sources(self) -> Any:
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        for index, source_id in enumerate(SOURCE_ORDER):
            box = card(self.Gtk, spacing=5)
            box.set_size_request(-1, 88)
            box.pack_start(
                styled_label(self.Gtk, SOURCE_LABELS[source_id], "card-title"),
                False,
                False,
                0,
            )
            status = styled_label(self.Gtk, "Not checked", "status-text")
            detail = styled_label(self.Gtk, "—", "card-detail")
            box.pack_start(status, False, False, 0)
            box.pack_start(detail, False, False, 0)
            self.source_labels[source_id] = (status, detail)
            grid.attach(box, index % 4, index // 4, 1, 1)
        return grid

    def _mode_changed(self, _combo: Any) -> None:
        mode = self.mode.get_active_id() or "all"
        self.mode_detail.set_text(MODE_LABELS[mode][1])
        selected = set(UPDATE_MODES[mode])
        for source_id, (status, detail) in self.source_labels.items():
            if source_id in selected:
                status.set_text("Not checked")
                detail.set_text("—")
            else:
                status.set_text("Not included")
                detail.set_text("This mode does not check this source")
        self.preview = None
        self.apply.set_sensitive(False)

    def _set_busy(self, busy: bool, text: str) -> None:
        self.mode.set_sensitive(not busy)
        self.full.set_sensitive(not busy)
        self.check.set_sensitive(not busy)
        self.apply.set_sensitive(not busy and self.preview is not None)
        if busy:
            self.progress.pulse()
        self.progress.set_text(text)

    def _check_clicked(self, _button: Any) -> None:
        mode = self.mode.get_active_id() or "all"
        self._set_busy(True, "Checking…")
        self.summary.set_text("Checking selected sources")
        for source_id in UPDATE_MODES[mode]:
            labels = self.source_labels.get(source_id)
            if labels is not None:
                labels[0].set_text("Checking…")
        generation = self.gate.begin()
        full = self.full.get_active()
        self.gate.run(
            generation,
            lambda: UpdatePreview.from_json(
                self.runner.run(BackendCommands.updates(mode, full=full)).json()
            ),
            self._preview_finished,
        )

    def _preview_finished(
        self,
        value: UpdatePreview | None,
        error: Exception | None,
    ) -> None:
        self.GLib.idle_add(self._apply_preview, value, error)

    def _apply_preview(self, value: UpdatePreview | None, error: Exception | None) -> bool:
        self._set_busy(False, "Idle")
        if error is not None or value is None:
            self.preview = None
            self.summary.set_text("Update check failed")
            self.log.append(str(error or "Unknown update check error"), error=True)
            self.apply.set_sensitive(False)
            return False
        self.preview = value
        by_id = {source.id: source for source in value.sources}
        for source_id, (status, detail) in self.source_labels.items():
            source = by_id.get(source_id)
            if source is None:
                if source_id == "profiles" and value.mode in {
                    "all",
                    "base",
                    "packages",
                    "profiles",
                }:
                    status.set_text(
                        "Update available" if value.profile_update_available else "Current"
                    )
                    detail.set_text(
                        f"{value.profile_package_count} entries · {value.profile_summary}"
                    )
                continue
            status.set_text("Update available" if source.update_available else "Current")
            current = source.current_date or source.current_revision[:12]
            candidate = source.candidate_date or source.candidate_revision[:12]
            detail.set_text(f"{current} → {candidate}" if source.update_available else current)
        self.summary.set_text(f"{value.update_count} source(s) can be updated")
        self.apply.set_sensitive(True)
        for item in value.errors:
            self.log.append(item, error=True)
        if value.full_closure_preview:
            self.log.append(value.full_closure_preview)
        return False

    def _apply_clicked(self, _button: Any) -> None:
        mode = self.mode.get_active_id() or "all"
        affected = ", ".join(SOURCE_LABELS[item] for item in UPDATE_MODES[mode])
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.QUESTION,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text=f"Run Nix Refresh: {MODE_LABELS[mode][0]}?",
        )
        dialog.format_secondary_text(
            f"Affected sources: {affected}. The desktop Polkit agent will handle authentication."
        )
        dialog.add_button("Update", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response != self.Gtk.ResponseType.OK:
            return
        self._set_busy(True, "Preparing privileged operation…")
        threading.Thread(
            target=self._prepare_operation,
            args=(mode,),
            name="prepare-refresh",
            daemon=True,
        ).start()

    def _prepare_operation(self, mode: str) -> None:
        try:
            repo = config_repo()
            if repo is None:
                raise RuntimeError("Nix configuration repository was not found")
            status = SystemStatus.from_json(
                self.runner.run(BackendCommands.status(online=False), timeout=45.0).json()
            )
            command = BackendCommands.privileged(
                "refresh", mode, str(repo), status.profile
            )
        except Exception as exc:
            self.GLib.idle_add(self._operation_prepare_failed, str(exc))
            return
        self.operation = StreamingProcess(command, self._operation_event, self._operation_done)
        self.operation.start()

    def _operation_prepare_failed(self, message: str) -> bool:
        self.log.append(message, error=True)
        self._set_busy(False, "Failed")
        return False

    def _operation_event(self, payload: dict[str, Any]) -> None:
        self.GLib.idle_add(self._apply_operation_event, payload)

    def _apply_operation_event(self, payload: dict[str, Any]) -> bool:
        kind = str(payload.get("event", "log"))
        phase = str(payload.get("phase", "operation"))
        if kind == "log":
            self.log.append(
                str(payload.get("message", "")),
                error=str(payload.get("stream", "")) == "stderr",
            )
        elif kind == "phase-started":
            self.progress.pulse()
            self.progress.set_text(phase.replace("-", " "))
        elif kind == "phase-completed":
            self.log.append(f"Completed: {phase}")
        elif kind == "operation-failed":
            self.log.append(str(payload.get("error", "Operation failed")), error=True)
        elif kind == "operation-completed":
            self.log.append("Nix Refresh completed")
        return False

    def _operation_done(self, code: int, error: str | None) -> None:
        self.GLib.idle_add(self._finish_operation, code, error)

    def _finish_operation(self, code: int, error: str | None) -> bool:
        self.operation = None
        self._set_busy(False, "Complete" if code == 0 else "Failed")
        if error:
            self.log.append(error, error=True)
        if code == 0:
            self._check_clicked(None)
        return False
