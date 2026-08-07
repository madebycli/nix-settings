from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from nix_settings.__main__ import main
from nix_settings.backend.github_auth import AuthStatus, GitHubCliAuth
from nix_settings.terminal import find_login_terminal

ROOT = Path(__file__).resolve().parents[1]


def test_terminal_fallback_reuses_packaged_nix_settings_login_command() -> None:
    resolved = {
        "nix-settings": "/nix/store/test/bin/nix-settings",
        "ghostty": "/run/current-system/sw/bin/ghostty",
    }
    with mock.patch(
        "nix_settings.terminal.shutil.which",
        side_effect=lambda value: resolved.get(value),
    ):
        detected = find_login_terminal()
    assert detected is not None
    launcher, command = detected
    assert launcher.name == "Ghostty"
    assert command == [
        "/run/current-system/sw/bin/ghostty",
        "-e",
        "/nix/store/test/bin/nix-settings",
        "github-login",
    ]


def test_terminal_github_login_command_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        GitHubCliAuth,
        "login",
        lambda _self: AuthStatus(True, True, login="madebycli"),
    )
    assert main(["github-login"]) == 0


def test_login_dialog_keeps_backup_terminal_fallback_and_opaque_surface() -> None:
    source = (ROOT / "src/nix_settings/gui/github_login.py").read_text(encoding="utf-8")
    assert "launch_login_terminal" in source
    assert "Open terminal login" in source
    assert 'add_class("nix-settings-root")' in source
    assert "set_opacity(1.0)" in source


def test_log_view_uses_native_wayland_clipboard_and_selection_copy() -> None:
    source = (ROOT / "src/nix_settings/gui/widgets/log_view.py").read_text(encoding="utf-8")
    assert "set_cursor_visible(True)" in source
    assert 'connect("key-press-event", self._key_press)' in source
    assert "Clipboard.get_default" in source
    assert "get_has_selection()" in source
    assert "copy_clipboard(clipboard)" in source
    assert "SELECTION_CLIPBOARD" in source
    assert 'set_label("Copied")' in source
    assert "clipboard.store()" in source


def test_main_shell_is_opaque_and_reuses_compact_title_bar_geometry() -> None:
    style = (ROOT / "src/nix_settings/gui/style.css").read_text(encoding="utf-8")
    window = (ROOT / "src/nix_settings/gui/window.py").read_text(encoding="utf-8")
    modal = (ROOT / "src/nix_settings/gui/modal.py").read_text(encoding="utf-8")

    assert ".nix-settings-root {\n  background: rgb(14, 14, 14);" in style
    assert ".main-header {\n  min-height: 32px;" in style
    assert 'header.set_size_request(-1, 32)' in window
    assert "header.set_margin_top(6)" in window
    assert "header.set_margin_bottom(6)" in window
    assert 'add_class("home-icon")' in window
    assert "font-size: 20px" in style
    assert "dialog.set_opacity(1.0)" in modal
    assert 'add_class("nix-settings-modal-content")' in modal


def test_sync_dashboard_has_no_outer_page_scrollbar() -> None:
    source = (ROOT / "src/nix_settings/gui/pages/sync.py").read_text(encoding="utf-8")
    assert 'add_class("sync-content")' in source
    assert "self.widget = content" in source
    assert "page_scroller" not in source
    assert "LogView(Gtk, min_height=120)" in source
    assert "scroll.set_min_content_height(78)" in source
