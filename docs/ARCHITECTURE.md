# Architecture

## Fixed GTK3 layer-shell surface

`SettingsWindow` owns the only `Gtk.ApplicationWindow`. GtkLayerShell is initialized once, the logical monitor workarea is read once, and the calculated size is applied before the window is shown. A direct `Gtk.Stack` with transitions disabled holds the fixed application views. There is no secondary top-level window and no separate routing framework.

The existing `SoundPage` is instantiated unchanged and only receives the same shared outer frame. It starts its monitor and initial refresh when Sound is first shown.

## Views

- Overview: native cards populated from typed `nix-status --json` data.
- Updates: exact nix-config mode mapping, safe preview, confirmation and NDJSON operation events.
- Config Sync: read-only structured state plus existing `config-sync` actions and managed-path editor.
- Generations: structured list, comparison and restricted rollback.
- Storage: status, mandatory cleanup preview and separate optimization.
- System: health snapshot, doctor and restricted build/switch.
- Sound: existing PipeWire/WirePlumber implementation.

All views scroll inside the frozen frame. Header height and card/control geometry are shared.

## Backend boundary

`backend.models` validates stable JSON contracts. `backend.process` starts argv lists with `shell=False`, a controlled environment and new process groups. `RequestGate` assigns monotonically increasing generations so stale worker results cannot replace newer UI state. GTK mutations are handed back through `GLib.idle_add`.

Long-running actions use NDJSON-style events and a native read-only `Gtk.TextView`. The log strips ANSI sequences, redacts common credential assignments, retains at most 2,000 lines and only follows the end while the user remains at the bottom.

## Privilege boundary

Unprivileged work includes status, Git relation, update preview, profile metadata, Config Sync comparison and local statistics.

The packaged helper is invoked through `pkexec` and a system-installed Polkit policy. It accepts a fixed operation allowlist and validates caller UID, repository location/ownership/remote, profile names, arguments and executable paths. It never accepts a command string. The desktop Polkit agent owns authentication.

## Backend repository

`madebycli/nix-config` remains the business-logic source. Text CLI output stays compatible while `--json` adds read-only contracts. Config Sync's adapter imports the current backend module, including its manifests, checksums, secret detection and conflict classification. The terminal scripts remain usable without Nix Settings.
