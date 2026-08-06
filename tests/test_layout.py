from nix_settings.gui.layout import MIN_HEIGHT, MIN_WIDTH, TARGET_HEIGHT, TARGET_WIDTH, window_size


def test_window_size_is_monitor_bounded() -> None:
    assert window_size(None, None) == (TARGET_WIDTH, TARGET_HEIGHT)
    assert window_size(800, 650) == (MIN_WIDTH, MIN_HEIGHT)
    assert window_size(4000, 3000) == (TARGET_WIDTH, TARGET_HEIGHT)
