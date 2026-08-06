from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable


class PipeWireMonitor:
    """Watch pw-dump changes without polling the whole graph continuously."""

    def __init__(
        self,
        on_change: Callable[[], None],
        on_disconnect: Callable[[str], None],
    ) -> None:
        self.on_change = on_change
        self.on_disconnect = on_disconnect
        self._stop = threading.Event()
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pipewire-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._process is not None:
            self._process.terminate()

    def _run(self) -> None:
        delay = 0.5
        while not self._stop.is_set():
            try:
                self._process = subprocess.Popen(
                    ["pw-dump", "--monitor"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    shell=False,
                )
                assert self._process.stdout is not None
                pending = False
                last_emit = 0.0
                for line in self._process.stdout:
                    if self._stop.is_set():
                        break
                    if not line.strip():
                        continue
                    pending = True
                    now = time.monotonic()
                    if now - last_emit >= 0.25:
                        self.on_change()
                        last_emit = now
                        pending = False
                if pending and not self._stop.is_set():
                    self.on_change()
                if self._stop.is_set():
                    return
                stderr = ""
                if self._process.stderr is not None:
                    stderr = self._process.stderr.read().strip()
                self.on_disconnect(stderr or "PipeWire monitor disconnected")
            except FileNotFoundError:
                self.on_disconnect("pw-dump is not installed")
            except OSError as exc:
                self.on_disconnect(str(exc))
            self._stop.wait(delay)
            delay = min(delay * 2, 8.0)
