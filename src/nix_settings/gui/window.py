from __future__ import annotations

import os
from typing import Any

from nix_settings.audio.wireplumber import WirePlumberBackend
from nix_settings.gui.layout import HEADER_HEIGHT, MIN_HEIGHT, MIN_WIDTH, window_size
from nix_settings.gui.navigation import PAGES, build_navigation
from nix_settings.gui.pages.placeholder import build_placeholder
from nix_settings.gui.pages.sound import SoundPage
from nix_settings.gui.theme import install_css


class SettingsWindow:
    def __init__(self, Gtk: Any, Gdk: Any, GLib: Any, application: Any, page: str = "sound") -> None:
        self.Gtk = Gtk
        self.Gdk = Gdk
        self.GLib = GLib
        self.window = Gtk.ApplicationWindow(application=application)
        self.window.set_title("Nix Settings")
        self.window.add_css_class("nix-settings-window")
        self.window.set_default_size(*self._size())
        self.window.set_size_request(MIN_WIDTH, MIN_HEIGHT)
        self.window.set_resizable(True)
        self._layer_shell_enabled = self._configure_layer_shell()
        install_css(Gtk, Gdk)
        self.sound_page = SoundPage(Gtk, GLib, WirePlumberBackend())
        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        for name, title in PAGES:
            child = self.sound_page.widget if name == "sound" else build_placeholder(Gtk, title)
            self.stack.add_titled(child, name, title)
        self.stack.set_visible_child_name(page if page in dict(PAGES) else "sound")
        self.window.set_child(self._build_root())
        self.window.connect("close-request", self._close_requested)
        self._install_shortcuts()

    def present(self) -> None:
        self.window.present()
        self.sound_page.start()

    def _close_requested(self, _window: Any) -> bool:
        self.sound_page.stop()
        return False

    def refresh_active(self) -> None:
        if self.stack.get_visible_child_name() == "sound":
            self.sound_page.refresh()

    def _size(self) -> tuple[int, int]:
        display = self.Gdk.Display.get_default()
        if display is None:
            return window_size(None, None)
        monitors = display.get_monitors()
        monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is None:
            return window_size(None, None)
        geometry = monitor.get_geometry()
        return window_size(int(geometry.width), int(geometry.height))

    def _configure_layer_shell(self) -> bool:
        if not os.environ.get("WAYLAND_DISPLAY"):
            self.window.set_decorated(True)
            return False
        try:
            import gi

            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell as LayerShell

            self.window.set_decorated(False)
            self.window.set_resizable(False)
            LayerShell.init_for_window(self.window)
            LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
            LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.EXCLUSIVE)
            LayerShell.set_exclusive_zone(self.window, 0)
            LayerShell.set_namespace(self.window, "nix-settings")
            return True
        except (ImportError, ValueError, AttributeError):
            self.window.set_decorated(True)
            return False

    def _build_root(self) -> Any:
        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL)
        root.add_css_class("nix-settings-root")
        root.append(self._header())
        body = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL)
        body.set_vexpand(True)
        body.append(build_navigation(self.Gtk, self.stack))
        body.append(self.stack)
        root.append(body)
        footer = self.Gtk.Label(label="Esc = close  •  Ctrl+R = refresh  •  Ctrl+Q = quit")
        footer.add_css_class("shortcut-hint")
        footer.set_margin_top(6)
        footer.set_margin_bottom(8)
        root.append(footer)
        return root

    def _header(self) -> Any:
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        header.add_css_class("app-header")
        header.set_size_request(-1, HEADER_HEIGHT)
        close = self.Gtk.Button(label="✕")
        close.add_css_class("close-button")
        close.connect("clicked", lambda *_: self.window.close())
        title = self.Gtk.Label(label="Nix Settings", xalign=0)
        title.add_css_class("app-title")
        title.set_hexpand(True)
        status = self.Gtk.Label(label="READY")
        status.add_css_class("status-chip")
        header.append(close)
        header.append(title)
        header.append(status)
        return header

    def _install_shortcuts(self) -> None:
        controller = self.Gtk.EventControllerKey()
        controller.connect("key-pressed", self._key_pressed)
        self.window.add_controller(controller)

    def _key_pressed(self, _controller: Any, keyval: int, _keycode: int, state: int) -> bool:
        ctrl = bool(state & self.Gdk.ModifierType.CONTROL_MASK)
        if keyval == self.Gdk.KEY_Escape:
            self.window.close()
            return True
        if ctrl and keyval in {self.Gdk.KEY_q, self.Gdk.KEY_Q}:
            app = self.window.get_application()
            if app is not None:
                app.quit()
            return True
        if ctrl and keyval in {self.Gdk.KEY_r, self.Gdk.KEY_R}:
            self.refresh_active()
            return True
        return False
