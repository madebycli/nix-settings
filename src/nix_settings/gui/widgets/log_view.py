from __future__ import annotations

import shutil
import subprocess
from collections import deque
from typing import Any

from nix_settings.backend.process import redact_line


class LogView:
    def __init__(self, Gtk: Any, *, max_lines: int = 2000, min_height: int = 180) -> None:
        from gi.repository import Gdk, GLib

        self.Gtk = Gtk
        self.Gdk = Gdk
        self.GLib = GLib
        self.max_lines = max_lines
        self._lines: deque[str] = deque(maxlen=max_lines)
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="LOG", xalign=0)
        title.get_style_context().add_class("section-title")
        toolbar.pack_start(title, True, True, 0)
        self.copy_button = Gtk.Button(label="Copy")
        self.copy_button.set_size_request(72, 28)
        self.copy_button.get_style_context().add_class("flat-action")
        self.copy_button.connect("clicked", self._copy)
        clear = Gtk.Button(label="Clear")
        clear.set_size_request(72, 28)
        clear.get_style_context().add_class("flat-action")
        clear.connect("clicked", self._clear_clicked)
        toolbar.pack_start(self.copy_button, False, False, 0)
        toolbar.pack_start(clear, False, False, 0)
        self.widget.pack_start(toolbar, False, False, 0)

        self.view = Gtk.TextView()
        self.view.set_editable(False)
        self.view.set_cursor_visible(True)
        self.view.set_can_focus(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.get_style_context().add_class("log-view")
        self.view.connect("key-press-event", self._key_press)
        self.buffer = self.view.get_buffer()
        self.error_tag = self.buffer.create_tag("error", weight=700)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(min_height)
        self.scroll.get_style_context().add_class("log-scroll")
        self.scroll.add(self.view)
        self.widget.pack_start(self.scroll, True, True, 0)

    def append(self, message: str, *, error: bool = False) -> None:
        line = redact_line(message).strip()
        if not line:
            return
        adjustment = self.scroll.get_vadjustment()
        at_bottom = adjustment.get_value() >= max(
            0.0, adjustment.get_upper() - adjustment.get_page_size() - 4.0
        )
        self._lines.append(line)
        text = "\n".join(self._lines) + "\n"
        self.buffer.set_text(text)
        if error:
            start = self.buffer.get_iter_at_line(max(0, len(self._lines) - 1))
            end = self.buffer.get_end_iter()
            self.buffer.apply_tag(self.error_tag, start, end)
        if at_bottom:
            mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
            self.view.scroll_mark_onscreen(mark)
            self.buffer.delete_mark(mark)

    def clear(self) -> None:
        self._lines.clear()
        self.buffer.set_text("")

    def _clear_clicked(self, _button: Any) -> None:
        self.clear()

    def _clipboard(self) -> Any:
        clipboard = self.Gtk.Clipboard.get_default(self.view.get_display())
        if clipboard is None:
            clipboard = self.Gtk.Clipboard.get(self.Gdk.SELECTION_CLIPBOARD)
        return clipboard

    def _text_to_copy(self) -> str:
        if self.buffer.get_has_selection():
            start = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            end = self.buffer.get_iter_at_mark(self.buffer.get_selection_bound())
            if start.compare(end) > 0:
                start, end = end, start
            return str(self.buffer.get_text(start, end, True))
        start, end = self.buffer.get_bounds()
        return str(self.buffer.get_text(start, end, True)).rstrip("\n")

    @staticmethod
    def _copy_wayland(text: str) -> bool:
        executable = shutil.which("wl-copy")
        if executable is None:
            return False
        try:
            result = subprocess.run(
                [executable, "--type", "text/plain;charset=utf-8"],
                input=text,
                text=True,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def _copy(self, _button: Any = None) -> None:
        text = self._text_to_copy()
        if not text:
            return

        # The application is Wayland-only, so use the compositor-native
        # clipboard path first. GTK remains a fallback for dev/test sessions.
        wayland_ok = self._copy_wayland(text)
        clipboard = self._clipboard()
        clipboard.set_text(text, -1)
        clipboard.store()
        self.copy_button.set_label("Copied" if wayland_ok else "Copied (GTK)")
        self.GLib.timeout_add(900, self._reset_copy_label)

    def _reset_copy_label(self) -> bool:
        self.copy_button.set_label("Copy")
        return False

    def _key_press(self, _view: Any, event: Any) -> bool:
        control = bool(event.state & self.Gdk.ModifierType.CONTROL_MASK)
        key_name = self.Gdk.keyval_name(event.keyval) or ""
        if control and key_name.lower() == "c":
            self._copy()
            return True
        return False
