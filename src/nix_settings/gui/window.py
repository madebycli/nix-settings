from __future__ import annotations

from typing import Any

from nix_settings.audio.backend import AudioBackend
from nix_settings.audio.models import AudioSnapshot
from nix_settings.gui.layout import HEADER_HEIGHT, layout_mode, window_size
from nix_settings.gui.pages.generations import GenerationsPage
from nix_settings.gui.pages.overview import OverviewPage
from nix_settings.gui.pages.sound import SoundPage
from nix_settings.gui.pages.storage import StoragePage
from nix_settings.gui.pages.sync import SyncPage
from nix_settings.gui.pages.system import SystemPage
from nix_settings.gui.pages.updates import UpdatesPage
from nix_settings.gui.theme import install_css

PAGE_TITLES = {
    "overview": "Nix Settings",
    "sound": "Sound",
    "updates": "Updates",
    "sync": "Config Sync",
    "system": "System",
    "generations": "Generations",
    "storage": "Storage",
}


class SettingsWindow:
    def __init__(
        self,
        Gtk: Any,
        Gdk: Any,
        GLib: Any,
        GtkLayerShell: Any,
        application: Any,
        backend: AudioBackend,
        page: str = "overview",
    ) -> None:
        self.Gtk = Gtk
        self.Gdk = Gdk
        self.GLib = GLib
        self.GtkLayerShell = GtkLayerShell
        self.backend = backend
        self.window = Gtk.ApplicationWindow(application=application)
        self.window.set_title("Nix Settings")
        self.window.set_app_paintable(True)
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.get_style_context().add_class("nix-settings-window")
        self._configure_visual()
        self.width, self.height = self._size()
        self.window.set_size_request(self.width, self.height)
        self.window.set_default_size(self.width, self.height)
        self._configure_layer_shell()
        install_css(Gtk, Gdk)
        self.window.get_style_context().add_class(f"layout-{layout_mode(self.width, self.height)}")

        self.sound_page = SoundPage(
            Gtk,
            GLib,
            backend,
            AudioSnapshot.empty(),
            self.width,
            None,
        )
        self.overview_page = OverviewPage(Gtk, GLib, self.show_page)
        self.updates_page = UpdatesPage(Gtk, GLib, self.window)
        self.sync_page = SyncPage(Gtk, GLib, self.window)
        self.system_page = SystemPage(Gtk, GLib, self.window)
        self.generations_page = GenerationsPage(Gtk, GLib, self.window)
        self.storage_page = StoragePage(Gtk, GLib, self.window)
        self.pages: dict[str, Any] = {
            "overview": self.overview_page,
            "sound": self.sound_page,
            "updates": self.updates_page,
            "sync": self.sync_page,
            "system": self.system_page,
            "generations": self.generations_page,
            "storage": self.storage_page,
        }
        self._started_pages: set[str] = set()
        self.current_page = page if page in self.pages else "overview"
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_homogeneous(True)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        for name, page_object in self.pages.items():
            self.stack.add_named(page_object.widget, name)

        self.header_title: Any = None
        self.home_button: Any = None
        self.refresh_button: Any = None
        self.window.add(self._build_root())
        self.window.connect("key-press-event", self._key_pressed)
        self.window.connect("delete-event", self._close_requested)
        self.window.connect("destroy", self._destroyed)
        self.show_page(self.current_page)

    def present(self) -> None:
        self.window.show_all()
        if not self.sound_page.has_error:
            self.sound_page.error.hide()
        self.show_page(self.current_page)
        self.window.present()

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
        workarea = monitor.get_workarea()
        scale = int(monitor.get_scale_factor())
        return window_size(int(workarea.width), int(workarea.height), scale)

    def _build_root(self) -> Any:
        root = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("nix-settings-root")
        root.pack_start(self._header(), False, False, 0)
        root.pack_start(self.Gtk.Separator(), False, False, 0)
        root.pack_start(self.stack, True, True, 0)
        return root

    def _header(self) -> Any:
        header = self.Gtk.Grid()
        header.set_column_spacing(10)
        header.set_hexpand(True)
        header.set_size_request(-1, HEADER_HEIGHT)
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

        self.home_button = self.Gtk.Button(label="⌂")
        self.home_button.set_size_request(32, 30)
        self.home_button.set_tooltip_text("Overview")
        self.home_button.get_style_context().add_class("flat-action")
        self.home_button.connect("clicked", lambda *_: self.show_page("overview"))
        header.attach(self.home_button, 1, 0, 1, 1)

        self.header_title = self.Gtk.Label(label="Nix Settings", xalign=0)
        self.header_title.set_halign(self.Gtk.Align.START)
        self.header_title.set_valign(self.Gtk.Align.CENTER)
        self.header_title.get_style_context().add_class("picker-title")
        header.attach(self.header_title, 2, 0, 1, 1)

        spacer = self.Gtk.Box()
        spacer.set_hexpand(True)
        header.attach(spacer, 3, 0, 1, 1)

        self.refresh_button = self.Gtk.Button(label="Refresh")
        self.refresh_button.set_size_request(88, 30)
        self.refresh_button.set_halign(self.Gtk.Align.END)
        self.refresh_button.get_style_context().add_class("flat-action")
        self.refresh_button.connect("clicked", self._refresh_current)
        header.attach(self.refresh_button, 4, 0, 1, 1)
        return header

    def show_page(self, name: str) -> None:
        if name not in self.pages:
            name = "overview"
        self.current_page = name
        self.stack.set_visible_child_name(name)
        self.header_title.set_text(PAGE_TITLES[name])
        self.home_button.set_visible(name != "overview")
        refreshable = name == "sound" or callable(getattr(self.pages[name], "refresh", None))
        self.refresh_button.set_visible(refreshable)
        if name not in self._started_pages:
            page = self.pages[name]
            start = getattr(page, "start", None)
            if callable(start):
                start()
            if name == "sound":
                self.sound_page.refresh()
            self._started_pages.add(name)

    def _refresh_current(self, _button: Any) -> None:
        if self.current_page == "sound":
            self.sound_page.refresh()
            return
        refresh = getattr(self.pages[self.current_page], "refresh", None)
        if callable(refresh):
            refresh()

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
        for page in self.pages.values():
            operation = getattr(page, "operation", None)
            if operation is not None:
                operation.cancel()

    def _key_pressed(self, _window: Any, event: Any) -> bool:
        ctrl = bool(event.state & self.Gdk.ModifierType.CONTROL_MASK)
        if event.keyval == self.Gdk.KEY_Escape:
            if self.current_page != "overview":
                self.show_page("overview")
            else:
                self.window.close()
            return True
        if ctrl and event.keyval in {self.Gdk.KEY_q, self.Gdk.KEY_Q}:
            app = self.window.get_application()
            if app is not None:
                app.quit()
            return True
        if ctrl and event.keyval in {self.Gdk.KEY_r, self.Gdk.KEY_R}:
            self._refresh_current(None)
            return True
        return False
