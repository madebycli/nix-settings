from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class RequestGate(Generic[T]):
    """Discard stale worker results without blocking the GTK main thread."""

    def __init__(self) -> None:
        self._generation = 0
        self._lock = threading.Lock()

    def begin(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def invalidate(self) -> None:
        self.begin()

    def run(
        self,
        generation: int,
        work: Callable[[], T],
        deliver: Callable[[T | None, Exception | None], None],
    ) -> None:
        def target() -> None:
            try:
                value = work()
                error: Exception | None = None
            except Exception as exc:
                value = None
                error = exc
            if self.current(generation):
                deliver(value, error)

        threading.Thread(target=target, name="nix-settings-request", daemon=True).start()
