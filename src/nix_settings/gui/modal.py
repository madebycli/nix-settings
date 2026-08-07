from __future__ import annotations

from typing import Any


def prepare_layer_dialog(dialog: Any) -> None:
    """Keep modal GTK3 dialogs above the layer-shell main surface."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gtk, GtkLayerShell

    dialog.set_decorated(False)
    dialog.set_app_paintable(True)
    dialog.set_opacity(1.0)
    dialog.get_style_context().add_class("nix-settings-root")
    dialog.get_style_context().add_class("nix-settings-modal")
    content = dialog.get_content_area()
    content.get_style_context().add_class("nix-settings-modal-content")
    screen = dialog.get_screen()
    visual = screen.get_rgba_visual() if screen is not None else None
    if visual is not None:
        dialog.set_visual(visual)

    action_area = dialog.get_action_area()
    for button in action_area.get_children():
        response = dialog.get_response_for_widget(button)
        if response in {
            Gtk.ResponseType.OK,
            Gtk.ResponseType.ACCEPT,
            Gtk.ResponseType.APPLY,
            Gtk.ResponseType.YES,
        }:
            button.get_style_context().add_class("primary-action")
        else:
            button.get_style_context().add_class("flat-action")

    GtkLayerShell.init_for_window(dialog)
    GtkLayerShell.set_layer(dialog, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(dialog, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    GtkLayerShell.set_exclusive_zone(dialog, 0)
    GtkLayerShell.set_namespace(dialog, "nix-settings-modal")
