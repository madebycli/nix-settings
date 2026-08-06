from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


class AudioDirection(StrEnum):
    OUTPUT = "output"
    INPUT = "input"
    PLAYBACK = "playback"
    RECORDING = "recording"


@dataclass(frozen=True, slots=True)
class AudioDevice:
    id: int
    name: str
    description: str
    direction: AudioDirection
    is_default: bool = False
    is_muted: bool = False
    volume: float = 1.0
    ports: tuple[str, ...] = ()
    active_port: str | None = None
    profiles: tuple[str, ...] = ()
    active_profile: str | None = None

    def with_default(self, selected: bool) -> AudioDevice:
        return replace(self, is_default=selected)


@dataclass(frozen=True, slots=True)
class AudioStream:
    id: int
    application_name: str
    application_icon: str | None
    media_name: str | None
    direction: AudioDirection
    device_id: int | None
    is_muted: bool = False
    volume: float = 1.0
    volume_is_writable: bool = False
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class AudioSnapshot:
    outputs: tuple[AudioDevice, ...]
    inputs: tuple[AudioDevice, ...]
    playback_streams: tuple[AudioStream, ...]
    recording_streams: tuple[AudioStream, ...]
    default_output_id: int | None
    default_input_id: int | None
    timestamp: datetime

    @classmethod
    def empty(cls) -> AudioSnapshot:
        return cls((), (), (), (), None, None, datetime.now(UTC))
