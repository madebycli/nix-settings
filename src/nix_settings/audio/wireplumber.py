from __future__ import annotations

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.commands import (
    CommandRunner,
    move_stream_args,
    set_default_args,
    set_mute_args,
    set_volume_args,
)
from nix_settings.audio.models import AudioSnapshot
from nix_settings.audio.pipewire import parse_pw_dump


class WirePlumberBackend(AudioBackend):
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def snapshot(self) -> AudioSnapshot:
        return parse_pw_dump(self.runner.run(["pw-dump"]).stdout)

    def set_volume(self, node_id: int, volume: float) -> None:
        self.runner.run(set_volume_args(node_id, volume))

    def set_muted(self, node_id: int, muted: bool) -> None:
        self.runner.run(set_mute_args(node_id, muted))

    def set_default(self, node_id: int) -> None:
        self.runner.run(set_default_args(node_id))

    def move_stream(self, stream_id: int, device_id: int) -> None:
        self.runner.run(move_stream_args(stream_id, device_id))
