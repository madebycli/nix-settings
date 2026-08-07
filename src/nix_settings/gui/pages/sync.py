from __future__ import annotations

import difflib
from typing import Any

from nix_settings.backend.models import GitHubSyncStatus, SyncStatus
from nix_settings.backend.paths import (
    PathValidationError,
    atomic_write,
    normalized_lines,
    validate_excludes,
    validate_managed_paths,
)
from nix_settings.backend.process import BackendCommands, JsonRunner, StreamingProcess, config_repo
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.github_login import run_login
from nix_settings.gui.widgets.common import (
    action_button,
    card,
    page_scroller,
    stat_row,
    styled_label,
)
from nix_settings.gui.widgets.log_view import LogView


def sync_action_enabled(command: str, github: GitHubSyncStatus | None) -> bool:
    if command not in {"push", "sync"}:
        return True
    return bool(
        github is not None
        and github.gh_installed
        and github.authenticated
        and github.can_push
        and github.remote_ok
    )


class SyncPage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=180.0)
        self.gate: RequestGate[SyncStatus] = RequestGate()
        self.operation: StreamingProcess | None = None
        self.current_status: SyncStatus | None = None
        self.values: dict[str, Any] = {}
        self.action_buttons: dict[str, Any] = {}
        self.busy = False
        self._started = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._top_cards(), False, False, 0)
        content.pack_start(self._actions_card(), False, False, 0)
        content.pack_start(self._paths_editor(), False, False, 0)
        content.pack_start(self._progress(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _top_cards(self) -> Any:
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(12)
        grid.attach(self._account_card(), 0, 0, 1, 1)
        grid.attach(self._repository_card(), 1, 0, 1, 1)
        return grid

    def _account_card(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(
            styled_label(self.Gtk, "GITHUB ACCOUNT", "section-title"),
            True,
            True,
            0,
        )
        self.github_badge = styled_label(self.Gtk, "CHECKING", "status-text", xalign=0.5)
        self.github_badge.set_size_request(112, 28)
        header.pack_end(self.github_badge, False, False, 0)
        box.pack_start(header, False, False, 0)

        self.account_name = styled_label(self.Gtk, "Checking GitHub CLI…", "card-title")
        self.account_detail = styled_label(
            self.Gtk,
            "Browser login uses GitHub CLI; Nix Settings never handles the token.",
            "card-detail",
        )
        box.pack_start(self.account_name, False, False, 0)
        box.pack_start(self.account_detail, False, False, 0)

        self.login_button = action_button(
            self.Gtk,
            "Sign in",
            self._login_clicked,
            width=132,
            primary=True,
        )
        self.login_button.set_halign(self.Gtk.Align.START)
        box.pack_end(self.login_button, False, False, 0)
        return box

    def _repository_card(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(
            styled_label(self.Gtk, "SYNC REPOSITORY", "section-title"),
            True,
            True,
            0,
        )
        self.scope = self.Gtk.ComboBoxText()
        for key, label in (("all", "All"), ("nixos", "NixOS"), ("dotfiles", "Dotfiles")):
            self.scope.append(key, label)
        self.scope.set_active_id("all")
        self.scope.set_size_request(126, 30)
        self.scope.connect("changed", lambda *_: self.refresh())
        header.pack_end(self.scope, False, False, 0)
        box.pack_start(header, False, False, 0)

        for key, title in (
            ("repo", "Repository"),
            ("branch", "Branch"),
            ("relation", "Ahead / Behind"),
            ("dirty", "Worktree"),
            ("last_sync", "Last sync"),
            ("plan", "Planned action"),
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            box.pack_start(row, False, False, 0)
        return box

    def _actions_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "SYNC ACTIONS", "section-title"), False, False, 0)
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        actions = (
            ("pull", "Download"),
            ("push", "Upload"),
            ("sync", "Synchronize"),
            ("init", "Initialize"),
            ("history", "History"),
            ("doctor", "Doctor"),
        )
        for index, (command, label) in enumerate(actions):
            button = action_button(
                self.Gtk,
                label,
                lambda _button, value=command: self._action_clicked(value),
                width=138,
                primary=command == "sync",
            )
            self.action_buttons[command] = button
            grid.attach(button, index % 3, index // 3, 1, 1)
        box.pack_start(grid, False, False, 0)

        self.sync_summary = styled_label(
            self.Gtk,
            "Download stays read-only for GitHub authentication. Upload and Synchronize require browser sign-in.",
            "card-detail",
        )
        box.pack_start(self.sync_summary, False, False, 0)
        return box

    def _paths_editor(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(
            styled_label(self.Gtk, "MANAGED DOTFILE PATHS", "section-title"),
            True,
            True,
            0,
        )
        reload_button = action_button(self.Gtk, "Reload", lambda *_: self._load_paths(), width=88)
        save_button = action_button(
            self.Gtk,
            "Review & save",
            lambda *_: self._save_paths(),
            width=132,
            primary=True,
        )
        header.pack_start(reload_button, False, False, 0)
        header.pack_start(save_button, False, False, 0)
        box.pack_start(header, False, False, 0)

        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(10)
        self.paths_view = self._editor_column(
            grid,
            0,
            "PATHS",
            "One path relative to HOME per line",
        )
        self.excludes_view = self._editor_column(
            grid,
            1,
            "EXCLUDES",
            "Glob patterns relative to HOME",
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
        scroll.set_min_content_height(112)
        scroll.add(view)
        holder.pack_start(scroll, True, True, 0)
        grid.attach(holder, column, 0, 1, 1)
        return view

    def _progress(self) -> Any:
        box = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=7)
        row = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        self.operation_status = styled_label(self.Gtk, "Ready", "card-detail")
        row.pack_start(self.operation_status, True, True, 0)
        self.progress = self.Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Waiting")
        self.progress.get_style_context().add_class("deck-progress")
        box.pack_start(row, False, False, 0)
        box.pack_start(self.progress, False, False, 0)
        return box

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._load_paths()
        self.refresh()

    def refresh(self) -> None:
        if self.busy:
            return
        scope = self.scope.get_active_id() or "all"
        generation = self.gate.begin()
        self.values["plan"].set_text("Loading…")
        self.github_badge.set_text("CHECKING")
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
            self.current_status = None
            self.values["plan"].set_text("Failed")
            self.github_badge.set_text("ERROR")
            self.log.append(str(error or "Unknown config-sync status error"), error=True)
            self._set_actions_sensitive(True)
            return False

        self.current_status = value
        self.values["repo"].set_text(value.repository_path)
        self.values["branch"].set_text(value.branch)
        self.values["relation"].set_text(f"{value.ahead} / {value.behind}")
        self.values["dirty"].set_text("Modified" if value.dirty else "Clean")
        self.values["last_sync"].set_text(value.last_sync or "Never")
        self.values["plan"].set_text(value.planned_action.replace("-", " "))
        for label in self.values.values():
            label.set_tooltip_text(label.get_text())

        github = value.github
        if github.authenticated:
            account = f"@{github.login}" if github.login else "Signed in"
            self.account_name.set_text(account)
            permission = github.permission or "unknown permission"
            identity = github.git_email or github.git_name or "Git identity will be configured on upload"
            self.account_detail.set_text(f"{permission} · {identity}")
            self.github_badge.set_text("READY" if github.can_push else "READ ONLY")
            self.login_button.set_label("Switch account")
        elif github.gh_installed:
            self.account_name.set_text("Not signed in")
            self.account_detail.set_text(
                "Use browser login once. Download remains available without authentication."
            )
            self.github_badge.set_text("SIGNED OUT")
            self.login_button.set_label("Sign in")
        else:
            self.account_name.set_text("GitHub CLI unavailable")
            self.account_detail.set_text(github.error or "The packaged gh executable was not found")
            self.github_badge.set_text("NO GH")
            self.login_button.set_label("Sign in")

        counts = (
            f"Dotfiles: {len(value.local)} local · {len(value.remote)} remote · "
            f"{len(value.conflicts)} conflicts"
        )
        self.sync_summary.set_text(counts)
        for item in value.errors:
            self.log.append(item, error=True)
        self._set_actions_sensitive(True)
        return False

    def _login_clicked(self, _button: Any) -> None:
        if self.busy:
            return
        self.log.append("Starting GitHub CLI browser login")
        if run_login(self.parent_window):
            self.log.append("GitHub login completed")
        else:
            self.log.append("GitHub login cancelled or incomplete")
        self.refresh()

    def _action_clicked(self, command: str) -> None:
        if self.busy:
            return
        status = self.current_status
        github = status.github if status is not None else None
        if not sync_action_enabled(command, github):
            self.log.append("Sign in to GitHub with write access before uploading", error=True)
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

        self.busy = True
        self._set_actions_sensitive(False)
        self.operation_status.set_text(f"Running {command}…")
        self.progress.set_fraction(0.0)
        self.progress.set_text(f"{command.capitalize()} in progress")
        self.GLib.timeout_add(120, self._pulse_progress)
        self.log.append(f"Starting config-sync {command} ({scope})")
        self.operation = StreamingProcess(argv, self._operation_event, self._operation_done)
        self.operation.start()

    def _confirm_action(self, command: str) -> bool:
        labels = {
            "push": "Upload safe local changes to GitHub?",
            "pull": "Download safe changes from GitHub?",
            "sync": "Synchronize local and GitHub changes?",
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
            "Secret checks, three-way conflict detection, backups and fast-forward-only history remain active."
        )
        dialog.add_button("Continue", self.Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        return bool(response == self.Gtk.ResponseType.OK)

    def _pulse_progress(self) -> bool:
        if not self.busy:
            return False
        self.progress.pulse()
        return True

    def _set_actions_sensitive(self, enabled: bool) -> None:
        self.scope.set_sensitive(enabled and not self.busy)
        self.login_button.set_sensitive(enabled and not self.busy)
        github = self.current_status.github if self.current_status is not None else None
        for command, button in self.action_buttons.items():
            button.set_sensitive(enabled and not self.busy and sync_action_enabled(command, github))

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
        self.busy = False
        if error:
            self.log.append(error, error=True)
        success = code == 0
        self.log.append("Config Sync completed" if success else "Config Sync failed", error=not success)
        self.operation_status.set_text("Ready" if success else "Last operation failed")
        self.progress.set_fraction(1.0 if success else 0.0)
        self.progress.set_text("Complete" if success else "Failed")
        self._set_actions_sensitive(True)
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
                    old_excludes,
                    new_excludes,
                    "excludes.conf",
                    "excludes.conf",
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
        dialog = self.Gtk.Dialog(
            title="Review managed path changes",
            transient_for=self.parent_window,
            modal=True,
        )
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
