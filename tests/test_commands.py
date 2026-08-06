from __future__ import annotations

import inspect

from nix_settings.audio import commands
from nix_settings.audio.commands import (
    move_stream_args,
    normalize_volume,
    set_default_args,
    set_mute_args,
    set_volume_args,
)


def test_volume_normalization() -> None:
    assert normalize_volume(-1) == 0
    assert normalize_volume(0.4) == 0.4
    assert normalize_volume(2) == 1


def test_control_argument_construction() -> None:
    assert set_volume_args(4, 2.0) == ["wpctl", "set-volume", "4", "1.000"]
    assert set_mute_args(4, True) == ["wpctl", "set-mute", "4", "1"]
    assert set_default_args(4) == ["wpctl", "set-default", "4"]
    assert move_stream_args(7, 4) == ["wpctl", "move", "7", "4"]


def test_runner_explicitly_disables_shell() -> None:
    source = inspect.getsource(commands.CommandRunner.run)
    assert "shell=False" in source
    assert "shell=True" not in source
