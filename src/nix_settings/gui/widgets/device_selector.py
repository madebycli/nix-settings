from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from nix_settings.audio.models import AudioDevice


class DeviceSelector:
    def __init__(
        self,
        Gtk: Any,
        devices: Sequence[AudioDevice],
        selected_id: int | None,
        on_selected: Callable[[int], None],
        on_scroll: Callable[[Any], None] | None = None,
    ) -> None:
        self._ids: list[int] = []
        self._selected_id = selected_id
        self._on_scroll = on_scroll
        self.widget = Gtk.ComboBoxText()
        active_index = 0
        for index, device in enumerate(devices):
            self._ids.append(device.id)
            self.widget.append_text(device.description)
            if device.id == selected_id:
                active_index = index
        if self._ids:
            self.widget.set_active(active_index)
        self.widget.set_hexpand(True)
        self.widget.connect("changed", self._changed, on_selected)
        self.widget.connect("scroll-event", self._scroll)

    def _changed(self, combo: Any, callback: Callable[[int], None]) -> None:
        index = int(combo.get_active())
        if not 0 <= index < len(self._ids):
            return
        selected_id = self._ids[index]
        if selected_id == self._selected_id:
            return
        self._selected_id = selected_id
        callback(selected_id)

    def _scroll(self, _combo: Any, event: Any) -> bool:
        if self._on_scroll is not None:
            self._on_scroll(event)
        return True
