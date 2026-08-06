# Architecture

Nix Settings uses a strict boundary between presentation and audio control.

- `audio.models` defines immutable typed data passed to the UI.
- `audio.pipewire` converts structured `pw-dump` JSON into those models.
- `audio.commands` is the only raw `wpctl` command-construction layer.
- `audio.wireplumber` implements the backend interface.
- `audio.monitor` owns the long-running event subscription and reconnect loop.
- `gui.pages.sound` receives snapshots and dispatches background operations.
- all worker results cross into GTK through `GLib.idle_add`.

GTK4 Layer Shell is enabled only under Wayland and falls back to a normal GTK4 application window when the namespace or session is unavailable. The single-instance behavior comes from the stable `Gtk.Application` ID.
