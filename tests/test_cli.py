from __future__ import annotations

import io

import pytest

from nix_settings import __version__
from nix_settings.__main__ import main, parser
from nix_settings.doctor import Check, run_doctor


def test_version_is_exposed() -> None:
    assert __version__ == "0.2.0"


def test_help_contains_commands() -> None:
    help_text = parser().format_help()
    assert "sound" in help_text
    assert "doctor" in help_text


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "nix-settings 0.2.0" in capsys.readouterr().out


def test_doctor_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "nix_settings.doctor.collect_checks",
        lambda: [Check("required", False, "missing"), Check("optional", False, "missing", False)],
    )
    output = io.StringIO()
    assert run_doctor(output) == 1
    text = output.getvalue()
    assert "[FAIL] required" in text
    assert "[WARN] optional" in text
