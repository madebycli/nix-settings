from __future__ import annotations

from pathlib import Path

import pytest

from nix_settings.backend.paths import (
    PathValidationError,
    normalized_lines,
    secret_reason,
    validate_excludes,
    validate_managed_paths,
)
from nix_settings.backend.process import BackendCommands, redact_line
from nix_settings.privileged_helper import HelperError, MODE_INPUTS, dispatch


def test_log_redaction_and_ansi_removal() -> None:
    assert redact_line("\x1b[31mtoken=abc123\x1b[0m") == "token=<redacted>"
    assert "secret-value" not in redact_line("password: secret-value")


def test_secret_path_validation(tmp_path: Path) -> None:
    assert secret_reason(".config/niri") is None
    assert secret_reason(".ssh") is not None
    with pytest.raises(PathValidationError):
        validate_managed_paths(["../outside"], home=tmp_path)
    with pytest.raises(PathValidationError):
        validate_managed_paths([".config/browser/sessions"], home=tmp_path)
    assert validate_managed_paths([".config/niri"], home=tmp_path) == (".config/niri",)
    assert validate_excludes(["**/*.log"]) == ("**/*.log",)
    assert normalized_lines("a\na\n# comment\nb\n") == ("a", "b")


def test_helper_allowlist_rejects_arbitrary_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nix_settings.privileged_helper.os.geteuid", lambda: 0)
    monkeypatch.setattr("nix_settings.privileged_helper.event", lambda *_args, **_kwargs: None)
    with pytest.raises(HelperError):
        dispatch(["sh", "-c", "id"])


def test_privileged_commands_are_fixed_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIX_SETTINGS_HELPER", "/nix/store/helper")
    monkeypatch.setattr(
        "nix_settings.backend.process.shutil.which",
        lambda name: "/nix/store/pkexec" if name == "pkexec" else None,
    )
    assert BackendCommands.privileged("clean", "5") == [
        "/nix/store/pkexec",
        "/nix/store/helper",
        "clean",
        "5",
    ]
    with pytest.raises(ValueError):
        BackendCommands.privileged("shell", "id")


def test_refresh_helper_modes_match_backend() -> None:
    assert MODE_INPUTS["base"] == ("nixpkgs", "nix-cachyos-kernel")
    assert MODE_INPUTS["profiles"] == ()
