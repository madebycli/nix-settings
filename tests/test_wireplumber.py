from __future__ import annotations

import pytest

from nix_settings.audio.commands import CommandResult
from nix_settings.audio.wireplumber import WirePlumberBackend, parse_wpctl_volume


def test_parse_wpctl_volume() -> None:
    assert parse_wpctl_volume("Volume: 0.42\n") == (0.42, False)
    assert parse_wpctl_volume("Volume: 0.75 [MUTED]\n") == (0.75, True)


def test_parse_wpctl_volume_is_capped() -> None:
    assert parse_wpctl_volume("Volume: 1.40\n") == (1.0, False)


def test_parse_wpctl_volume_rejects_unknown_output() -> None:
    with pytest.raises(ValueError):
        parse_wpctl_volume("unknown")


def test_pending_volume_masks_stale_snapshot_until_confirmed() -> None:
    class Runner:
        def run(self, _args: list[str]) -> CommandResult:
            return CommandResult("", "", 0)

    backend = WirePlumberBackend(Runner())  # type: ignore[arg-type]
    backend.set_volume(7, 0.90)
    assert backend._effective_volume(7, 0.22) == 0.90
    assert backend._effective_volume(7, 0.90) == 0.90
    assert 7 not in backend._pending_volumes
