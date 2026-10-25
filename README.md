# Nix Sound

A focused sound center: an event-driven Rust backend and a genuine Noctalia overlay. No GTK, Qt, Python runtime, settings sidebar, or unfinished system-management pages.

## Install

```sh
nix profile add github:madebycli/nix-settings#nix-settings
nix-settings install-plugin
nix-settings sound
```

`install-plugin` installs and enables the local `madebycli/nix-sound` plugin without adding a bar widget. Existing Noctalia configuration and plugin enablement are retained. Changed settings and previously installed plugin files are backed up. The executable path is stored in the plugin, including the Nix wrapper that supplies audio utilities. Nix installs also keep an indirect GC root in `$XDG_STATE_HOME/nix-sound/engine`, so an engine installed from a temporary `nix run` remains available.

Noctalia **5.2+ / API 31**, a Wayland session and a Pulse-compatible server are required. On NixOS use PipeWire with `services.pipewire.pulse.enable = true`. The package supplies `pactl`; it does not start a second audio server. After an update, run `nix-settings install-plugin` again; the installer reloads the local plugin in a running Noctalia session and repairs stale generated engine paths. If the backend exits while the panel is open, the panel reports the error and reconnects automatically.

```sh
nix profile upgrade --all --refresh
nix-settings install-plugin
nix-settings doctor
```

## Appearance and layout

Noctalia owns the panel, native controls, palette, font, accessibility scaling, shadows, animations and effects. The plugin reads effective settings for custom section corners, borders and card opacity; it never generates colors from a wallpaper. Theme changes apply live.

The large system-output and microphone controls sit above their application lists. Device labels are shown without a separate technical profile/fallback row. Playback is on the left, recording on the right; their lists scroll independently. Below 760 content pixels the overlay switches to one scrollable column. Logical monitor dimensions and Noctalia UI scaling determine the available space. The host additionally clamps panel surfaces to its output; no physical monitor diagonal is assumed. An open panel keeps a safe extent after monitor enlargement and negotiates the larger size on reopening.

Open from a launcher or key binding with `nix-settings sound`, or directly:

```sh
noctalia msg panel-toggle madebycli/nix-sound:sound
```

Escape and outside click use Noctalia's normal dismissal behavior.

## Audio engine

One subscription receives audio-server events. A debounced graph refresh uses two structured JSON calls regardless of the number of streams; there is no per-device polling. Slider changes are committed on release. Installation also reloads the local plugin in a running Noctalia session so updated scripts and panel dimensions take effect. The centered overlay is capped at 1600 × 900 logical pixels before Noctalia UI scaling and clamps to smaller monitors; compact application cards retain their logos and switch to one scrollable column on narrow screens. Output/input defaults, mute, volume and routing for both playback and recording use supported Pulse server commands. Server restarts reconnect automatically. Every recording stream remains independently controllable.

The backend starts on first open and remains idle between events. IPC uses a private, bounded Unix-socket protocol with typed requests, command deadlines and single-instance locking. Closing Noctalia stops its child backend and audio subscription. The plugin detects backend launch failures and unexpected exits, shows a reconnect action and retries with bounded backoff; while healthy it does not poll audio or spawn a timer subprocess. The overlay checks monitor and appearance changes once per second and compares only the settings that affect its layout, keeping within Noctalia's short plugin callback budget.

## Nix modules

Both `nixosModules.default` and `homeManagerModules.default` retain `programs.nix-settings.enable`. The package and `noctalia-plugin` Flake outputs are available for x86_64 and aarch64 Linux. Run `nix-settings install-plugin` as the desktop user after installing the package.

## Development and checks

```sh
cargo fmt --check
cargo clippy --all-targets --locked -- -D warnings
cargo test --locked
cargo build --locked
python3 tools/install_acceptance.py
python3 tools/audio_acceptance.py
nix flake check --no-write-lock-file
```

The audio acceptance tool needs `pulseaudio` and `pulseaudio-utils` and starts an isolated server with null devices. It checks real master controls, playback/recording routing, reconnect and shutdown. `tools/plugin_contract.py --noctalia-source /path/to/noctalia` executes native Luau callbacks against upstream property definitions and checks monitor/scale/theme cases; it requires `luau`.

See `docs/VALIDATION.md` for verified scope and limitations. The former GTK application and broader settings experiments are preserved in `backup/before-noctalia-sound-20261021`, `backup/system-management-shell`, `backup/github-cli-sync-ui` and `backup/initial-sound`.
