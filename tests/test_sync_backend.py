import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from nix_settings.backend import process
from nix_settings.backend.process import BackendCommands


def test_sync_status_uses_packaged_contract_not_checkout_adapter() -> None:
    command = BackendCommands.sync_status("all")
    assert command == ["config-sync", "status", "--json", "--scope", "all"]
    assert "config-sync-json.py" not in " ".join(command)


def test_sync_conflict_policy_is_passed_as_fixed_argv() -> None:
    assert BackendCommands.sync_action("push", "all", conflict_policy="local") == [
        "config-sync",
        "push",
        "--scope",
        "all",
        "--conflict-policy",
        "local",
    ]
    assert BackendCommands.sync_action("sync", "dotfiles", conflict_policy="repository")[-2:] == [
        "--conflict-policy",
        "repository",
    ]
    with pytest.raises(ValueError):
        BackendCommands.sync_action("doctor", "all", conflict_policy="local")


def test_privileged_prefers_nixos_pkexec_wrapper() -> None:
    with tempfile.TemporaryDirectory() as directory:
        wrapper = Path(directory) / "pkexec"
        wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        wrapper.chmod(0o755)
        with (
            mock.patch.object(process, "SYSTEM_PKEXEC", wrapper),
            mock.patch.dict(
                os.environ,
                {"NIX_SETTINGS_HELPER": "/nix/store/test-helper"},
                clear=False,
            ),
            mock.patch.object(
                process.shutil,
                "which",
                return_value="/nix/store/wrong-pkexec",
            ),
        ):
            argv = BackendCommands.privileged("clean", "3")
    assert argv[0] == str(wrapper)
    assert "/nix/store/wrong-pkexec" not in argv
