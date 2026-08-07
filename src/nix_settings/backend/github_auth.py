from __future__ import annotations

import errno
import os
import pty
import re
import selectors
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

DEVICE_LOGIN_URL = "https://github.com/login/device"
_DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True, slots=True)
class AuthStatus:
    installed: bool
    authenticated: bool
    login: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LoginEvent:
    message: str
    code: str | None = None
    url: str | None = None


LoginSink = Callable[[LoginEvent], None]


def clean_output(value: str) -> str:
    return _ANSI_ESCAPE.sub("", value).strip()


def extract_device_code(value: str) -> str | None:
    match = _DEVICE_CODE.search(clean_output(value))
    return match.group(0) if match is not None else None


class GitHubCliAuth:
    def status(self) -> AuthStatus:
        if shutil.which("gh") is None:
            return AuthStatus(False, False, error="GitHub CLI (gh) is not installed")
        result = subprocess.run(
            ["gh", "auth", "status", "--hostname", "github.com"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if result.returncode != 0:
            detail = clean_output(result.stderr or result.stdout)
            return AuthStatus(True, False, error=detail or "Not signed in to GitHub")
        login_result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        login = clean_output(login_result.stdout) if login_result.returncode == 0 else None
        return AuthStatus(True, True, login=login or None)

    def login(
        self,
        *,
        sink: LoginSink,
        browser_command: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> AuthStatus:
        if shutil.which("gh") is None:
            return AuthStatus(False, False, error="GitHub CLI (gh) is not installed")
        environment = os.environ.copy()
        if browser_command is not None:
            environment["GH_BROWSER"] = browser_command

        master_fd, slave_fd = pty.openpty()
        try:
            try:
                process = subprocess.Popen(
                    self.login_args(),
                    env=environment,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    start_new_session=True,
                )
            except Exception:
                os.close(master_fd)
                raise
        finally:
            os.close(slave_fd)

        # gh's web flow currently prompts to configure Git credentials and then
        # to continue with browser authentication. Accept both supported defaults.
        os.write(master_fd, b"\n\n")
        output: list[str] = []
        pending = ""
        deadline = time.monotonic() + 900
        selector = selectors.DefaultSelector()
        selector.register(master_fd, selectors.EVENT_READ)
        try:
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    self._terminate(process)
                    return AuthStatus(True, False, error="GitHub login cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    return AuthStatus(True, False, error="GitHub login timed out")
                if selector.select(timeout=min(0.25, remaining)):
                    pending = self._read(master_fd, output, pending, sink)

            while True:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                pending = self._consume(chunk, output, pending, sink)
        finally:
            selector.close()
            os.close(master_fd)

        if pending.strip():
            self._emit(sink, pending)
        returncode = process.wait()
        if returncode != 0:
            detail = clean_output("".join(output)) or f"gh exited with {returncode}"
            return AuthStatus(True, False, error=detail)

        setup = subprocess.run(
            ["gh", "auth", "setup-git", "--hostname", "github.com"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if setup.returncode != 0:
            detail = clean_output(setup.stderr or setup.stdout)
            return AuthStatus(True, False, error=detail or "Git credential setup failed")
        return self.status()

    @staticmethod
    def login_args() -> list[str]:
        return [
            "gh",
            "auth",
            "login",
            "--hostname",
            "github.com",
            "--web",
            "--git-protocol",
            "https",
        ]

    @classmethod
    def _read(
        cls,
        master_fd: int,
        output: list[str],
        pending: str,
        sink: LoginSink,
    ) -> str:
        try:
            chunk = os.read(master_fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return pending
            raise
        return cls._consume(chunk, output, pending, sink)

    @classmethod
    def _consume(
        cls,
        chunk: bytes,
        output: list[str],
        pending: str,
        sink: LoginSink,
    ) -> str:
        text = chunk.decode("utf-8", errors="replace")
        output.append(text)
        pending += text.replace("\r", "\n")
        lines = pending.split("\n")
        pending = lines.pop()
        for line in lines:
            cls._emit(sink, line)
        return pending

    @staticmethod
    def _emit(sink: LoginSink, line: str) -> None:
        message = clean_output(line)
        if not message:
            return
        code = extract_device_code(message)
        sink(LoginEvent(message=message, code=code, url=DEVICE_LOGIN_URL if code else None))

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
