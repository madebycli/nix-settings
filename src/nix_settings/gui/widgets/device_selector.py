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
        *,
        width: int | None = None,
    ) -> None:
        self._selected_id = selected_id
        self._on_scroll = on_scroll
        self._model = Gtk.ListStore(str, int)
        active_index = 0
        for index, device in enumerate(devices):
            self._model.append((device.description, device.id))
            if device.id == selected_id:
                active_index = index

        self.widget = Gtk.ComboBox.new_with_model(self._model)
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", 3)
        renderer.set_property("ellipsize-set", True)
        renderer.set_property("width-chars", 34)
        self.widget.pack_start(renderer, True)
        self.widget.add_attribute(renderer, "text", 0)
        self.widget.set_active(active_index if devices else -1)
        self.widget.set_hexpand(True)
        if width is not None:
            self.widget.set_size_request(width, 34)
        self.widget.connect("changed", self._changed, on_selected)
        self.widget.connect("scroll-event", self._scroll)

    def _changed(self, combo: Any, callback: Callable[[int], None]) -> None:
        tree_iter = combo.get_active_iter()
        if tree_iter is None:
            return
        selected_id = int(self._model[tree_iter][1])
        if selected_id == self._selected_id:
            return
        self._selected_id = selected_id
        callback(selected_id)

    def _scroll(self, _combo: Any, event: Any) -> bool:
        if self._on_scroll is not None:
            self._on_scroll(event)
        return True
