# Architecture

Nix Settings keeps presentation and audio control separate.

- `audio.models` defines immutable typed data passed to the UI.
- `audio.pipewire` converts structured `pw-dump` JSON into those models.
- `audio.commands` is the only raw `wpctl` command-construction layer.
- `audio.wireplumber` implements the backend interface.
- `audio.monitor` owns the long-running event subscription and reconnect loop.
- `gui.pages.sound` receives snapshots and dispatches background operations.
- worker results cross into GTK through `GLib.idle_add` or bounded timeouts.

The graphical process uses GTK3 and `GtkLayerShell`. It requires Wayland and deliberately does not fall back to a normal floating window. `nix-settings sound` opens only the sound center, without a settings sidebar or unfinished pages. The stable `Gtk.Application` ID provides single-instance behavior.

Sound controls are initialized before their signal handlers are connected. PipeWire events are debounced, slider writes are delayed until dragging finishes, and the vertical adjustment is restored after snapshot rendering. These rules prevent duplicate operations and scroll jumps.
