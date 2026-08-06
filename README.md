# Nix Settings

A GTK3 + GtkLayerShell sound center for NixOS.

## Run

```bash
nix run github:madebycli/nix-settings -- sound
```

Check the runtime first with:

```bash
nix run github:madebycli/nix-settings -- doctor
```

The graphical interface requires a Wayland compositor with layer-shell support, PipeWire, WirePlumber, `wpctl`, and `pw-dump`.

## Sound layout

The Sound center uses a fixed 2×2 workspace:

- Output | Input
- Playback | Recording

Playback and Recording scroll independently. Application rows keep a stable two-line geometry: application identity and Route on the first line, then Volume, percentage, and Mute on the second line.

On normal desktop and 15-inch monitor sizes, every stream Route selector uses the same fixed 300 logical-pixel width as the LibreWolf reference row. Short application names cannot stretch it. On genuinely narrow monitors, the selector is reduced from the available panel width so the application identity and Route controls do not overlap.

## Keyboard

- `Esc`: close
- `Ctrl+R`: refresh
- `Ctrl+Q`: quit

## Development

```bash
nix develop
pytest -q
ruff check .
mypy src
```

The application deliberately has no floating-window fallback. Failure to initialize GtkLayerShell is treated as a startup error.
