# Nix Settings

[![CI](https://github.com/madebycli/nix-settings/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/madebycli/nix-settings/actions/workflows/ci.yml)
[![Nixpkgs update](https://github.com/madebycli/nix-settings/actions/workflows/update-nixpkgs.yml/badge.svg?branch=main)](https://github.com/madebycli/nix-settings/actions/workflows/update-nixpkgs.yml)

A GTK3 + GtkLayerShell NixOS system-management surface. The application keeps one fixed layer-shell window and adds an Overview dashboard around the existing Sound Center.

## Commands

```bash
nix-settings                 # Overview
nix-settings overview
nix-settings sound           # Existing Sound Center directly
nix-settings updates
nix-settings sync
nix-settings system
nix-settings generations
nix-settings storage
nix-settings doctor
```

`SoundPage` remains the existing implementation. Output/Input, Playback/Recording, independent scrolling, route geometry and volume interaction are not replaced by the system-management views.

## Install into a profile

```bash
nix profile add github:madebycli/nix-settings#nix-settings
```

This installs the application, desktop entry and restricted helper payload. Read-only pages work when the required `nix-config` commands are installed. Privileged actions additionally require the Polkit policy to be activated system-wide through the NixOS module.

## NixOS module and Polkit

Add the Flake input:

```nix
{
  inputs.nix-settings.url = "github:madebycli/nix-settings";
  inputs.nix-settings.inputs.nixpkgs.follows = "nixpkgs";
}
```

Enable the module:

```nix
{ inputs, ... }:
{
  imports = [ inputs.nix-settings.nixosModules.default ];
  programs.nix-settings.enable = true;
}
```

The module installs the package, enables Polkit and activates the policy for the packaged restricted helper. Authentication is displayed by the desktop's existing Polkit agent. Nix Settings never reads a password and does not fall back to a terminal password prompt.

The helper accepts only these operations:

- refresh with one documented Nix Refresh mode;
- build/switch with a validated repository and profile;
- cleanup with a bounded rollback-generation count;
- store optimization;
- rollback.

It does not accept arbitrary commands or shell fragments.

## Backend contract

The GUI consumes machine-readable interfaces supplied by `madebycli/nix-config`:

```bash
nix-status --json
nix-status --online --json
nix-updates all --json
nix-generations --json
nix-clean --dry-run 5 --json
```

Config Sync uses the read-only `scripts/config-sync-json.py` adapter and the existing `config-sync` command for actions. The adapter imports the existing checksum, manifest, Secret, state and conflict code rather than parsing terminal tables.

Update previews run in temporary repository/profile copies. They do not modify the real `flake.lock` or personal profile. A detailed closure build is only performed when explicitly selected.

## Window and layout

The complete outer frame is created before slow backend work starts. Its logical size is calculated once from the GDK monitor workarea and remains frozen for the process lifetime. Every view scrolls internally.

The 1920×1080 reference remains 1480×900 logical pixels. Automated geometry tests also cover 1280×720, 1366×768, 2560×1440, 3840×2160 and a reduced logical HiDPI workarea.

The shared theme is based on the existing Nix Settings Sound Center and GitHub Backup Deck: transparent near-black root, native GTK foreground/accent colors, mono typography, stable cards, round close button and native read-only log views.

## Config Sync

The Config Sync view supports Status, Upload, Download, Synchronize, Initialize, History and Doctor with All, NixOS and Dotfiles scopes. Download and Synchronize keep the existing fast-forward and conflict rules. Conflicts are surfaced and are never resolved by date.

Managed paths edit the existing `sync/paths.conf` and `sync/excludes.conf`. Changes are normalized, checked for unsafe paths and common secret/session/key patterns, shown as a unified diff, then written atomically.

## Cleanup and storage

Cleanup always requests a structured dry-run first. The backend and privileged helper independently verify the running generation, boot default, latest generation and bounded keep count before deletion. Optimize is a separate action and never removes generations.

## Development

```bash
python -m compileall -q src
pytest -q
ruff check .
mypy src
nix flake check --no-write-lock-file --print-build-logs
nix build .#nix-settings
```

Pure Python tests do not perform updates, generation deletion or Git pushes. Real Wayland layer-shell behavior, desktop Polkit authentication and NixOS switch/cleanup operations must be validated manually before merge.
