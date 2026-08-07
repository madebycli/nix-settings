from __future__ import annotations

from pathlib import Path

from nix_settings.backend.github_auth import GitHubCliAuth, extract_device_code
from nix_settings.backend.models import GitHubSyncStatus, SyncStatus
from nix_settings.gui.pages.sync import sync_action_enabled

ROOT = Path(__file__).resolve().parents[1]


def github_status(**overrides: object) -> GitHubSyncStatus:
    values: dict[str, object] = {
        "gh_installed": True,
        "authenticated": True,
        "login": "madebycli",
        "permission": "ADMIN",
        "can_push": True,
        "remote_url": "https://github.com/madebycli/nix-config.git",
        "remote_ok": True,
        "git_name": "madebycli",
        "git_email": "example@users.noreply.github.com",
        "credential_helper_ready": True,
        "error": None,
    }
    values.update(overrides)
    return GitHubSyncStatus(**values)  # type: ignore[arg-type]


def test_browser_login_uses_supported_gh_web_flow() -> None:
    assert GitHubCliAuth.login_args() == [
        "gh",
        "auth",
        "login",
        "--hostname",
        "github.com",
        "--web",
        "--git-protocol",
        "https",
    ]


def test_device_code_is_extracted_from_gh_output() -> None:
    assert extract_device_code("First copy ABCD-1234 and continue") == "ABCD-1234"
    assert extract_device_code("No code here") is None


def test_sync_contract_remains_backward_compatible_without_github_block() -> None:
    status = SyncStatus.from_json(
        {
            "repositoryPath": "/tmp/nix-config",
            "profile": "nyx",
            "scope": "all",
            "branch": "main",
            "ahead": 0,
            "behind": 0,
            "dirty": False,
            "lastSync": None,
            "localChanges": [],
            "stagedChanges": [],
            "changes": {"local": [], "remote": [], "same": [], "conflicts": []},
            "plannedAction": "none",
            "backups": [],
            "errors": [],
        }
    )
    assert not status.github.gh_installed
    assert not status.github.authenticated
    assert not status.github.can_push


def test_upload_and_sync_require_authenticated_write_access() -> None:
    ready = github_status()
    signed_out = github_status(authenticated=False, can_push=False)
    read_only = github_status(permission="READ", can_push=False)

    assert sync_action_enabled("push", ready)
    assert sync_action_enabled("sync", ready)
    assert not sync_action_enabled("push", signed_out)
    assert not sync_action_enabled("sync", read_only)
    assert sync_action_enabled("pull", signed_out)
    assert sync_action_enabled("doctor", signed_out)


def test_nix_package_runtime_contains_github_cli() -> None:
    package = (ROOT / "nix/package.nix").read_text(encoding="utf-8")
    assert "  gh," in package
    assert "    gh\n    git\n" in package
