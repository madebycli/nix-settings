from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")


class JsonCache:
    """Small fail-soft cache for non-secret structured UI snapshots."""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            root = base / "nix-settings"
        self.root = root

    def _path(self, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ValueError("invalid cache key")
        return self.root / f"{key}.json"

    def load(self, key: str) -> Mapping[str, Any] | None:
        path = self._path(key)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("cacheVersion") != 1:
            return None
        payload = value.get("payload")
        return payload if isinstance(payload, dict) else None

    def save(self, key: str, payload: object) -> None:
        if not isinstance(payload, Mapping):
            return
        path = self._path(key)
        temporary: Path | None = None
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_text(
                json.dumps({"cacheVersion": 1, "payload": dict(payload)}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            os.replace(temporary, path)
        except OSError:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
