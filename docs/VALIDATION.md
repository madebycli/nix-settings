# Validation (2026-10-21)

Verified locally in the managed Linux environment:

- Rust unit tests, rustfmt and Clippy with warnings denied.
- Real isolated PulseAudio 17: graph parsing, exclusion of monitor sources, master volume/mute/default, real playback and recording stream routing, recording volume, server restart/reconnect, signal shutdown/socket removal.
- Real installer in temporary XDG directories: preservation of existing config and enabled plugins, original settings backup, repeat installs, no bar widget, help without mutation and malformed-settings preservation.
- Native Luau callback execution/property checks against unmodified Noctalia 5.3.0 sources (`e37d7145b95a51b801db9bb20d1c600f35111e0b`), including 1366×768, 1280×720, 800×600, 640×360 and 3840×2160 logical outputs, UI scaling, square/round corners and glass/soft cards. Luau scripts compile.

The isolated null-device audio run produced its first snapshot in about 25 ms with a debug binary; this is one test observation, not a hardware/startup performance guarantee.

The x86_64 Nix package build, packaged CLI and complete `nix flake check` (including official Noctalia plugin lint) passed locally. Both native plugins also loaded in unmodified Noctalia 5.3.0 under software-rendered Sway. The combined host runner exercised live palette/shape/border/transparency/UI-scale changes, native Sound backend startup and audio control, and native overlays at 800×600 and 1366×768 with 125% UI scaling. Screenshots remain in the execution workspace, outside the source repositories.

An already open panel retains a safe size when a monitor grows; closing and reopening negotiates the larger host surface. Scroll viewports receive exact remaining height through native flex layout, so content stays within the panel.

PipeWire-Pulse on the user's machine, physical device hotplug, a physical 15-inch monitor and GPU-backed MangoWM remain unverified. The Sway/Noctalia tests do not establish target-hardware acceptance. Runtime prerequisites and installation commands are in README.md.
