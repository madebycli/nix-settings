# Nix Settings

Nix Settings is a native, keyboard-friendly settings application for NixOS. The first milestone provides a reusable GTK4 application shell and a functional Sound page backed by PipeWire and WirePlumber.

## Status

Implemented:

- GTK4 application shell with GTK4 Layer Shell on supported Wayland compositors
- normal GTK4 window fallback when Layer Shell or Wayland is unavailable
- single graphical instance through `Gtk.Application`
- navigation placeholders for future settings pages
- typed PipeWire device, stream and snapshot models
- default output and microphone selection
- volume and mute controls capped at 100%
- playback and recording stream routing
- per-stream controls only when the capability is writable
- event-driven `pw-dump --monitor` refresh with bounded reconnect backoff
- `doctor`, `--version` and `--help` commands
- Nix package, app, development shell, checks, NixOS module and Home Manager module

Not implemented: updates, generations, storage cleanup, network, Bluetooth management and integrations. Bluetooth audio devices still appear on the Sound page when PipeWire exposes them.

## Run

```bash
nix run .#nix-settings
nix run .#nix-settings -- sound
nix run .#nix-settings -- doctor
```

After publishing:

```bash
nix run github:madebycli/nix-settings
```

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
./result/bin/nix-settings --help
```

## Architecture

- `audio/` owns structured discovery, parsing, commands and monitoring.
- `gui/` owns layout, reusable widgets and pages; it never assembles raw PipeWire commands.
- GTK updates are dispatched through `GLib.idle_add`.
- subprocess calls use argument arrays, timeouts and `shell=False`.
- all geometry and spacing constants live in `gui/layout.py`.

## GTK baseline decision

The supplied project brief named GTK3, while the newer supplied design baseline makes GTK4 and Gtk4LayerShell mandatory for new projects. This implementation follows the newer baseline and keeps a normal GTK4 fallback for unsupported sessions.

## Runtime notes

Live level meters remain neutral unless a future backend exposes real peak data. The application does not invent activity levels or unsupported capture-gain controls.
