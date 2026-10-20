# Architecture

`src/audio.rs` normalizes one structured Pulse server graph plus default-device info and constructs validated argv operations. It uses the PipeWire-Pulse compatibility protocol through `pactl`. Unlike the old backend, it does not spawn a volume query per node or use the unsupported `wpctl move` command.

`src/server.rs` owns the snapshot, subscription and private Unix socket. A bounded queue serializes requests with audio events. Refreshes are limited to one per 60 ms during changes. The idle loop blocks; the subscription reconnects with bounded exponential backoff. Commands have three-second deadlines. SIGTERM/INT stop the subscription and remove the socket. Runtime directories must belong to the current UID and be private.

`src/install.rs` embeds and installs the native plugin, preserves unrelated settings and plugin enablement, backs up changed settings, and keeps plugin backups outside Noctalia's scanned directory. Repeat installations do not duplicate enablement or add widgets.

`plugins/nix-sound/service.luau` lazily starts the backend and passes JSON snapshots through Noctalia's shared plugin state. It coalesces pending volume operations. `sound.luau` renders real host controls; stable node keys preserve control and scroll identity. `host.luau` reads effective Noctalia appearance and logical monitor dimensions. Native shell effects are owned by Noctalia, with no independent theme generation.
