from pathlib import Path

process_path = Path("src/nix_settings/backend/process.py")
process = process_path.read_text(encoding="utf-8")

if "def resolve_pkexec()" not in process:
    anchor = "\n\nclass BackendCommands:\n"
    helper = r'''

SYSTEM_PKEXEC = Path("/run/wrappers/bin/pkexec")


def resolve_pkexec() -> str | None:
    """Prefer the NixOS setuid wrapper over an immutable-store pkexec on PATH."""
    if SYSTEM_PKEXEC.is_file() and os.access(SYSTEM_PKEXEC, os.X_OK):
        return str(SYSTEM_PKEXEC)
    return shutil.which("pkexec")
'''
    if anchor not in process:
        raise SystemExit("BackendCommands anchor missing")
    process = process.replace(anchor, helper + anchor, 1)

old_sync_action = '''    @staticmethod
    def sync_action(command: str, scope: str) -> list[str]:
        allowed = {"status", "push", "pull", "sync", "init", "history", "doctor"}
        if command not in allowed:
            raise ValueError("unsupported config-sync action")
        return ["config-sync", command, "--scope", scope]
'''
new_sync_action = '''    @staticmethod
    def sync_action(
        command: str,
        scope: str,
        *,
        conflict_policy: str | None = None,
    ) -> list[str]:
        allowed = {"status", "push", "pull", "sync", "init", "history", "doctor"}
        if command not in allowed:
            raise ValueError("unsupported config-sync action")
        result = ["config-sync", command, "--scope", scope]
        if conflict_policy is not None:
            if command not in {"push", "pull", "sync"}:
                raise ValueError("conflict policy is only valid for sync operations")
            if conflict_policy not in {"local", "repository"}:
                raise ValueError("unsupported conflict policy")
            result.extend(["--conflict-policy", conflict_policy])
        return result
'''
if old_sync_action in process:
    process = process.replace(old_sync_action, new_sync_action, 1)
elif "conflict policy is only valid for sync operations" not in process:
    raise SystemExit("sync_action block missing")

process = process.replace('        pkexec = shutil.which("pkexec")\n', '        pkexec = resolve_pkexec()\n', 1)
if 'pkexec = resolve_pkexec()' not in process:
    raise SystemExit("pkexec resolver replacement missing")
process_path.write_text(process, encoding="utf-8")

sync_path = Path("src/nix_settings/gui/pages/sync.py")
sync = sync_path.read_text(encoding="utf-8")
old_argv = '''        scope = self.scope.get_active_id() or "all"
        argv = BackendCommands.sync_action(command, scope)
        if mutating:
'''
new_argv = '''        scope = self.scope.get_active_id() or "all"
        conflict_policy: str | None = None
        if (
            status is not None
            and status.conflicts
            and scope != "nixos"
            and command in {"push", "pull", "sync"}
        ):
            conflict_policy = self._choose_conflict_policy(command, status.conflicts)
            if conflict_policy is None:
                return
        argv = BackendCommands.sync_action(
            command,
            scope,
            conflict_policy=conflict_policy,
        )
        if mutating:
'''
if old_argv in sync:
    sync = sync.replace(old_argv, new_argv, 1)
elif "self._choose_conflict_policy(command, status.conflicts)" not in sync:
    raise SystemExit("sync argv block missing")

if "def _choose_conflict_policy(" not in sync:
    anchor = "\n    def _confirm_action(self, command: str) -> bool:\n"
    method = r'''
    def _choose_conflict_policy(self, command: str, conflicts: tuple[str, ...]) -> str | None:
        visible = list(conflicts[:8])
        details = "\n".join(f"• {path}" for path in visible)
        if len(conflicts) > len(visible):
            details += f"\n• … and {len(conflicts) - len(visible)} more"

        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.WARNING,
            buttons=self.Gtk.ButtonsType.NONE,
            text=f"{len(conflicts)} dotfile conflict(s) need an explicit choice",
        )
        dialog.add_button("Cancel", self.Gtk.ResponseType.CANCEL)
        if command in {"push", "sync"}:
            dialog.add_button("Use local", 101)
        if command in {"pull", "sync"}:
            dialog.add_button("Use repository", 102)

        if command == "push":
            explanation = (
                "Upload will copy the local HOME versions into the repository and continue. "
                "Git history keeps the previous repository versions."
            )
        elif command == "pull":
            explanation = (
                "Download will replace these local HOME versions from the repository and create "
                "timestamped local backups first."
            )
        else:
            explanation = (
                "Choose which side wins only for the listed conflicts. Other local/remote changes "
                "continue through the normal three-way sync rules. Repository-to-HOME replacements "
                "are backed up first."
            )
        dialog.format_secondary_text(f"{explanation}\n\n{details}")
        prepare_layer_dialog(dialog)
        response = dialog.run()
        dialog.destroy()
        if response == 101:
            self.log.append("Conflict choice: use local versions")
            return "local"
        if response == 102:
            self.log.append("Conflict choice: use repository versions")
            return "repository"
        return None
'''
    if anchor not in sync:
        raise SystemExit("confirm action anchor missing")
    sync = sync.replace(anchor, "\n" + method + anchor, 1)

sync_path.write_text(sync, encoding="utf-8")

tests = Path("tests/test_sync_backend.py")
t = tests.read_text(encoding="utf-8")
if "test_privileged_prefers_nixos_pkexec_wrapper" not in t:
    t = '''import os
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
            mock.patch.dict(os.environ, {"NIX_SETTINGS_HELPER": "/nix/store/test-helper"}, clear=False),
            mock.patch.object(process.shutil, "which", return_value="/nix/store/wrong-pkexec"),
        ):
            argv = BackendCommands.privileged("clean", "3")
    assert argv[0] == str(wrapper)
    assert "/nix/store/wrong-pkexec" not in argv
'''
    tests.write_text(t, encoding="utf-8")

ui_tests = Path("tests/test_github_sync_ui.py")
u = ui_tests.read_text(encoding="utf-8")
if "test_sync_conflict_dialog_exposes_explicit_local_and_repository_choices" not in u:
    u += r'''


def test_sync_conflict_dialog_exposes_explicit_local_and_repository_choices() -> None:
    source = (ROOT / "src/nix_settings/gui/pages/sync.py").read_text(encoding="utf-8")
    assert "def _choose_conflict_policy" in source
    assert 'dialog.add_button("Use local", 101)' in source
    assert 'dialog.add_button("Use repository", 102)' in source
    assert "Conflict choice: use local versions" in source
    assert "Conflict choice: use repository versions" in source
'''
    ui_tests.write_text(u, encoding="utf-8")
