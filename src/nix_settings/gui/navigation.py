from __future__ import annotations

from typing import Any

PAGES = (
    ("overview", "Overview"),
    ("updates", "Updates"),
    ("generations", "Generations"),
    ("storage", "Storage"),
    ("sound", "Sound"),
    ("network", "Network"),
    ("bluetooth", "Bluetooth"),
    ("integrations", "Integrations"),
)


def build_navigation(Gtk: Any, stack: Any) -> Any:
    sidebar = Gtk.StackSidebar(stack=stack)
    sidebar.add_css_class("navigation")
    sidebar.set_vexpand(True)
    return sidebar
