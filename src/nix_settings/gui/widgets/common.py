from __future__ import annotations

from collections.abc import Callable
from typing import Any


def styled_label(Gtk: Any, text: str, css_class: str, *, xalign: float = 0.0) -> Any:
    label = Gtk.Label(label=text, xalign=xalign)
    label.set_ellipsize(3)
    label.set_tooltip_text(text)
    label.get_style_context().add_class(css_class)
    return label


def card(Gtk: Any, *, spacing: int = 10) -> Any:
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    widget.get_style_context().add_class("card")
    widget.set_hexpand(True)
    return widget


def stat_row(Gtk: Any, name: str, value: str = "—") -> tuple[Any, Any]:
    row = Gtk.Grid()
    row.set_column_spacing(12)
    row.set_hexpand(True)
    key = styled_label(Gtk, name, "stat-key")
    key.set_size_request(176, -1)
    value_label = styled_label(Gtk, value, "stat-value")
    value_label.set_hexpand(True)
    value_label.set_halign(Gtk.Align.END)
    value_label.set_xalign(1.0)
    row.attach(key, 0, 0, 1, 1)
    row.attach(value_label, 1, 0, 1, 1)
    return row, value_label


def action_button(
    Gtk: Any,
    label: str,
    callback: Callable[..., object],
    *,
    width: int = 132,
    primary: bool = False,
) -> Any:
    button = Gtk.Button(label=label)
    button.set_size_request(width, 32)
    button.get_style_context().add_class("primary-action" if primary else "flat-action")
    button.connect("clicked", callback)
    return button


def page_scroller(Gtk: Any, child: Any) -> Any:
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_hexpand(True)
    scroller.set_vexpand(True)
    scroller.add(child)
    return scroller


def placeholder_page(Gtk: Any, title: str, detail: str) -> Any:
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    content.get_style_context().add_class("content")
    content.set_valign(Gtk.Align.START)
    box = card(Gtk)
    box.pack_start(styled_label(Gtk, title, "card-title"), False, False, 0)
    box.pack_start(styled_label(Gtk, detail, "card-detail"), False, False, 0)
    content.pack_start(box, False, False, 0)
    return page_scroller(Gtk, content)
