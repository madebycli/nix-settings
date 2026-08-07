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


def test_log_view_supports_selection_ctrl_c_and_clipboard_button() -> None:
    source = (ROOT / "src/nix_settings/gui/widgets/log_view.py").read_text(encoding="utf-8")
    assert "set_cursor_visible(True)" in source
    assert 'connect("key-press-event", self._key_press)' in source
    assert "get_selection_bound" in source
    assert "SELECTION_CLIPBOARD" in source
    assert "clipboard.store()" in source
