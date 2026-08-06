from __future__ import annotations

from pathlib import Path

import pytest

from nix_settings.audio.models import AudioDirection
from nix_settings.audio.pipewire import PipeWireParseError, parse_pw_dump

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_devices_and_defaults() -> None:
    snapshot = parse_pw_dump(fixture("basic.json"))
    assert snapshot.default_output_id == 42
    assert snapshot.default_input_id == 43
    assert snapshot.outputs[0].is_default
    assert snapshot.outputs[0].volume == pytest.approx(0.72)
    assert snapshot.inputs[0].is_muted
    assert snapshot.inputs[0].direction is AudioDirection.INPUT


def test_parses_ports_and_profiles() -> None:
    snapshot = parse_pw_dump(fixture("basic.json"))
    output = snapshot.outputs[0]
    assert output.active_port == "analog-output-speaker"
    assert output.active_profile == "output:analog-stereo"
    assert "output:analog-stereo" in output.profiles


def test_identifies_playback_and_recording_streams() -> None:
    snapshot = parse_pw_dump(fixture("streams.json"))
    assert snapshot.playback_streams[0].application_name == "Firefox"
    assert snapshot.playback_streams[0].device_id == 10
    assert snapshot.playback_streams[0].volume_is_writable
    assert snapshot.recording_streams[0].application_name == "Discord"
    assert snapshot.recording_streams[0].device_id == 11
    assert not snapshot.recording_streams[0].volume_is_writable


def test_bluetooth_profile_and_channel_volume() -> None:
    snapshot = parse_pw_dump(fixture("bluetooth.json"))
    device = snapshot.outputs[0]
    assert device.description == "WH-1000XM5"
    assert device.active_profile == "a2dp-sink"
    assert device.volume == pytest.approx(0.6)


def test_empty_graph_is_valid() -> None:
    snapshot = parse_pw_dump("[]")
    assert not snapshot.outputs
    assert not snapshot.recording_streams


@pytest.mark.parametrize("payload", ["not-json", fixture("malformed.json")])
def test_malformed_data(payload: str) -> None:
    with pytest.raises(PipeWireParseError):
        parse_pw_dump(payload)


def test_routes_streams_from_link_objects() -> None:
    snapshot = parse_pw_dump(fixture("links.json"))
    assert snapshot.playback_streams[0].device_id == 10
    assert snapshot.recording_streams[0].device_id == 11


def test_several_outputs_keep_default_first() -> None:
    snapshot = parse_pw_dump(fixture("several-outputs.json"))
    assert [device.id for device in snapshot.outputs] == [31, 30]
    assert snapshot.default_output_id == 31


def test_disconnected_fixture_is_empty_snapshot() -> None:
    snapshot = parse_pw_dump(fixture("disconnected.json"))
    assert snapshot.outputs == ()
    assert snapshot.inputs == ()
