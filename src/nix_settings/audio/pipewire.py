from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from nix_settings.audio.models import AudioDevice, AudioDirection, AudioSnapshot, AudioStream


class PipeWireParseError(ValueError):
    """Raised for malformed pw-dump data."""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _props(item: Mapping[str, Any]) -> Mapping[str, Any]:
    info = _mapping(item.get("info"))
    props = dict(_mapping(info.get("props")))
    props.update(_mapping(item.get("props")))
    return props


def _first(props: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = props.get(key)
        if value not in (None, ""):
            return value
    return None


def _text(props: Mapping[str, Any], *keys: str, fallback: str = "Unknown") -> str:
    value = _first(props, *keys)
    return str(value) if value is not None else fallback


def _find_named_values(value: object, wanted: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in wanted:
                found.append(nested)
            found.extend(_find_named_values(nested, wanted))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_find_named_values(nested, wanted))
    return found


def _coerce_volume(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return max(0.0, min(1.0, number))
    if isinstance(value, list):
        channels = [float(v) for v in value if isinstance(v, (int, float))]
        if channels:
            return max(0.0, min(1.0, sum(channels) / len(channels)))
    if isinstance(value, Mapping):
        for key in ("volume", "value", "channelVolumes"):
            result = _coerce_volume(value.get(key))
            if result is not None:
                return result
    return None


def _volume(item: Mapping[str, Any], props: Mapping[str, Any]) -> float:
    direct = _coerce_volume(_first(props, "volume", "node.volume", "audio.volume"))
    if direct is not None:
        return direct
    candidates = _find_named_values(item, {"channelVolumes", "volume"})
    for candidate in candidates:
        result = _coerce_volume(candidate)
        if result is not None:
            return result
    return 1.0


def _muted(item: Mapping[str, Any], props: Mapping[str, Any]) -> bool:
    direct = _first(props, "mute", "node.mute", "audio.mute")
    if isinstance(direct, bool):
        return direct
    if isinstance(direct, (int, str)):
        return str(direct).lower() in {"1", "true", "yes", "on"}
    for candidate in _find_named_values(item, {"mute", "muted"}):
        if isinstance(candidate, bool):
            return candidate
    return False


def _string_tuple(item: Mapping[str, Any], keys: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in _find_named_values(item, keys):
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, Mapping):
            name = _first(value, "name", "description", "port", "profile")
            if name is not None:
                result.append(str(name))
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    result.append(entry)
                elif isinstance(entry, Mapping):
                    name = _first(entry, "name", "description", "port", "profile")
                    if name is not None:
                        result.append(str(name))
    return tuple(dict.fromkeys(result))


def _active_name(item: Mapping[str, Any], props: Mapping[str, Any], *keys: str) -> str | None:
    value = _first(props, *keys)
    if value is not None:
        return str(value)
    values = _find_named_values(item, set(keys))
    for candidate in values:
        if isinstance(candidate, str):
            return candidate
        if isinstance(candidate, Mapping):
            name = _first(candidate, "name", "description")
            if name is not None:
                return str(name)
    return None


def _metadata_defaults(items: Iterable[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    sink_name: str | None = None
    source_name: str | None = None
    sink_keys = {"default.audio.sink", "default.configured.audio.sink"}
    source_keys = {"default.audio.source", "default.configured.audio.source"}
    for item in items:
        if item.get("type") != "PipeWire:Interface:Metadata":
            continue
        entries: list[object] = []
        metadata = item.get("metadata")
        if isinstance(metadata, list):
            entries.extend(metadata)
        elif isinstance(metadata, Mapping):
            entries.extend(metadata.values())
        info_metadata = _mapping(item.get("info")).get("metadata")
        if isinstance(info_metadata, list):
            entries.extend(info_metadata)
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            key = str(entry.get("key", ""))
            raw = entry.get("value")
            try:
                parsed: object = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                parsed = raw
            name = parsed.get("name") if isinstance(parsed, Mapping) else parsed
            if key in sink_keys and name:
                sink_name = str(name)
            elif key in source_keys and name:
                source_name = str(name)
    return sink_name, source_name


def _link_routes(items: Iterable[Mapping[str, Any]]) -> tuple[dict[int, int], dict[int, int]]:
    outgoing: dict[int, int] = {}
    incoming: dict[int, int] = {}
    for item in items:
        if item.get("type") != "PipeWire:Interface:Link":
            continue
        props = _props(item)
        output_node = _first(props, "link.output.node", "output.node")
        input_node = _first(props, "link.input.node", "input.node")
        try:
            output_id = int(output_node)
            input_id = int(input_node)
        except (TypeError, ValueError):
            continue
        outgoing[output_id] = input_id
        incoming[input_id] = output_id
    return outgoing, incoming


def _linked_device_id(item: Mapping[str, Any], props: Mapping[str, Any]) -> int | None:
    value = _first(
        props,
        "target.object",
        "node.target",
        "object.target",
        "device.id",
        "target.id",
    )
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def parse_pw_dump(payload: str | bytes | list[object]) -> AudioSnapshot:
    try:
        raw: object = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PipeWireParseError("pw-dump returned malformed JSON") from exc
    if not isinstance(raw, list):
        raise PipeWireParseError("pw-dump root must be a JSON array")
    items = [item for item in raw if isinstance(item, Mapping)]
    default_sink_name, default_source_name = _metadata_defaults(items)
    outgoing_links, incoming_links = _link_routes(items)
    outputs: list[AudioDevice] = []
    inputs: list[AudioDevice] = []
    playback: list[AudioStream] = []
    recording: list[AudioStream] = []

    for item in items:
        if item.get("type") != "PipeWire:Interface:Node":
            continue
        props = _props(item)
        media_class = _text(props, "media.class", fallback="")
        node_id = item.get("id")
        if not isinstance(node_id, int):
            continue
        name = _text(props, "node.name", "object.path", fallback=f"node-{node_id}")
        description = _text(
            props,
            "node.description",
            "device.description",
            "node.nick",
            fallback=name,
        )
        volume = _volume(item, props)
        muted = _muted(item, props)

        if media_class in {"Audio/Sink", "Audio/Source"}:
            direction = (
                AudioDirection.OUTPUT if media_class == "Audio/Sink" else AudioDirection.INPUT
            )
            default_name = default_sink_name if direction is AudioDirection.OUTPUT else default_source_name
            device = AudioDevice(
                id=node_id,
                name=name,
                description=description,
                direction=direction,
                is_default=default_name in {name, description},
                is_muted=muted,
                volume=volume,
                ports=_string_tuple(item, {"ports", "EnumRoute", "route"}),
                active_port=_active_name(item, props, "active.port", "port.name", "route.name"),
                profiles=_string_tuple(item, {"profiles", "EnumProfile", "profile"}),
                active_profile=_active_name(
                    item, props, "active.profile", "device.profile.name", "profile.name"
                ),
            )
            (outputs if direction is AudioDirection.OUTPUT else inputs).append(device)
            continue

        if media_class not in {"Stream/Output/Audio", "Stream/Input/Audio"}:
            continue
        direction = (
            AudioDirection.PLAYBACK
            if media_class == "Stream/Output/Audio"
            else AudioDirection.RECORDING
        )
        writable = bool(
            _first(props, "volume.writable", "node.volume.writable", "audio.volume.writable")
        )
        stream = AudioStream(
            id=node_id,
            application_name=_text(
                props,
                "application.name",
                "application.process.binary",
                "client.name",
                fallback="Unknown application",
            ),
            application_icon=(
                str(icon)
                if (icon := _first(props, "application.icon-name", "application.icon"))
                else None
            ),
            media_name=(
                str(media)
                if (media := _first(props, "media.name", "node.description"))
                else None
            ),
            direction=direction,
            device_id=(
                _linked_device_id(item, props)
                or (outgoing_links.get(node_id) if direction is AudioDirection.PLAYBACK else None)
                or (incoming_links.get(node_id) if direction is AudioDirection.RECORDING else None)
            ),
            is_muted=muted,
            volume=volume,
            volume_is_writable=writable or direction is AudioDirection.PLAYBACK,
            is_active=str(_first(props, "node.state", "state") or "running").lower()
            not in {"idle", "suspended", "error"},
        )
        (playback if direction is AudioDirection.PLAYBACK else recording).append(stream)

    default_output_id = next((device.id for device in outputs if device.is_default), None)
    default_input_id = next((device.id for device in inputs if device.is_default), None)
    outputs.sort(key=lambda device: (not device.is_default, device.description.casefold()))
    inputs.sort(key=lambda device: (not device.is_default, device.description.casefold()))
    playback.sort(key=lambda stream: (stream.application_name.casefold(), stream.id))
    recording.sort(key=lambda stream: (stream.application_name.casefold(), stream.id))
    return AudioSnapshot(
        outputs=tuple(outputs),
        inputs=tuple(inputs),
        playback_streams=tuple(playback),
        recording_streams=tuple(recording),
        default_output_id=default_output_id,
        default_input_id=default_input_id,
        timestamp=datetime.now(UTC),
    )
