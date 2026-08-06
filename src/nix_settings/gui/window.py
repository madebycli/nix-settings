from __future__ import annotations

from typing import Any

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.models import AudioSnapshot
from nix_settings.gui.layout import window_size
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
        backend: AudioBackend,
        initial_snapshot: AudioSnapshot,
        initial_error: str | None = None,
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

        self.sound_page = SoundPage(
            Gtk,
            GLib,
            backend,
            initial_snapshot,
            width,
            initial_error,
        )
        self.window.add(self._build_root())
        self.window.connect("key-press-event", self._key_pressed)
        self.window.connect("delete-event", self._close_requested)
        self.window.connect("destroy", self._destroyed)

    def present(self) -> None:
        self.window.show_all()
        if not self.sound_page.has_error:
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
        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("nix-settings-root")
        root.pack_start(self._header(), False, False, 0)
        root.pack_start(self.Gtk.Separator(), False, False, 0)
        root.pack_start(self.sound_page.widget, True, True, 0)
        return root

    def _header(self) -> Any:
        header = self.Gtk.Grid()
        header.set_column_spacing(10)
        header.set_hexpand(True)
        header.set_size_request(-1, 32)
        header.set_margin_top(6)
        header.set_margin_bottom(6)
        header.set_margin_start(12)
        header.set_margin_end(12)

        close = self.Gtk.EventBox()
        close.set_size_request(32, 32)
        close.set_halign(self.Gtk.Align.CENTER)
        close.set_valign(self.Gtk.Align.CENTER)
        close.set_hexpand(False)
        close.set_vexpand(False)
        close.set_tooltip_text("Close")
        close.add_events(
            self.Gdk.EventMask.BUTTON_PRESS_MASK
            | self.Gdk.EventMask.ENTER_NOTIFY_MASK
            | self.Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        close.get_style_context().add_class("x-btn")
        close.connect("button-press-event", self._close_clicked)
        close.connect("enter-notify-event", self._close_entered)
        close.connect("leave-notify-event", self._close_left)

        close_label = self.Gtk.Label(label="×")
        close_label.set_halign(self.Gtk.Align.CENTER)
        close_label.set_valign(self.Gtk.Align.CENTER)
        close_label.get_style_context().add_class("x-btn-label")
        close.add(close_label)
        header.attach(close, 0, 0, 1, 1)

        title = self.Gtk.Label(label="Sound", xalign=0)
        title.set_halign(self.Gtk.Align.START)
        title.set_valign(self.Gtk.Align.CENTER)
        title.get_style_context().add_class("picker-title")
        header.attach(title, 1, 0, 1, 1)

        spacer = self.Gtk.Box()
        spacer.set_hexpand(True)
        header.attach(spacer, 2, 0, 1, 1)

        refresh = self.Gtk.Button(label="Refresh")
        refresh.set_size_request(88, 30)
        refresh.set_halign(self.Gtk.Align.END)
        refresh.get_style_context().add_class("flat-action")
        refresh.connect("clicked", lambda *_: self.sound_page.refresh())
        header.attach(refresh, 3, 0, 1, 1)
        return header

    def _close_clicked(self, _widget: Any, event: Any) -> bool:
        if int(getattr(event, "button", 0)) == 1:
            self.window.close()
            return True
        return False

    @staticmethod
    def _close_entered(widget: Any, _event: Any) -> bool:
        widget.get_style_context().add_class("hover")
        return False

    @staticmethod
    def _close_left(widget: Any, _event: Any) -> bool:
        widget.get_style_context().remove_class("hover")
        return False

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
