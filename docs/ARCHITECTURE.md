# Architecture

`src/audio.rs` normalizes one structured Pulse server graph plus default-device info and constructs validated argv operations. It uses the PipeWire-Pulse compatibility protocol through `pactl`. Unlike the old backend, it does not spawn a volume query per node or use the unsupported `wpctl move` command.

`src/server.rs` owns the snapshot, subscription and private Unix socket. A bounded queue serializes requests with audio events. Refreshes are limited to one per 60 ms during changes. The idle loop blocks; the subscription reconnects with bounded exponential backoff. Commands have three-second deadlines. SIGTERM/INT stop the subscription and remove the socket. Runtime directories must belong to the current UID and be private.

`src/install.rs` embeds and installs the native plugin, preserves unrelated settings and plugin enablement, backs up changed settings, and keeps plugin backups outside Noctalia's scanned directory. Repeat installations do not duplicate enablement or add widgets.

`plugins/nix-sound/service.luau` lazily starts the backend and passes JSON snapshots through Noctalia's shared plugin state. It coalesces pending volume operations. `sound.luau` renders real host controls; stable node keys preserve control and scroll identity. `host.luau` reads effective Noctalia appearance and logical monitor dimensions. Native shell effects are owned by Noctalia, with no independent theme generation.

The centered Sound panel has a preferred maximum of 1600 × 900 logical pixels before Noctalia UI scaling. The host clamps it to smaller output bounds with native screen margins. Native flex distributes column widths without hard-coded monitor-width children, avoiding clipping beside bars or at UI scaling. Application cards have two rows (resolved XDG icon/name/device, then slider/percentage/mute), with 4–8 px gaps/padding. A narrow display uses one outer scroll. Slider onChange captures the numeric value; the argument-free onDragEnd commits it for pointer, wheel and keyboard input.

Percentage labels live inside a fixed-width native flex column. Label width alone is not enforced by the host, so a free label previously stole track width when changing from 90% to 100%. All volume rows now reserve the same percentage-column width.

Master headers share 24-pixel icon slots and 18-pixel semibold text with the host's fixed-height text baseline. The shell font family remains inherited. Section headers share consistent insets; application identities occupy a fixed column so routing selectors align even when app names have different lengths. App labels use the native body-size text hierarchy.

Wide-mode master cards and section captions account for the native ScrollView's own 4-output-pixel horizontal viewport insets. Matching script padding divides that inset by the effective Noctalia UI scale, avoiding a second scaled margin. Adjacent columns rely on those viewport insets for their gutter. Only a 4-unit master/section gap remains; the section heading adds no extra gap above the list's native vertical inset. This keeps master and application tracks aligned and avoids compounded empty space.
