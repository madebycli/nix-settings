from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nix_settings.backend.cache import JsonCache
from nix_settings.backend.models import SystemStatus, format_bytes
from nix_settings.backend.process import BackendCommands, JsonRunner
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.widgets.common import card, page_scroller, stat_row, styled_label


class OverviewPage:
    def __init__(
        self,
        Gtk: Any,
        GLib: Any,
        open_page: Callable[[str], None],
    ) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.open_page = open_page
        self.runner = JsonRunner(timeout=45.0)
        self.cache = JsonCache()
        self._has_snapshot = False
        self.local_gate: RequestGate[SystemStatus] = RequestGate()
        self.online_gate: RequestGate[SystemStatus] = RequestGate()
        self._started = False
        self.values: dict[str, Any] = {}

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._navigation(), False, False, 0)
        dashboard = Gtk.Grid()
        dashboard.set_column_homogeneous(True)
        dashboard.set_column_spacing(10)
        dashboard.set_row_spacing(10)
        dashboard.attach(self._system_card(), 0, 0, 1, 1)
        dashboard.attach(self._storage_card(), 1, 0, 1, 1)
        dashboard.attach(self._repository_card(), 0, 1, 1, 1)
        dashboard.attach(self._activity_card(), 1, 1, 1, 1)
        content.pack_start(dashboard, False, False, 0)
        self.widget = page_scroller(Gtk, content)

    def _navigation(self) -> Any:
        grid = self.Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        pages = (
            ("sound", "Sound", "Outputs, inputs and application streams"),
            ("updates", "Updates", "Preview and apply Nix Refresh modes"),
            ("sync", "Config Sync", "Safe repository and dotfile synchronization"),
            ("generations", "Generations", "Inspect, compare and roll back"),
            ("storage", "Storage", "Store usage, cleanup and optimization"),
            ("system", "System", "System actions and health checks"),
        )
        for index, (page, title, detail) in enumerate(pages):
            button = self.Gtk.Button()
            button.set_size_request(-1, 78)
            button.get_style_context().add_class("nav-card")
            body = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=4)
            body.pack_start(styled_label(self.Gtk, title, "card-title"), False, False, 0)
            body.pack_start(styled_label(self.Gtk, detail, "card-detail"), False, False, 0)
            button.add(body)
            button.connect("clicked", lambda _button, name=page: self.open_page(name))
            grid.attach(button, index % 3, index // 3, 1, 1)
        return grid

    def _system_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "SYSTEM", "section-title"), False, False, 0)
        for key, title in (
            ("host", "Hostname"),
            ("profile", "Active profile"),
            ("generation", "System generation"),
            ("generation_count", "Generations"),
            ("profile_packages", "Profile entries"),
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            box.pack_start(row, False, False, 0)
        return box

    def _storage_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "STORAGE", "section-title"), False, False, 0)
        for key, title in (
            ("store", "Nix Store"),
            ("closure", "Current closure"),
            ("disk", "Disk used"),
            ("free", "Disk free"),
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            box.pack_start(row, False, False, 0)
        self.disk_bar = self.Gtk.ProgressBar()
        self.disk_bar.set_show_text(True)
        self.disk_bar.get_style_context().add_class("deck-progress")
        box.pack_start(self.disk_bar, False, False, 0)
        return box

    def _repository_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "CONFIG REPOSITORY", "section-title"), False, False, 0)
        for key, title in (
            ("repo", "Path"),
            ("branch", "Branch"),
            ("worktree", "Worktree"),
            ("relation", "GitHub relation"),
            ("last_sync", "Last config sync"),
        ):
            row, value = stat_row(self.Gtk, title)
            self.values[key] = value
            box.pack_start(row, False, False, 0)
        return box

    def _activity_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "STATUS", "section-title"), False, False, 0)
        row, value = stat_row(self.Gtk, "Snapshot")
        self.values["snapshot"] = value
        box.pack_start(row, False, False, 0)
        row, value = stat_row(self.Gtk, "Online check")
        self.values["online"] = value
        box.pack_start(row, False, False, 0)
        self.error = styled_label(self.Gtk, "", "card-detail")
        self.error.set_line_wrap(True)
        box.pack_start(self.error, False, False, 0)
        return box

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        cached = self.cache.load("system-status")
        if cached is not None:
            try:
                value = SystemStatus.from_json(cached)
            except ValueError:
                pass
            else:
                self._apply_status(value)
                self.values["snapshot"].set_text(f"Cached · {value.updated_at}")
                self.values["online"].set_text("Refreshing…")
        self.refresh()

    def refresh(self) -> None:
        self.values["snapshot"].set_text("Loading local data…")
        self.values["online"].set_text("Waiting")
        generation = self.local_gate.begin()
        self.local_gate.run(generation, self._load_local, self._local_finished)

    def _load_local(self) -> SystemStatus:
        payload = self.runner.run(BackendCommands.status(online=False)).json()
        self.cache.save("system-status", payload)
        return SystemStatus.from_json(payload)

    def _load_online(self) -> SystemStatus:
        payload = self.runner.run(BackendCommands.status(online=True)).json()
        self.cache.save("system-status", payload)
        return SystemStatus.from_json(payload)

    def _local_finished(
        self,
        value: SystemStatus | None,
        error: Exception | None,
    ) -> None:
        self.GLib.idle_add(self._apply_local, value, error)

    def _apply_local(self, value: SystemStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.values["snapshot"].set_text(
                "Cached · refresh failed" if self._has_snapshot else "Failed"
            )
            self.error.set_text(str(error or "Unknown status error"))
        else:
            self._apply_status(value)
            self.values["snapshot"].set_text(value.updated_at)
        self.values["online"].set_text("Checking…")
        generation = self.online_gate.begin()
        self.online_gate.run(generation, self._load_online, self._online_finished)
        return False

    def _online_finished(
        self,
        value: SystemStatus | None,
        error: Exception | None,
    ) -> None:
        self.GLib.idle_add(self._apply_online, value, error)

    def _apply_online(self, value: SystemStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.values["online"].set_text("Cached" if self._has_snapshot else "Failed")
            self.error.set_text(str(error or "Online status failed"))
        else:
            self._apply_status(value)
            self.values["online"].set_text("Complete")
        return False

    def _apply_status(self, value: SystemStatus) -> None:
        self._has_snapshot = True
        self.values["host"].set_text(value.host)
        self.values["profile"].set_text(value.profile)
        current = "—" if value.current_generation is None else str(value.current_generation)
        latest = "—" if value.latest_generation is None else str(value.latest_generation)
        self.values["generation"].set_text(f"{current} / latest {latest}")
        self.values["generation_count"].set_text(str(value.generation_count))
        self.values["profile_packages"].set_text(str(value.profile_package_count))
        self.values["store"].set_text(format_bytes(value.store_bytes))
        self.values["closure"].set_text(format_bytes(value.closure_bytes))
        self.values["disk"].set_text(format_bytes(value.disk_used_bytes))
        self.values["free"].set_text(format_bytes(value.disk_free_bytes))
        self.disk_bar.set_fraction(max(0.0, min(1.0, value.disk_used_percent / 100.0)))
        self.disk_bar.set_text(f"{value.disk_used_percent}% used")
        self.values["repo"].set_text(value.repository_path)
        self.values["branch"].set_text(value.branch or "detached")
        self.values["worktree"].set_text("Modified" if value.dirty else "Clean")
        self.values["relation"].set_text(f"ahead {value.ahead} · behind {value.behind}")
        self.values["last_sync"].set_text(value.last_sync or "Never")
        self.error.set_text(" · ".join(value.errors))
        for label in self.values.values():
            label.set_tooltip_text(label.get_text())
