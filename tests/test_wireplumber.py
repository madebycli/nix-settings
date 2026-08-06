from __future__ import annotations

import pytest

from nix_settings.audio.wireplumber import parse_wpctl_volume


def test_parse_wpctl_volume() -> None:
    assert parse_wpctl_volume("Volume: 0.42\n") == (0.42, False)
    assert parse_wpctl_volume("Volume: 0.75 [MUTED]\n") == (0.75, True)


def test_parse_wpctl_volume_is_capped() -> None:
    assert parse_wpctl_volume("Volume: 1.40\n") == (1.0, False)


def test_parse_wpctl_volume_rejects_unknown_output() -> None:
    with pytest.raises(ValueError):
        parse_wpctl_volume("unknown")
