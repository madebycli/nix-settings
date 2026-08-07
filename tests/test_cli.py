from __future__ import annotations

import io
import re
import sys
import types

import pytest

from nix_settings import __version__
from nix_settings.__main__ import PAGES, main, parser
from nix_settings.doctor import Check, run_doctor


def test_version_is_exposed() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_help_contains_pages_and_doctor() -> None:
    help_text = parser().format_help()
    for page in PAGES:
        assert page in help_text
    assert "doctor" in help_text


def test_default_page_is_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    module = types.ModuleType("nix_settings.app")
    module.run_gui = lambda page: seen.append(page) or 0
    monkeypatch.setitem(sys.modules, "nix_settings.app", module)
    assert main([]) == 0
    assert seen == ["overview"]


def test_direct_sound_page(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    module = types.ModuleType("nix_settings.app")
    module.run_gui = lambda page: seen.append(page) or 0
    monkeypatch.setitem(sys.modules, "nix_settings.app", module)
    assert main(["sound"]) == 0
    assert seen == ["sound"]


def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert f"nix-settings {__version__}" in capsys.readouterr().out


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
