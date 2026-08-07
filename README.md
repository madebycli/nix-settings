# Nix Settings

A GTK3 + GtkLayerShell sound center for NixOS.

## Run directly

```bash
nix run github:madebycli/nix-settings#nix-settings -- sound
```

Check the runtime first with:

```bash
nix run github:madebycli/nix-settings#nix-settings -- doctor
```

The graphical interface requires a Wayland compositor with layer-shell support, PipeWire, WirePlumber, `wpctl`, and `pw-dump`.

## Install into a Nix profile

```bash
nix profile add github:madebycli/nix-settings#nix-settings
```

Refresh this and every other unlocked profile entry:

```bash
nix profile upgrade --all --refresh
```

The profile stores the unlocked GitHub reference. A normal source commit to `main` is therefore available through the next profile upgrade even when the visible application version has not changed. No edit to `flake.nix`, `nix/package.nix`, or `flake.lock` is required for an ordinary application-code change.

## NixOS module

Add the repository as a direct Flake input:

```nix
{
  inputs.nix-settings.url = "github:madebycli/nix-settings";
  inputs.nix-settings.inputs.nixpkgs.follows = "nixpkgs";
}
```

Import and enable the module:

```nix
{ inputs, ... }:
{
  imports = [ inputs.nix-settings.nixosModules.default ];
  programs.nix-settings.enable = true;
}
```

## Home Manager module

```nix
{ inputs, ... }:
{
  imports = [ inputs.nix-settings.homeManagerModules.default ];
  programs.nix-settings.enable = true;
}
```

## Automatic dependency updates

The committed `flake.lock` keeps installations reproducible. The **Update Nixpkgs input** workflow:

- runs once per day;
- is manually startable with **Run workflow**;
- updates only the `nixpkgs` input to the current `nixos-unstable` revision;
- evaluates the Flake, runs every check, and builds Nix Settings;
- commits the new lock file only after validation succeeds.

A future install therefore uses the newest dependency set that this repository has successfully validated, rather than remaining permanently fixed to today's Nixpkgs revision.

## Version source

`src/nix_settings/version.py` is the single application-version source. Python packaging and Nix derive their version from it. Ordinary source changes do not require a version bump.

## Continuous integration

Every push to `main` and every pull request verifies:

- that `flake.lock` is present and synchronized;
- Flake evaluation and all checks;
- the complete `nix-settings` package build;
- the exact public direct-install command `nix profile add github:madebycli/nix-settings#nix-settings`.

## Sound layout

The Sound center uses a fixed 2×2 workspace:

- Output | Input
- Playback | Recording

Playback and Recording scroll independently. Application rows keep a stable two-line geometry: application identity and Route on the first line, then Volume, percentage, and Mute on the second line.

Starting with version 0.2.7, every stream Route selector uses the same fixed 300 logical-pixel width as the LibreWolf reference row on normal desktop and 15-inch monitor sizes. Short application names cannot stretch it. On genuinely narrow monitors, the selector is reduced from the available panel width so the application identity and Route controls do not overlap.

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
nix flake check --no-write-lock-file --print-build-logs
```

The application deliberately has no floating-window fallback. Failure to initialize GtkLayerShell is treated as a startup error.
