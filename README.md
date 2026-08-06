# Nix Settings

Nix Settings is a focused GTK3 layer-shell sound center for NixOS, PipeWire and WirePlumber.

## Sound center

The application opens as a real Wayland layer surface. It intentionally does not fall back to a floating desktop window. The Sound command shows only the sound center: no settings sidebar and no unfinished navigation entries.

Implemented:

- fixed, monitor-bounded overlay geometry;
- exclusive keyboard focus through GTK Layer Shell;
- default output and microphone selection;
- output and microphone volume and mute controls capped at 100%;
- playback stream volume, mute and routing;
- recording stream mute and routing, with gain only when writable;
- event-driven PipeWire refresh;
- preserved scroll position during external audio changes;
- debounced sliders and monitor events;
- signal-safe selectors that do not trigger duplicate operations during initialization;
- `doctor`, `--version` and `--help` commands.

## Run

```bash
nix run github:madebycli/nix-settings -- doctor
nix run github:madebycli/nix-settings -- sound
```

A Wayland compositor with layer-shell support is required. Nix Settings exits with a clear error instead of opening a normal floating window when Wayland is unavailable.

## Development

```bash
nix develop
python -m compileall -q src
pytest -q
ruff check .
mypy src
nix flake check --print-build-logs
nix build .#nix-settings --print-build-logs
./result/bin/nix-settings doctor
./result/bin/nix-settings sound
```

## Architecture

- `audio/` owns structured PipeWire discovery and WirePlumber commands.
- `gui/` owns the GTK3 layer surface and sound widgets.
- GTK updates enter the main loop through `GLib.idle_add` and timeouts.
- subprocess calls use explicit argument arrays and `shell=False`.
- geometry and spacing live in `gui/layout.py`.
