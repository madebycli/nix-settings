from pathlib import Path


def test_desktop_entry_opens_overview() -> None:
    text = Path("data/com.madebycli.NixSettings.desktop").read_text(encoding="utf-8")
    assert "Exec=nix-settings\n" in text
    assert "Terminal=false" in text


def test_no_gtk4_or_nonhermetic_python_references() -> None:
    files = [*Path("src").rglob("*.py")]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "Gtk4" not in text
    assert "Gtk-4.0" not in text
    assert "/usr/bin/python" not in text
    assert "shell=True" not in text


def test_window_keeps_sound_as_existing_page() -> None:
    text = Path("src/nix_settings/gui/window.py").read_text(encoding="utf-8")
    assert "from nix_settings.gui.pages.sound import SoundPage" in text
    assert "self.sound_page = SoundPage" in text
