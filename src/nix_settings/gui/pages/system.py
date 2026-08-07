from __future__ import annotations

import threading
from typing import Any

from nix_settings.backend.models import SystemStatus
from nix_settings.backend.process import BackendCommands, JsonRunner, StreamingProcess, config_repo
from nix_settings.gui.widgets.common import (
    action_button,
    card,
    page_scroller,
    stat_row,
    styled_label,
)
from nix_settings.gui.widgets.log_view import LogView


class SystemPage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=90.0)
        self.operation: StreamingProcess | None = None
        self.values: dict[str, Any] = {}
        self._started = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._health_card(), False, False, 0)
        content.pack_start(self._actions_card(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _health_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "SYSTEM HEALTH", "section-title"), False, False, 0)
        for key, title in (
            ("host", "Host"),
            ("profile", "Profile"),
            ("generation", "Generation"),
            ("repo", "Repository"),
            ("state", "State"),
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            box.pack_start(row, False, False, 0)
        return box

    def _actions_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "ACTIONS", "section-title"), False, False, 0)
        row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        row.pack_start(action_button(self.Gtk, "Run doctor", self._doctor, width=120), False, False, 0)
        row.pack_start(action_button(self.Gtk, "Refresh", self._refresh_clicked, width=100), False, False, 0)
        row.pack_start(
            action_button(
                self.Gtk, "Build & switch", self._switch_clicked, width=138, primary=True
            ),
            False,
            False,
            0,
        )
        box.pack_start(row, False, False, 0)
        box.pack_start(
            styled_label(
                self.Gtk,
                "Authentication is delegated to the desktop Polkit agent; no password is read by Nix Settings.",
                "card-detail",
            ),
            False,
            False,
            0,
        )
        return box

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.refresh()

    def _refresh_clicked(self, _button: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        threading.Thread(target=self._load_status, name="system-status", daemon=True).start()

    def _load_status(self) -> None:
        try:
            value = SystemStatus.from_json(
                self.runner.run(BackendCommands.status(online=False)).json()
            )
            error: Exception | None = None
        except Exception as exc:
            value = None
            error = exc
        self.GLib.idle_add(self._apply_status, value, error)

    def _apply_status(self, value: SystemStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.values["state"].set_text("Failed")
            self.log.append(str(error or "Unknown status error"), error=True)
            return False
        self.values["host"].set_text(value.host)
        self.values["profile"].set_text(value.profile)
        self.values["generation"].set_text(str(value.current_generation or "—"))
        self.values["repo"].set_text(value.repository_path)
        self.values["state"].set_text("Ready" if not value.errors else "Warnings")
        return False

    def _doctor(self, _button: Any) -> None:
        self.operation = StreamingProcess(["nix-settings", "doctor"], self._event, self._done)
        self.operation.start()

    def _switch_clicked(self, _button: Any) -> None:
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.QUESTION,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text="Build and switch the active NixOS profile?",
        )
        dialog.format_secondary_text(
            "The restricted helper validates the repository and profile before running nixos-rebuild."
        )
        dialog.add_button("Build & switch", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response != self.Gtk.ResponseType.OK:
            return
        threading.Thread(target=self._prepare_switch, name="prepare-switch", daemon=True).start()

    def _prepare_switch(self) -> None:
        try:
            repo = config_repo()
            if repo is None:
                raise RuntimeError("Nix configuration repository was not found")
            status = SystemStatus.from_json(
                self.runner.run(BackendCommands.status(online=False)).json()
            )
            argv = BackendCommands.privileged("switch", str(repo), status.profile)
        except Exception as exc:
            self.GLib.idle_add(self._append_operation_log, str(exc), True)
            return
        self.operation = StreamingProcess(argv, self._event, self._done)
        self.operation.start()

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
        if error:
            self.log.append(error, error=True)
        if code == 0:
            self.refresh()
        return False
