from __future__ import annotations

from typing import Any

from nix_settings.audio.wireplumber import WirePlumberBackend
from nix_settings.gui.layout import HEADER_HEIGHT, window_size
from nix_settings.gui.pages.sound import SoundPage
from nix_settings.gui.theme import install_css


class SettingsWindow:
    def __init__(
        self,
        Gtk: Any,
        Gdk: Any,
        GLib: Any,
        GtkLayerShell: Any,
        application: Any,
        page: str = "sound",
    ) -> None:
        del page
        self.Gtk = Gtk
        self.Gdk = Gdk
        self.GLib = GLib
        self.GtkLayerShell = GtkLayerShell
        self.window = Gtk.ApplicationWindow(application=application)
        self.window.set_title("Nix Settings Sound")
        self.window.set_app_paintable(True)
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.get_style_context().add_class("nix-settings-window")
        self._configure_visual()
        width, height = self._size()
        self.window.set_size_request(width, height)
        self.window.set_default_size(width, height)
        self._configure_layer_shell()
        install_css(Gtk, Gdk)

        self.sound_page = SoundPage(Gtk, GLib, WirePlumberBackend())
        self.window.add(self._build_root())
        self.window.connect("key-press-event", self._key_pressed)
        self.window.connect("delete-event", self._close_requested)
        self.window.connect("destroy", self._destroyed)

    def present(self) -> None:
        self.window.show_all()
        self.sound_page.error.hide()
        self.window.present()
        self.sound_page.start()

    def _configure_visual(self) -> None:
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None:
            self.window.set_visual(visual)

    def _configure_layer_shell(self) -> None:
        self.GtkLayerShell.init_for_window(self.window)
        self.GtkLayerShell.set_layer(self.window, self.GtkLayerShell.Layer.OVERLAY)
        self.GtkLayerShell.set_keyboard_mode(
            self.window,
            self.GtkLayerShell.KeyboardMode.EXCLUSIVE,
        )
        self.GtkLayerShell.set_exclusive_zone(self.window, 0)
        self.GtkLayerShell.set_namespace(self.window, "nix-settings-sound")

    def _size(self) -> tuple[int, int]:
        display = self.Gdk.Display.get_default()
        if display is None:
            return window_size(None, None)
        monitor = display.get_primary_monitor()
        if monitor is None and display.get_n_monitors() > 0:
            monitor = display.get_monitor(0)
        if monitor is None:
            return window_size(None, None)
        geometry = monitor.get_geometry()
        return window_size(int(geometry.width), int(geometry.height))

    def _build_root(self) -> Any:
        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class("nix-settings-root")
        root.pack_start(self._header(), False, False, 0)
        root.pack_start(self.sound_page.widget, True, True, 0)
        footer = self.Gtk.Label(label="Esc = close  •  Ctrl+R = refresh  •  Ctrl+Q = quit")
        footer.get_style_context().add_class("shortcut-hint")
        footer.set_margin_top(3)
        footer.set_margin_bottom(10)
        root.pack_end(footer, False, False, 0)
        return root

    def _header(self) -> Any:
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=10)
        header.get_style_context().add_class("app-header")
        header.set_size_request(-1, HEADER_HEIGHT)
        header.set_margin_top(10)
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_bottom(2)

        close = self.Gtk.Button(label="×")
        close.set_size_request(30, 30)
        close.get_style_context().add_class("close-button")
        close.connect("clicked", lambda *_: self.window.close())

        title = self.Gtk.Label(label="Sound", xalign=0)
        title.get_style_context().add_class("app-title")
        title.set_hexpand(True)

        refresh = self.Gtk.Button(label="Refresh")
        refresh.set_size_request(82, 30)
        refresh.get_style_context().add_class("pill")
        refresh.connect("clicked", lambda *_: self.sound_page.refresh())

        header.pack_start(close, False, False, 0)
        header.pack_start(title, True, True, 0)
        header.pack_end(refresh, False, False, 0)
        return header

    def _close_requested(self, _window: Any, _event: Any) -> bool:
        self.sound_page.stop()
        return False

    def _destroyed(self, _window: Any) -> None:
        self.sound_page.stop()

    def _key_pressed(self, _window: Any, event: Any) -> bool:
        ctrl = bool(event.state & self.Gdk.ModifierType.CONTROL_MASK)
        if event.keyval == self.Gdk.KEY_Escape:
            self.window.close()
            return True
        if ctrl and event.keyval in {self.Gdk.KEY_q, self.Gdk.KEY_Q}:
            app = self.window.get_application()
            if app is not None:
                app.quit()
            return True
        if ctrl and event.keyval in {self.Gdk.KEY_r, self.Gdk.KEY_R}:
            self.sound_page.refresh()
            return True
        return False
