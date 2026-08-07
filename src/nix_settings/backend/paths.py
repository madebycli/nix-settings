from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

SECRET_PARTS = {
    ".ssh",
    ".gnupg",
    "sessions",
    "session",
    "local storage",
    "keyrings",
    "credentials",
}
SECRET_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "cookies",
    "cookies.sqlite",
    "login data",
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
SECRET_TOKENS = ("token", "secret", "password", "credential")


class PathValidationError(ValueError):
    pass


def normalized_lines(text: str) -> tuple[str, ...]:
    result: list[str] = []
    for raw in text.splitlines():
        value = raw.strip()
        if value and not value.startswith("#") and value not in result:
            result.append(value)
    return tuple(result)


def secret_reason(value: str) -> str | None:
    path = Path(value)
    lowered = value.casefold()
    parts = {item.casefold() for item in path.parts}
    name = path.name.casefold()
    if name in SECRET_NAMES or name.startswith(".env."):
        return "credential or environment file"
    if path.suffix.casefold() in SECRET_SUFFIXES:
        return "key or certificate file"
    if parts & SECRET_PARTS:
        return "credential, keyring or session directory"
    if any(token in lowered for token in SECRET_TOKENS):
        return "possible credential in path name"
    return None


def validate_managed_paths(values: Iterable[str], *, home: Path | None = None) -> tuple[str, ...]:
    root = (home or Path.home()).resolve()
    result: list[str] = []
    for value in values:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or value in {"", "."}:
            raise PathValidationError(f"unsafe managed path: {value}")
        reason = secret_reason(value)
        if reason:
            raise PathValidationError(f"unsafe managed path {value}: {reason}")
        candidate = root / path
        if candidate.is_symlink():
            raise PathValidationError(f"symbolic links are not allowed: {value}")
        result.append(path.as_posix())
    if not result:
        raise PathValidationError("at least one managed path is required")
    return tuple(result)


def validate_excludes(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise PathValidationError(f"unsafe exclude pattern: {value}")
        if value:
            result.append(value)
    return tuple(result)


def atomic_write(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)
