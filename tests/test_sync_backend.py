from nix_settings.backend.process import BackendCommands


def test_sync_status_uses_packaged_contract_not_checkout_adapter() -> None:
    command = BackendCommands.sync_status("all")
    assert command == ["config-sync", "status", "--json", "--scope", "all"]
    assert "config-sync-json.py" not in " ".join(command)
