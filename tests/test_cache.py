from pathlib import Path

from nix_settings.backend.cache import JsonCache


def test_json_cache_round_trip(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    payload = {"host": "nyx", "diskUsedPercent": 66, "errors": []}
    cache.save("system-status", payload)
    assert cache.load("system-status") == payload


def test_json_cache_ignores_corruption(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "system-status.json").write_text("not-json", encoding="utf-8")
    assert cache.load("system-status") is None
