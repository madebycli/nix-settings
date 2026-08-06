from nix_settings.gui.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    STREAM_ROUTE_MIN_WIDTH,
    STREAM_ROUTE_TARGET_WIDTH,
    TARGET_HEIGHT,
    TARGET_WIDTH,
    stream_route_width,
    window_size,
)


def test_window_size_is_monitor_bounded() -> None:
    assert window_size(None, None) == (TARGET_WIDTH, TARGET_HEIGHT)
    assert window_size(800, 650) == (MIN_WIDTH, MIN_HEIGHT)
    assert window_size(4000, 3000) == (TARGET_WIDTH, TARGET_HEIGHT)


def test_stream_route_uses_librewolf_width_when_space_allows() -> None:
    assert stream_route_width(TARGET_WIDTH) == STREAM_ROUTE_TARGET_WIDTH
    assert stream_route_width(1270) == STREAM_ROUTE_TARGET_WIDTH


def test_stream_route_shrinks_only_for_narrow_windows() -> None:
    assert stream_route_width(1184) == 289
    assert stream_route_width(800) == STREAM_ROUTE_MIN_WIDTH
