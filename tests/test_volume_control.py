from nix_settings.gui.widgets.volume_control import VolumeControl


def test_percent_text_is_clamped_and_dynamic() -> None:
    assert VolumeControl._percent_text(-5) == "0%"
    assert VolumeControl._percent_text(42.4) == "42%"
    assert VolumeControl._percent_text(99.6) == "100%"
    assert VolumeControl._percent_text(130) == "100%"
