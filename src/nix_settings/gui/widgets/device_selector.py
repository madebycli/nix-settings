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
    ) -> None:
        self._ids: list[int] = []
        self.widget = Gtk.DropDown.new_from_strings([])
        names: list[str] = []
        selected = 0
        for index, device in enumerate(devices):
            self._ids.append(device.id)
            names.append(device.description)
            if device.id == selected_id:
                selected = index
        self.widget.set_model(Gtk.StringList.new(names))
        if names:
            self.widget.set_selected(selected)
        self.widget.set_hexpand(True)
        self.widget.connect("notify::selected", self._changed, on_selected)

    def _changed(self, dropdown: Any, _param: Any, callback: Callable[[int], None]) -> None:
        index = int(dropdown.get_selected())
        if 0 <= index < len(self._ids):
            callback(self._ids[index])
