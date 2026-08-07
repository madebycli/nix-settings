from __future__ import annotations

import argparse
import sys

from nix_settings.doctor import run_doctor
from nix_settings.version import __version__

PAGES = ("overview", "sound", "updates", "sync", "system", "generations", "storage")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="nix-settings",
        description="GTK3 layer-shell NixOS system management",
    )
    result.add_argument(
        "command",
        nargs="?",
        choices=(*PAGES, "doctor", "github-login"),
        help="page or command",
    )
    result.add_argument("--version", action="version", version=f"nix-settings {__version__}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "doctor":
        return run_doctor(sys.stdout)
    if args.command == "github-login":
        from nix_settings.backend.github_auth import GitHubCliAuth

        status = GitHubCliAuth().login()
        if status.authenticated:
            account = f" as {status.login}" if status.login else ""
            print(f"GitHub login complete{account}.")
            return 0
        print(status.error or "GitHub login failed", file=sys.stderr)
        return 1
    from nix_settings.app import run_gui

    return run_gui(args.command or "overview")


if __name__ == "__main__":
    raise SystemExit(main())
