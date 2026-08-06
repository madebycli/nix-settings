from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass


class AudioCommandError(RuntimeError):
    """Raised when an audio control command fails."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class CommandRunner:
    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def run(self, args: Sequence[str]) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise AudioCommandError(f"Command not found: {args[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioCommandError(f"Command timed out: {args[0]}") from exc
        result = CommandResult(completed.stdout, completed.stderr, completed.returncode)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            raise AudioCommandError(f"{args[0]} failed: {detail}")
        return result


def normalize_volume(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def set_volume_args(node_id: int, volume: float) -> list[str]:
    return ["wpctl", "set-volume", str(node_id), f"{normalize_volume(volume):.3f}"]


def set_mute_args(node_id: int, muted: bool) -> list[str]:
    return ["wpctl", "set-mute", str(node_id), "1" if muted else "0"]


def set_default_args(node_id: int) -> list[str]:
    return ["wpctl", "set-default", str(node_id)]


def move_stream_args(stream_id: int, device_id: int) -> list[str]:
    return ["wpctl", "move", str(stream_id), str(device_id)]
