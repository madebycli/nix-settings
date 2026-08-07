from __future__ import annotations

import os
import shutil
import threading
from typing import Any

from nix_settings.backend.github_auth import DEVICE_LOGIN_URL, GitHubCliAuth, LoginEvent


def run_login(parent: Any) -> bool:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell

    dialog = Gtk.Dialog(title="Sign in to GitHub", transient_for=parent, modal=True)
    dialog.set_decorated(False)
    dialog.set_app_paintable(True)
    dialog.set_size_request(560, 300)
    dialog.get_style_context().add_class("login-dialog")
    rgba = dialog.get_screen().get_rgba_visual()
    if rgba is not None:
        dialog.set_visual(rgba)
    GtkLayerShell.init_for_window(dialog)
    GtkLayerShell.set_layer(dialog, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(dialog, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    GtkLayerShell.set_namespace(dialog, "nix-settings-github-login")
    GtkLayerShell.set_exclusive_zone(dialog, 0)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)

    content = dialog.get_content_area()
    content.set_margin_top(18)
    content.set_margin_bottom(18)
    content.set_margin_start(18)
    content.set_margin_end(18)
    content.set_spacing(12)

    heading = Gtk.Label(label="GitHub CLI browser login", xalign=0)
    heading.get_style_context().add_class("picker-title")
    content.pack_start(heading, False, False, 0)

    explanation = Gtk.Label(
        label=(
            "A browser window will open. Paste the one-time code shown below and approve "
            "GitHub CLI access. Nix Settings never asks for or stores your GitHub token."
        ),
        xalign=0,
    )
    explanation.set_line_wrap(True)
    explanation.get_style_context().add_class("card-detail")
    content.pack_start(explanation, False, False, 0)

    spinner = Gtk.Spinner()
    spinner.start()
    content.pack_start(spinner, False, False, 0)

    status_label = Gtk.Label(label="Starting GitHub CLI…", xalign=0)
    status_label.set_line_wrap(True)
    status_label.get_style_context().add_class("card-detail")
    content.pack_start(status_label, False, False, 0)

    code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    code_box.set_no_show_all(True)
    code_label = Gtk.Label(label="")
    code_label.set_selectable(True)
    code_label.get_style_context().add_class("login-code")
    code_box.pack_start(code_label, True, True, 0)
    copy_button = Gtk.Button(label="Copy code")
    copy_button.get_style_context().add_class("action-btn")
    code_box.pack_start(copy_button, False, False, 0)
    browser_button = Gtk.Button(label="Open browser again")
    browser_button.get_style_context().add_class("flat-action")
    code_box.pack_start(browser_button, False, False, 0)
    content.pack_start(code_box, False, False, 0)

    auth = GitHubCliAuth()
    cancel_event = threading.Event()
    noop_browser = os.environ.get("NIX_SETTINGS_NOOP_BROWSER") or shutil.which("true")
    state: dict[str, Any] = {
        "active": True,
        "browser_opened": False,
        "code": None,
        "error": None,
    }

    def open_browser() -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(DEVICE_LOGIN_URL, None)
            state["browser_opened"] = True
        except GLib.Error as exc:
            status_label.set_text(
                f"Could not open the browser automatically: {exc}. Open {DEVICE_LOGIN_URL} manually."
            )

    def copy_code() -> None:
        code = state["code"]
        if not isinstance(code, str):
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(code, -1)
        clipboard.store()
        status_label.set_text("Code copied. Complete the sign-in in your browser.")

    def show_event(event: LoginEvent) -> bool:
        if not state["active"]:
            return False
        status_label.set_text(event.message)
        if event.code is not None:
            state["code"] = event.code
            code_label.set_text(event.code)
            code_box.set_no_show_all(False)
            code_box.show_all()
            copy_code()
            if noop_browser is not None and not state["browser_opened"]:
                open_browser()
        return False

    def finish(authenticated: bool, error: str | None) -> bool:
        if not state["active"]:
            return False
        state["error"] = error
        spinner.stop()
        dialog.response(Gtk.ResponseType.OK if authenticated else Gtk.ResponseType.REJECT)
        return False

    def worker() -> None:
        try:
            result = auth.login(
                sink=lambda event: GLib.idle_add(show_event, event),
                browser_command=noop_browser,
                cancel_event=cancel_event,
            )
            GLib.idle_add(finish, result.authenticated, result.error)
        except Exception as exc:  # noqa: BLE001 - worker/UI boundary
            GLib.idle_add(finish, False, str(exc))

    copy_button.connect("clicked", lambda _button: copy_code())
    browser_button.connect("clicked", lambda _button: open_browser())
    dialog.show_all()
    code_box.hide()
    threading.Thread(target=worker, name="github-login", daemon=True).start()

    response = dialog.run()
    state["active"] = False
    if response != Gtk.ResponseType.OK:
        cancel_event.set()
    authenticated = bool(response == Gtk.ResponseType.OK)
    error_message = state["error"]
    dialog.destroy()

    if not authenticated and response != Gtk.ResponseType.CANCEL and error_message:
        error = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="GitHub login failed",
        )
        error.format_secondary_text(str(error_message))
        error.run()
        error.destroy()
    return authenticated
