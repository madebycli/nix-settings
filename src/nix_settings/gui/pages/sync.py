from __future__ import annotations

import difflib
from typing import Any

from nix_settings.backend.models import SyncStatus
from nix_settings.backend.paths import (
    PathValidationError,
    atomic_write,
    normalized_lines,
    validate_excludes,
    validate_managed_paths,
)
from nix_settings.backend.process import BackendCommands, JsonRunner, StreamingProcess, config_repo
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.widgets.common import (
    action_button,
    card,
    page_scroller,
    stat_row,
    styled_label,
)
from nix_settings.gui.widgets.log_view import LogView


class SyncPage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=180.0)
        self.gate: RequestGate[SyncStatus] = RequestGate()
        self.operation: StreamingProcess | None = None
        self.values: dict[str, Any] = {}
        self._started = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._status_card(), False, False, 0)
        content.pack_start(self._actions_card(), False, False, 0)
        content.pack_start(self._paths_editor(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _status_card(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        header.pack_start(styled_label(self.Gtk, "CONFIG SYNC", "section-title"), True, True, 0)
        self.scope = self.Gtk.ComboBoxText()
        for key, label in (("all", "All"), ("nixos", "NixOS"), ("dotfiles", "Dotfiles")):
            self.scope.append(key, label)
        self.scope.set_active_id("all")
        self.scope.set_size_request(130, 32)
        self.scope.connect("changed", lambda *_: self.refresh())
        header.pack_start(self.scope, False, False, 0)
        refresh = action_button(self.Gtk, "Refresh", lambda *_: self.refresh(), width=96)
        header.pack_start(refresh, False, False, 0)
        box.pack_start(header, False, False, 0)
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(16)
        left = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        right = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        for index, (key, title) in enumerate(
            (
                ("repo", "Repository"),
                ("profile", "Profile"),
                ("branch", "Branch"),
                ("relation", "Ahead / Behind"),
                ("dirty", "Worktree"),
                ("last_sync", "Last sync"),
                ("local", "Local changes"),
                ("remote", "Remote changes"),
                ("same", "Identical changes"),
                ("conflicts", "Conflicts"),
                ("plan", "Planned action"),
                ("backups", "Backups"),
            )
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            (left if index < 6 else right).pack_start(row, False, False, 0)
        grid.attach(left, 0, 0, 1, 1)
        grid.attach(right, 1, 0, 1, 1)
        box.pack_start(grid, False, False, 0)
        return box

    def _actions_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "ACTIONS", "section-title"), False, False, 0)
        row = self.Gtk.Grid()
        row.set_column_homogeneous(True)
        row.set_column_spacing(8)
        actions = (
            ("status", "Status"),
            ("push", "Upload"),
            ("pull", "Download"),
            ("sync", "Synchronize"),
            ("init", "Initialize"),
            ("history", "History"),
            ("doctor", "Doctor"),
        )
        self.action_buttons: list[Any] = []
        for index, (command, label) in enumerate(actions):
            button = action_button(
                self.Gtk,
                label,
                lambda _button, value=command: self._action_clicked(value),
                width=126,
                primary=command == "sync",
            )
            self.action_buttons.append(button)
            row.attach(button, index, 0, 1, 1)
        box.pack_start(row, False, False, 0)
        note = styled_label(
            self.Gtk,
            "Conflicts are never resolved by date. Download and synchronize use fast-forward safety.",
            "card-detail",
        )
        box.pack_start(note, False, False, 0)
        return box

    def _paths_editor(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(styled_label(self.Gtk, "MANAGED PATHS", "section-title"), True, True, 0)
        reload_button = action_button(self.Gtk, "Reload", lambda *_: self._load_paths(), width=88)
        save_button = action_button(
            self.Gtk, "Review & save", lambda *_: self._save_paths(), width=132, primary=True
        )
        header.pack_start(reload_button, False, False, 0)
        header.pack_start(save_button, False, False, 0)
        box.pack_start(header, False, False, 0)
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(10)
        self.paths_view = self._editor_column(grid, 0, "PATHS", "One path relative to HOME per line")
        self.excludes_view = self._editor_column(
            grid, 1, "EXCLUDES", "Glob patterns relative to HOME"
        )
        box.pack_start(grid, False, False, 0)
        self.path_status = styled_label(self.Gtk, "Not loaded", "card-detail")
        box.pack_start(self.path_status, False, False, 0)
        return box

    def _editor_column(self, grid: Any, column: int, title: str, hint: str) -> Any:
        holder = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=6)
        holder.pack_start(styled_label(self.Gtk, title, "section-title"), False, False, 0)
        holder.pack_start(styled_label(self.Gtk, hint, "card-detail"), False, False, 0)
        view = self.Gtk.TextView()
        view.set_wrap_mode(self.Gtk.WrapMode.NONE)
        view.get_style_context().add_class("config-editor")
        scroll = self.Gtk.ScrolledWindow()
        scroll.set_policy(self.Gtk.PolicyType.AUTOMATIC, self.Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(120)
        scroll.add(view)
        holder.pack_start(scroll, True, True, 0)
        grid.attach(holder, column, 0, 1, 1)
        return view

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._load_paths()
        self.refresh()

    def refresh(self) -> None:
        scope = self.scope.get_active_id() or "all"
        generation = self.gate.begin()
        self.values["plan"].set_text("Loading…")
        self.gate.run(
            generation,
            lambda: SyncStatus.from_json(
                self.runner.run(BackendCommands.sync_status(scope)).json()
            ),
            self._status_finished,
        )

    def _status_finished(self, value: SyncStatus | None, error: Exception | None) -> None:
        self.GLib.idle_add(self._apply_status, value, error)

    def _apply_status(self, value: SyncStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.values["plan"].set_text("Failed")
            self.log.append(str(error or "Unknown config-sync status error"), error=True)
            return False
        self.values["repo"].set_text(value.repository_path)
        self.values["profile"].set_text(value.profile)
        self.values["branch"].set_text(value.branch)
        self.values["relation"].set_text(f"{value.ahead} / {value.behind}")
        self.values["dirty"].set_text("Modified" if value.dirty else "Clean")
        self.values["last_sync"].set_text(value.last_sync or "Never")
        self.values["local"].set_text(str(len(value.local)))
        self.values["remote"].set_text(str(len(value.remote)))
        self.values["same"].set_text(str(len(value.same)))
        self.values["conflicts"].set_text(str(len(value.conflicts)))
        self.values["plan"].set_text(value.planned_action.replace("-", " "))
        self.values["backups"].set_text(str(len(value.backups)))
        for label in self.values.values():
            label.set_tooltip_text(label.get_text())
        for item in value.errors:
            self.log.append(item, error=True)
        return False

    def _action_clicked(self, command: str) -> None:
        if command == "status":
            self.refresh()
            return
        mutating = command in {"push", "pull", "sync", "init"}
        if mutating and not self._confirm_action(command):
            return
        scope = self.scope.get_active_id() or "all"
        argv = BackendCommands.sync_action(command, scope)
        if mutating:
            argv.append("--yes")
        if command in {"pull", "sync"}:
            argv.append("--no-apply")
        self._set_actions_sensitive(False)
        self.log.append(f"Starting config-sync {command} ({scope})")
        self.operation = StreamingProcess(argv, self._operation_event, self._operation_done)
        self.operation.start()

    def _confirm_action(self, command: str) -> bool:
        labels = {
            "push": "Upload safe local changes?",
            "pull": "Download safe remote changes?",
            "sync": "Synchronize local and remote changes?",
            "init": "Initialize synchronization state?",
        }
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.QUESTION,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text=labels[command],
        )
        dialog.format_secondary_text(
            "The existing config-sync conflict, checksum, backup and fast-forward rules remain active."
        )
        dialog.add_button("Continue", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        return bool(response == self.Gtk.ResponseType.OK)

    def _set_actions_sensitive(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.set_sensitive(enabled)
        self.scope.set_sensitive(enabled)

    def _operation_event(self, payload: dict[str, Any]) -> None:
        self.GLib.idle_add(
            self._append_operation_log,
            str(payload.get("message", payload.get("event", ""))),
            str(payload.get("stream", "")) == "stderr",
        )

    def _append_operation_log(self, message: str, error: bool) -> bool:
        self.log.append(message, error=error)
        return False

    def _operation_done(self, code: int, error: str | None) -> None:
        self.GLib.idle_add(self._finish_operation, code, error)

    def _finish_operation(self, code: int, error: str | None) -> bool:
        self.operation = None
        self._set_actions_sensitive(True)
        if error:
            self.log.append(error, error=True)
        self.log.append("Config Sync completed" if code == 0 else "Config Sync failed", error=code != 0)
        self.refresh()
        return False

    def _load_paths(self) -> None:
        repo = config_repo()
        if repo is None:
            self.path_status.set_text("Repository not found")
            return
        try:
            paths = (repo / "sync/paths.conf").read_text(encoding="utf-8")
            excludes = (repo / "sync/excludes.conf").read_text(encoding="utf-8")
        except OSError as exc:
            self.path_status.set_text(str(exc))
            return
        self.paths_view.get_buffer().set_text(paths)
        self.excludes_view.get_buffer().set_text(excludes)
        self.path_status.set_text(f"Loaded from {repo / 'sync'}")

    @staticmethod
    def _buffer_text(view: Any) -> str:
        buffer = view.get_buffer()
        return str(buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True))

    def _save_paths(self) -> None:
        repo = config_repo()
        if repo is None:
            self.path_status.set_text("Repository not found")
            return
        paths_file = repo / "sync/paths.conf"
        excludes_file = repo / "sync/excludes.conf"
        try:
            paths = validate_managed_paths(normalized_lines(self._buffer_text(self.paths_view)))
            excludes = validate_excludes(normalized_lines(self._buffer_text(self.excludes_view)))
            old_paths = paths_file.read_text(encoding="utf-8").splitlines(keepends=True)
            old_excludes = excludes_file.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, PathValidationError) as exc:
            self.path_status.set_text(str(exc))
            return
        new_paths = [f"{item}\n" for item in paths]
        new_excludes = [f"{item}\n" for item in excludes]
        diff = "".join(
            [
                *difflib.unified_diff(old_paths, new_paths, "paths.conf", "paths.conf"),
                *difflib.unified_diff(
                    old_excludes, new_excludes, "excludes.conf", "excludes.conf"
                ),
            ]
        )
        if not diff:
            self.path_status.set_text("No changes")
            return
        if not self._confirm_diff(diff):
            return
        try:
            atomic_write(paths_file, paths)
            atomic_write(excludes_file, excludes)
        except OSError as exc:
            self.path_status.set_text(str(exc))
            return
        self.path_status.set_text("Saved safely; review the repository diff before upload")
        self.refresh()

    def _confirm_diff(self, diff: str) -> bool:
        dialog = self.Gtk.Dialog(title="Review managed path changes", transient_for=self.parent_window, modal=True)
        dialog.add_button("Cancel", self.Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", self.Gtk.ResponseType.OK)
        dialog.set_default_size(760, 460)
        view = self.Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.get_buffer().set_text(diff)
        view.get_style_context().add_class("log-view")
        scroll = self.Gtk.ScrolledWindow()
        scroll.set_policy(self.Gtk.PolicyType.AUTOMATIC, self.Gtk.PolicyType.AUTOMATIC)
        scroll.add(view)
        area = dialog.get_content_area()
        area.set_margin_top(12)
        area.set_margin_bottom(12)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.pack_start(scroll, True, True, 0)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return bool(response == self.Gtk.ResponseType.OK)
