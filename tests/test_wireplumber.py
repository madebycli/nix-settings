from __future__ import annotations

import pytest

from nix_settings.audio.models import AudioDirection, AudioStream
from nix_settings.audio.wireplumber import parse_wpctl_volume, visible_recording_streams


def _recording(stream_id: int, app: str, media: str | None) -> AudioStream:
    return AudioStream(
        id=stream_id,
        application_name=app,
        application_icon=None,
        media_name=media,
        direction=AudioDirection.RECORDING,
        device_id=9,
        volume=1.0,
        volume_is_writable=True,
    )


def test_parse_wpctl_volume() -> None:
    assert parse_wpctl_volume("Volume: 0.42\n") == (0.42, False)
    assert parse_wpctl_volume("Volume: 0.75 [MUTED]\n") == (0.75, True)


def test_parse_wpctl_volume_is_capped() -> None:
    assert parse_wpctl_volume("Volume: 1.40\n") == (1.0, False)


def test_parse_wpctl_volume_rejects_unknown_output() -> None:
    with pytest.raises(ValueError):
        parse_wpctl_volume("unknown")


def test_recording_streams_only_keep_real_apps_once() -> None:
    streams = (
        _recording(1, "PulseAudio-Lautstärkeregler", "Ausschlagserkennung"),
        _recording(2, "PulseAudio-Lautstärkeregler", "Ausschlagserkennung"),
        _recording(3, "vesktop", "RecordStream"),
        _recording(4, "vesktop", "RecordStream"),
        _recording(5, "Unknown application", None),
    )
    visible = visible_recording_streams(streams)
    assert [stream.application_name for stream in visible] == ["vesktop"]
