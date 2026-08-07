from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
SECRET_RE = re.compile(
    r"(?i)(token|secret|password|passwd|authorization|private[-_ ]?key)\s*[:=]\s*([^\s]+)"
)


class ProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            raise ProcessError(f"invalid JSON from {self.argv[0]}: {exc}") from exc


def redact_line(value: str) -> str:
    clean = ANSI_RE.sub("", value)
    return SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", clean)


class JsonRunner:
    def __init__(self, *, timeout: float = 120.0) -> None:
        self.timeout = timeout

    @staticmethod
    def environment() -> dict[str, str]:
        allowed = (
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "XDG_STATE_HOME",
            "XDG_CONFIG_HOME",
            "NIX_PATH",
            "NIXOS_CONFIG_REPO",
            "SSL_CERT_FILE",
            "NIX_SSL_CERT_FILE",
            "LOCALE_ARCHIVE",
        )
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env["NO_COLOR"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        env["NIX_SETTINGS_NONINTERACTIVE"] = "1"
        return env

    def run(self, argv: Sequence[str], *, timeout: float | None = None) -> CommandResult:
        if not argv or not all(isinstance(item, str) and item for item in argv):
            raise ValueError("argv must contain non-empty strings")
        try:
            completed = subprocess.run(
                list(argv),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.environment(),
                timeout=self.timeout if timeout is None else timeout,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise ProcessError(f"program not found: {argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProcessError(f"command timed out: {argv[0]}") from exc
        result = CommandResult(
            tuple(argv),
            completed.returncode,
            redact_line(completed.stdout),
            redact_line(completed.stderr),
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise ProcessError(detail or f"command failed with exit code {result.returncode}")
        return result


class StreamingProcess:
    def __init__(
        self,
        argv: Sequence[str],
        on_event: Callable[[dict[str, Any]], None],
        on_done: Callable[[int, str | None], None],
    ) -> None:
        self.argv = tuple(argv)
        self.on_event = on_event
        self.on_done = on_done
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._run, name="nix-settings-operation", daemon=True).start()

    def cancel(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    def _run(self) -> None:
        error: str | None = None
        code = 1
        try:
            process = subprocess.Popen(
                list(self.argv),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=JsonRunner.environment(),
                start_new_session=True,
                bufsize=1,
            )
            with self._lock:
                self._process = process
            assert process.stdout is not None
            for raw in process.stdout:
                line = redact_line(raw.rstrip("\n"))
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"event": "log", "stream": "stdout", "message": line}
                self.on_event(payload)
            code = process.wait()
            if code != 0:
                error = f"operation failed with exit code {code}"
        except OSError as exc:
            error = str(exc)
        finally:
            with self._lock:
                self._process = None
            self.on_done(code, error)


def config_repo() -> Path | None:
    explicit = os.environ.get("NIXOS_CONFIG_REPO")
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    try:
        host = os.uname().nodename.split(".", 1)[0]
    except AttributeError:
        host = ""
    home = Path.home()
    candidates.extend([home / host, home / "nyx", home / "aether"])
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / ".git").is_dir() and (resolved / "flake.nix").is_file():
            return resolved
    return None


class BackendCommands:
    @staticmethod
    def status(*, online: bool) -> list[str]:
        result = ["nix-status", "--json"]
        if online:
            result.append("--online")
        return result

    @staticmethod
    def updates(mode: str, *, full: bool = False) -> list[str]:
        result = ["nix-updates", mode, "--json"]
        if full:
            result.append("--full")
        return result

    @staticmethod
    def generations(limit: int | None = None) -> list[str]:
        result = ["nix-generations", "--json"]
        if limit is not None:
            result.extend(["--last", str(limit)])
        return result

    @staticmethod
    def clean_preview(backups: int) -> list[str]:
        return ["nix-clean", "--dry-run", str(backups), "--json"]

    @staticmethod
    def sync_status(scope: str, *, offline: bool = False) -> list[str]:
        repo = config_repo()
        if repo is None:
            raise ProcessError("Nix configuration repository was not found")
        adapter = repo / "scripts/config-sync-json.py"
        if not adapter.is_file():
            raise ProcessError(f"structured config-sync adapter is missing: {adapter}")
        result = [sys.executable, str(adapter), "status", "--scope", scope]
        if offline:
            result.append("--offline")
        return result

    @staticmethod
    def sync_action(command: str, scope: str) -> list[str]:
        allowed = {"status", "push", "pull", "sync", "init", "history", "doctor"}
        if command not in allowed:
            raise ValueError("unsupported config-sync action")
        return ["config-sync", command, "--scope", scope]

    @staticmethod
    def privileged(operation: str, *arguments: str) -> list[str]:
        allowed = {"refresh", "clean", "optimize", "rollback", "switch"}
        if operation not in allowed:
            raise ValueError("unsupported privileged operation")
        pkexec = shutil.which("pkexec")
        helper = os.environ.get("NIX_SETTINGS_HELPER") or shutil.which("nix-settings-helper")
        if pkexec is None:
            raise ProcessError("pkexec is unavailable; install and enable Polkit")
        if helper is None:
            raise ProcessError("the restricted Nix Settings helper is unavailable")
        return [pkexec, helper, operation, *arguments]
