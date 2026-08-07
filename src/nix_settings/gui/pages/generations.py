from __future__ import annotations

from typing import Any

from nix_settings.backend.cache import JsonCache
from nix_settings.backend.models import GenerationStatus, format_bytes
from nix_settings.backend.process import BackendCommands, JsonRunner, StreamingProcess
from nix_settings.backend.requests import RequestGate
from nix_settings.gui.modal import prepare_layer_dialog
from nix_settings.gui.widgets.common import action_button, card, page_scroller, styled_label
from nix_settings.gui.widgets.log_view import LogView


class GenerationsPage:
    def __init__(self, Gtk: Any, GLib: Any, parent_window: Any) -> None:
        self.Gtk = Gtk
        self.GLib = GLib
        self.parent_window = parent_window
        self.runner = JsonRunner(timeout=120.0)
        self.cache = JsonCache()
        self.gate: RequestGate[GenerationStatus] = RequestGate()
        self.operation: StreamingProcess | None = None
        self._started = False

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.get_style_context().add_class("content")
        content.pack_start(self._summary(), False, False, 0)
        content.pack_start(self._list_card(), False, False, 0)
        self.log = LogView(Gtk)
        content.pack_start(self.log.widget, True, True, 0)
        self.widget = page_scroller(Gtk, content)

    def _summary(self) -> Any:
        box = card(self.Gtk)
        header = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        header.pack_start(styled_label(self.Gtk, "GENERATIONS", "section-title"), True, True, 0)
        refresh = action_button(self.Gtk, "Refresh", lambda *_: self.refresh(), width=96)
        rollback = action_button(
            self.Gtk, "Rollback", self._rollback_clicked, width=104, primary=True
        )
        header.pack_start(refresh, False, False, 0)
        header.pack_start(rollback, False, False, 0)
        box.pack_start(header, False, False, 0)
        stats = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=18)
        self.current = styled_label(self.Gtk, "Current: —", "state-title")
        self.latest = styled_label(self.Gtk, "Latest: —", "state-title")
        self.count = styled_label(self.Gtk, "Count: —", "state-title")
        stats.pack_start(self.current, False, False, 0)
        stats.pack_start(self.latest, False, False, 0)
        stats.pack_start(self.count, False, False, 0)
        box.pack_start(stats, False, False, 0)
        compare = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=8)
        compare.pack_start(styled_label(self.Gtk, "Compare", "card-detail"), False, False, 0)
        self.first = self.Gtk.ComboBoxText()
        self.second = self.Gtk.ComboBoxText()
        self.first.set_size_request(120, 32)
        self.second.set_size_request(120, 32)
        compare.pack_start(self.first, False, False, 0)
        compare.pack_start(self.second, False, False, 0)
        compare.pack_start(
            action_button(self.Gtk, "Show diff", self._compare_clicked, width=108),
            False,
            False,
            0,
        )
        box.pack_start(compare, False, False, 0)
        return box

    def _list_card(self) -> Any:
        box = card(self.Gtk)
        box.pack_start(styled_label(self.Gtk, "SYSTEM HISTORY", "section-title"), False, False, 0)
        self.list = self.Gtk.ListBox()
        self.list.set_selection_mode(self.Gtk.SelectionMode.NONE)
        scroll = self.Gtk.ScrolledWindow()
        scroll.set_policy(self.Gtk.PolicyType.NEVER, self.Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(250)
        scroll.add(self.list)
        box.pack_start(scroll, True, True, 0)
        return box

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        cached = self.cache.load("generations")
        if cached is not None:
            try:
                self._apply(GenerationStatus.from_json(cached), None)
            except ValueError:
                pass
        self.refresh()

    def _load_generations(self) -> GenerationStatus:
        payload = self.runner.run(BackendCommands.generations()).json()
        self.cache.save("generations", payload)
        return GenerationStatus.from_json(payload)

    def refresh(self) -> None:
        generation = self.gate.begin()
        self.gate.run(
            generation,
            self._load_generations,
            self._finished,
        )

    def _finished(self, value: GenerationStatus | None, error: Exception | None) -> None:
        self.GLib.idle_add(self._apply, value, error)

    def _apply(self, value: GenerationStatus | None, error: Exception | None) -> bool:
        if error is not None or value is None:
            self.log.append(str(error or "Unknown generation error"), error=True)
            return False
        self.current.set_text(f"Current: {value.current_generation or '—'}")
        self.latest.set_text(f"Latest: {value.latest_generation or '—'}")
        self.count.set_text(f"Count: {value.generation_count}")
        for child in list(self.list.get_children()):
            self.list.remove(child)
        self.first.remove_all()
        self.second.remove_all()
        for generation in value.generations:
            row = self.Gtk.Grid()
            row.set_column_spacing(12)
            row.set_margin_top(7)
            row.set_margin_bottom(7)
            row.set_margin_start(10)
            row.set_margin_end(10)
            number = styled_label(self.Gtk, str(generation.generation), "state-title")
            number.set_size_request(72, -1)
            created = styled_label(self.Gtk, generation.created_at or "Unknown date", "card-detail")
            created.set_size_request(190, -1)
            status = styled_label(self.Gtk, generation.status.replace("-", " "), "status-text")
            status.set_size_request(150, -1)
            path = styled_label(self.Gtk, generation.closure_path, "card-detail")
            path.set_hexpand(True)
            size = styled_label(self.Gtk, format_bytes(generation.closure_bytes), "card-detail")
            row.attach(number, 0, 0, 1, 1)
            row.attach(created, 1, 0, 1, 1)
            row.attach(status, 2, 0, 1, 1)
            row.attach(path, 3, 0, 1, 1)
            row.attach(size, 4, 0, 1, 1)
            self.list.add(row)
            label = str(generation.generation)
            self.first.append(label, label)
            self.second.append(label, label)
        if value.generations:
            self.first.set_active(0)
            self.second.set_active(min(1, len(value.generations) - 1))
        self.list.show_all()
        return False

    def _compare_clicked(self, _button: Any) -> None:
        first = self.first.get_active_id()
        second = self.second.get_active_id()
        if not first or not second or first == second:
            self.log.append("Choose two different generations", error=True)
            return
        argv = ["nix-generations", "--diff", first, second]
        self.operation = StreamingProcess(argv, self._event, self._done)
        self.operation.start()

    def _rollback_clicked(self, _button: Any) -> None:
        dialog = self.Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=self.Gtk.MessageType.WARNING,
            buttons=self.Gtk.ButtonsType.CANCEL,
            text="Roll back to the previous system generation?",
        )
        dialog.format_secondary_text(
            "The desktop Polkit agent will authenticate the restricted rollback helper."
        )
        dialog.add_button("Rollback", self.Gtk.ResponseType.OK)
        prepare_layer_dialog(dialog)
        response = dialog.run()
        dialog.destroy()
        if response != self.Gtk.ResponseType.OK:
            return
        self.operation = StreamingProcess(
            BackendCommands.privileged("rollback"), self._event, self._done
        )
        self.operation.start()

    def _event(self, payload: dict[str, Any]) -> None:
        self.GLib.idle_add(
            self._append_operation_log,
            str(payload.get("message", payload.get("event", ""))),
            str(payload.get("stream", "")) == "stderr",
        )

    def _append_operation_log(self, message: str, error: bool) -> bool:
        self.log.append(message, error=error)
        return False

    def _done(self, code: int, error: str | None) -> None:
        self.GLib.idle_add(self._finish, code, error)

    def _finish(self, code: int, error: str | None) -> bool:
        self.operation = None
        if error:
            self.log.append(error, error=True)
        if code == 0:
            self.refresh()
        return False
