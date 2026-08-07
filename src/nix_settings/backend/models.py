from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

UPDATE_MODES: dict[str, tuple[str, ...]] = {
    "all": (
        "nixpkgs",
        "home-manager",
        "nix-cachyos-kernel",
        "mango",
        "noctalia",
        "noctalia-greeter",
        "profiles",
    ),
    "base": ("nixpkgs", "nix-cachyos-kernel", "profiles"),
    "packages": ("nixpkgs", "profiles"),
    "kernel": ("nix-cachyos-kernel",),
    "desktop": ("home-manager", "mango", "noctalia", "noctalia-greeter"),
    "profiles": ("profiles",),
}


class ContractError(ValueError):
    pass


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContractError(f"{name} must be an array")
    return value


def _string(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ContractError(f"{name} must be a string")
    return value


def _integer(value: object, name: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractError(f"{name} must be an integer")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{name} must be a boolean")
    return value


def _errors(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in _sequence(value, "errors"))


@dataclass(frozen=True)
class SystemStatus:
    host: str
    profile: str
    current_generation: int | None
    latest_generation: int | None
    generation_count: int
    store_bytes: int
    closure_bytes: int
    disk_total_bytes: int
    disk_used_bytes: int
    disk_free_bytes: int
    disk_used_percent: int
    repository_path: str
    branch: str
    dirty: bool
    ahead: int
    behind: int
    profile_package_count: int
    last_sync: str | None
    updated_at: str
    errors: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> SystemStatus:
        data = _mapping(value, "status")
        return cls(
            host=_string(data.get("host"), "host") or "",
            profile=_string(data.get("profile"), "profile") or "",
            current_generation=_integer(data.get("currentGeneration"), "currentGeneration", optional=True),
            latest_generation=_integer(data.get("latestGeneration"), "latestGeneration", optional=True),
            generation_count=_integer(data.get("generationCount"), "generationCount") or 0,
            store_bytes=_integer(data.get("storeBytes"), "storeBytes") or 0,
            closure_bytes=_integer(data.get("closureBytes"), "closureBytes") or 0,
            disk_total_bytes=_integer(data.get("diskTotalBytes"), "diskTotalBytes") or 0,
            disk_used_bytes=_integer(data.get("diskUsedBytes"), "diskUsedBytes") or 0,
            disk_free_bytes=_integer(data.get("diskFreeBytes"), "diskFreeBytes") or 0,
            disk_used_percent=_integer(data.get("diskUsedPercent"), "diskUsedPercent") or 0,
            repository_path=_string(data.get("repositoryPath"), "repositoryPath") or "",
            branch=_string(data.get("branch"), "branch") or "",
            dirty=_boolean(data.get("dirty"), "dirty"),
            ahead=_integer(data.get("ahead"), "ahead") or 0,
            behind=_integer(data.get("behind"), "behind") or 0,
            profile_package_count=_integer(data.get("profilePackageCount"), "profilePackageCount") or 0,
            last_sync=_string(data.get("lastSync"), "lastSync", optional=True),
            updated_at=_string(data.get("updatedAt"), "updatedAt") or "",
            errors=_errors(data.get("errors", [])),
        )


@dataclass(frozen=True)
class UpdateSource:
    id: str
    display_name: str
    current_revision: str
    candidate_revision: str
    current_date: str | None
    candidate_date: str | None
    update_available: bool
    status: str
    error: str | None

    @classmethod
    def from_json(cls, value: object) -> UpdateSource:
        data = _mapping(value, "source")
        return cls(
            id=_string(data.get("id"), "source.id") or "",
            display_name=_string(data.get("displayName"), "source.displayName") or "",
            current_revision=_string(data.get("currentRevision"), "source.currentRevision") or "",
            candidate_revision=_string(data.get("candidateRevision"), "source.candidateRevision") or "",
            current_date=_string(data.get("currentDate"), "source.currentDate", optional=True),
            candidate_date=_string(data.get("candidateDate"), "source.candidateDate", optional=True),
            update_available=_boolean(data.get("updateAvailable"), "source.updateAvailable"),
            status=_string(data.get("status"), "source.status") or "",
            error=_string(data.get("error"), "source.error", optional=True),
        )


@dataclass(frozen=True)
class UpdatePreview:
    mode: str
    branch: str
    ahead: int
    behind: int
    sources: tuple[UpdateSource, ...]
    profile_package_count: int
    profile_update_available: bool
    profile_summary: str
    full_closure_preview: str | None
    errors: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> UpdatePreview:
        data = _mapping(value, "updates")
        relation = _mapping(data.get("repositoryRelation") or {}, "repositoryRelation")
        profile = _mapping(data.get("profile"), "profile")
        return cls(
            mode=_string(data.get("mode"), "mode") or "",
            branch=_string(relation.get("branch", ""), "repositoryRelation.branch") or "",
            ahead=_integer(relation.get("ahead", 0), "repositoryRelation.ahead") or 0,
            behind=_integer(relation.get("behind", 0), "repositoryRelation.behind") or 0,
            sources=tuple(UpdateSource.from_json(item) for item in _sequence(data.get("sources", []), "sources")),
            profile_package_count=_integer(profile.get("packageCount"), "profile.packageCount") or 0,
            profile_update_available=_boolean(profile.get("updateAvailable"), "profile.updateAvailable"),
            profile_summary=_string(profile.get("summary"), "profile.summary") or "",
            full_closure_preview=_string(data.get("fullClosurePreview"), "fullClosurePreview", optional=True),
            errors=_errors(data.get("errors", [])),
        )

    @property
    def update_count(self) -> int:
        return sum(item.update_available for item in self.sources) + int(self.profile_update_available)


@dataclass(frozen=True)
class Generation:
    generation: int
    created_at: str | None
    status: str
    closure_path: str
    closure_bytes: int

    @classmethod
    def from_json(cls, value: object) -> Generation:
        data = _mapping(value, "generation")
        return cls(
            generation=_integer(data.get("generation"), "generation.generation") or 0,
            created_at=_string(data.get("createdAt"), "generation.createdAt", optional=True),
            status=_string(data.get("status"), "generation.status") or "",
            closure_path=_string(data.get("closurePath"), "generation.closurePath") or "",
            closure_bytes=_integer(data.get("closureBytes"), "generation.closureBytes") or 0,
        )


@dataclass(frozen=True)
class GenerationStatus:
    current_generation: int | None
    latest_generation: int | None
    generation_count: int
    generations: tuple[Generation, ...]
    errors: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> GenerationStatus:
        data = _mapping(value, "generations")
        return cls(
            current_generation=_integer(data.get("currentGeneration"), "currentGeneration", optional=True),
            latest_generation=_integer(data.get("latestGeneration"), "latestGeneration", optional=True),
            generation_count=_integer(data.get("generationCount"), "generationCount") or 0,
            generations=tuple(Generation.from_json(item) for item in _sequence(data.get("generations", []), "generations")),
            errors=_errors(data.get("errors", [])),
        )


@dataclass(frozen=True)
class SyncStatus:
    repository_path: str
    profile: str
    scope: str
    branch: str
    ahead: int
    behind: int
    dirty: bool
    last_sync: str | None
    local_changes: tuple[str, ...]
    staged_changes: tuple[str, ...]
    local: tuple[str, ...]
    remote: tuple[str, ...]
    same: tuple[str, ...]
    conflicts: tuple[str, ...]
    planned_action: str
    backups: tuple[str, ...]
    errors: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> SyncStatus:
        data = _mapping(value, "sync status")
        changes = _mapping(data.get("changes", {}), "changes")
        return cls(
            repository_path=_string(data.get("repositoryPath"), "repositoryPath") or "",
            profile=_string(data.get("profile"), "profile") or "",
            scope=_string(data.get("scope"), "scope") or "",
            branch=_string(data.get("branch"), "branch") or "",
            ahead=_integer(data.get("ahead"), "ahead") or 0,
            behind=_integer(data.get("behind"), "behind") or 0,
            dirty=_boolean(data.get("dirty"), "dirty"),
            last_sync=_string(data.get("lastSync"), "lastSync", optional=True),
            local_changes=tuple(str(item) for item in data.get("localChanges", [])),
            staged_changes=tuple(str(item) for item in data.get("stagedChanges", [])),
            local=tuple(str(item) for item in changes.get("local", [])),
            remote=tuple(str(item) for item in changes.get("remote", [])),
            same=tuple(str(item) for item in changes.get("same", [])),
            conflicts=tuple(str(item) for item in changes.get("conflicts", [])),
            planned_action=_string(data.get("plannedAction"), "plannedAction") or "",
            backups=tuple(str(item) for item in data.get("backups", [])),
            errors=_errors(data.get("errors", [])),
        )


def format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    amount = float(max(0, value))
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{value} B"


@dataclass(frozen=True)
class CleanPreview:
    safe: bool
    generation_count: int
    current_generation: int
    latest_generation: int
    keep_backups: int
    delete_generations: tuple[int, ...]
    errors: tuple[str, ...]

    @classmethod
    def from_json(cls, value: object) -> CleanPreview:
        data = _mapping(value, "cleanup preview")
        return cls(
            safe=_boolean(data.get("safe"), "safe"),
            generation_count=_integer(data.get("generationCount"), "generationCount") or 0,
            current_generation=_integer(data.get("currentGeneration"), "currentGeneration") or 0,
            latest_generation=_integer(data.get("latestGeneration"), "latestGeneration") or 0,
            keep_backups=_integer(data.get("keepBackups"), "keepBackups") or 0,
            delete_generations=tuple(int(item) for item in _sequence(data.get("deleteGenerations", []), "deleteGenerations")),
            errors=_errors(data.get("errors", [])),
        )
