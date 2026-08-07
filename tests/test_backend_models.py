from nix_settings.backend.models import (
    UPDATE_MODES,
    CleanPreview,
    GenerationStatus,
    SystemStatus,
    UpdatePreview,
    format_bytes,
)


def test_status_json_parser() -> None:
    value = SystemStatus.from_json(
        {
            "host": "nyx",
            "profile": "nyx-niri",
            "currentGeneration": 42,
            "latestGeneration": 43,
            "generationCount": 7,
            "storeBytes": 100,
            "closureBytes": 50,
            "diskTotalBytes": 1000,
            "diskUsedBytes": 600,
            "diskFreeBytes": 400,
            "diskUsedPercent": 60,
            "repositoryPath": "/home/xxxxx/nyx",
            "branch": "main",
            "dirty": False,
            "ahead": 0,
            "behind": 1,
            "profilePackageCount": 3,
            "lastSync": None,
            "updatedAt": "2026-08-07T03:00:00+02:00",
            "errors": [],
        }
    )
    assert value.profile == "nyx-niri"
    assert value.disk_used_percent == 60


def test_update_modes_match_nix_config_contract() -> None:
    assert UPDATE_MODES["all"] == (
        "nixpkgs",
        "home-manager",
        "nix-cachyos-kernel",
        "mango",
        "noctalia",
        "noctalia-greeter",
        "profiles",
    )
    assert UPDATE_MODES["base"] == ("nixpkgs", "nix-cachyos-kernel", "profiles")
    assert UPDATE_MODES["packages"] == ("nixpkgs", "profiles")
    assert UPDATE_MODES["kernel"] == ("nix-cachyos-kernel",)
    assert UPDATE_MODES["desktop"] == (
        "home-manager",
        "mango",
        "noctalia",
        "noctalia-greeter",
    )
    assert UPDATE_MODES["profiles"] == ("profiles",)


def test_update_json_parser() -> None:
    value = UpdatePreview.from_json(
        {
            "mode": "kernel",
            "repositoryRelation": {"branch": "main", "ahead": 0, "behind": 0},
            "sources": [
                {
                    "id": "nix-cachyos-kernel",
                    "displayName": "Kernel/Core",
                    "currentRevision": "a",
                    "candidateRevision": "b",
                    "currentDate": None,
                    "candidateDate": None,
                    "updateAvailable": True,
                    "status": "update-available",
                    "error": None,
                }
            ],
            "profile": {"packageCount": 0, "updateAvailable": False, "summary": "not checked"},
            "fullClosurePreview": None,
            "errors": [],
        }
    )
    assert value.update_count == 1


def test_generations_and_cleanup_parsers() -> None:
    generations = GenerationStatus.from_json(
        {
            "currentGeneration": 2,
            "latestGeneration": 2,
            "generationCount": 1,
            "generations": [
                {
                    "generation": 2,
                    "createdAt": None,
                    "status": "running-and-boot",
                    "closurePath": "/nix/store/example",
                    "closureBytes": 1024,
                }
            ],
            "errors": [],
        }
    )
    cleanup = CleanPreview.from_json(
        {
            "safe": True,
            "generationCount": 6,
            "currentGeneration": 6,
            "latestGeneration": 6,
            "keepBackups": 3,
            "deleteGenerations": [1, 2],
            "errors": [],
        }
    )
    assert generations.generations[0].closure_bytes == 1024
    assert cleanup.delete_generations == (1, 2)
    assert format_bytes(1024) == "1.0 KiB"
