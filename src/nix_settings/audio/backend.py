from __future__ import annotations

from abc import ABC, abstractmethod

from nix_settings.audio.models import AudioSnapshot


class AudioBackend(ABC):
    @abstractmethod
    def snapshot(self) -> AudioSnapshot:
        raise NotImplementedError

    @abstractmethod
    def set_volume(self, node_id: int, volume: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_muted(self, node_id: int, muted: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_default(self, node_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def move_stream(self, stream_id: int, device_id: int) -> None:
        raise NotImplementedError
