from __future__ import annotations

import re
from dataclasses import replace

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.commands import (
    AudioCommandError,
    CommandRunner,
    move_stream_args,
    set_default_args,
    set_mute_args,
    set_volume_args,
)
from nix_settings.audio.models import AudioDevice, AudioSnapshot, AudioStream
from nix_settings.audio.pipewire import parse_pw_dump

_VOLUME_RE = re.compile(r"Volume:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_wpctl_volume(text: str) -> tuple[float, bool]:
    match = _VOLUME_RE.search(text)
    if match is None:
        raise ValueError("wpctl returned an unknown volume format")
    volume = max(0.0, min(1.0, float(match.group(1))))
    muted = "[MUTED]" in text.upper()
    return volume, muted


class WirePlumberBackend(AudioBackend):
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def snapshot(self) -> AudioSnapshot:
        snapshot = parse_pw_dump(self.runner.run(["pw-dump"]).stdout)
        return replace(
            snapshot,
            outputs=tuple(self._device_volume(device) for device in snapshot.outputs),
            inputs=tuple(self._device_volume(device) for device in snapshot.inputs),
            playback_streams=tuple(
                self._stream_volume(stream) for stream in snapshot.playback_streams
            ),
            recording_streams=tuple(
                self._stream_volume(stream) for stream in snapshot.recording_streams
            ),
        )

    def _live_volume(self, node_id: int) -> tuple[float, bool] | None:
        try:
            output = self.runner.run(["wpctl", "get-volume", str(node_id)]).stdout
            return parse_wpctl_volume(output)
        except (AudioCommandError, ValueError):
            return None

    def _device_volume(self, device: AudioDevice) -> AudioDevice:
        state = self._live_volume(device.id)
        return device if state is None else replace(device, volume=state[0], is_muted=state[1])

    def _stream_volume(self, stream: AudioStream) -> AudioStream:
        state = self._live_volume(stream.id)
        return stream if state is None else replace(stream, volume=state[0], is_muted=state[1])

    def set_volume(self, node_id: int, volume: float) -> None:
        self.runner.run(set_volume_args(node_id, volume))

    def set_muted(self, node_id: int, muted: bool) -> None:
        self.runner.run(set_mute_args(node_id, muted))

    def set_default(self, node_id: int) -> None:
        self.runner.run(set_default_args(node_id))

    def move_stream(self, stream_id: int, device_id: int) -> None:
        self.runner.run(move_stream_args(stream_id, device_id))
