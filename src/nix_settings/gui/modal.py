from __future__ import annotations

from typing import Any


def prepare_layer_dialog(dialog: Any) -> None:
    """Keep modal GTK3 dialogs above the layer-shell main surface."""
    import gi

    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell

    dialog.set_decorated(False)
    dialog.set_app_paintable(True)
    dialog.get_style_context().add_class("nix-settings-root")
    screen = dialog.get_screen()
    visual = screen.get_rgba_visual() if screen is not None else None
    if visual is not None:
        dialog.set_visual(visual)
    GtkLayerShell.init_for_window(dialog)
    GtkLayerShell.set_layer(dialog, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(dialog, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    GtkLayerShell.set_exclusive_zone(dialog, 0)
    GtkLayerShell.set_namespace(dialog, "nix-settings-modal")
