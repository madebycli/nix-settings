import pytest

from nix_settings.gui.layout import (
    HEADER_HEIGHT,
    MAX_HEIGHT,
    MAX_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    STREAM_ROUTE_MIN_WIDTH,
    STREAM_ROUTE_TARGET_WIDTH,
    TARGET_HEIGHT,
    TARGET_WIDTH,
    layout_mode,
    stream_route_width,
    window_size,
)


@pytest.mark.parametrize(
    ("workarea", "expected"),
    [
        ((1280, 720, 1), (987, 600)),
        ((1366, 768, 1), (1052, 640)),
        ((1920, 1080, 1), (1480, 900)),
        ((2560, 1440, 1), (1709, 1039)),
        ((3840, 2160, 1), (1840, 1120)),
        ((1440, 900, 2), (1110, 675)),
    ],
)
def test_responsive_monitor_geometry(
    workarea: tuple[int, int, int], expected: tuple[int, int]
) -> None:
    assert window_size(*workarea) == expected


def test_window_geometry_is_bounded_and_frozen() -> None:
    assert window_size(None, None) == (TARGET_WIDTH, TARGET_HEIGHT)
    for width, height, scale in (
        (1280, 720, 1),
        (1366, 768, 1),
        (1920, 1080, 1),
        (2560, 1440, 1),
        (3840, 2160, 1),
        (1440, 900, 2),
    ):
        first = window_size(width, height, scale)
        assert first == window_size(width, height, scale)
        assert MIN_WIDTH <= first[0] <= MAX_WIDTH
        assert MIN_HEIGHT <= first[1] <= MAX_HEIGHT
        assert first[0] <= width - 48
        assert first[1] <= height - 48


def test_header_height_is_page_independent() -> None:
    assert HEADER_HEIGHT == 52


def test_layout_breakpoint() -> None:
    assert layout_mode(987, 600) == "compact"
    assert layout_mode(1480, 900) == "normal"


def test_stream_route_preserves_sound_geometry() -> None:
    assert stream_route_width(TARGET_WIDTH) == STREAM_ROUTE_TARGET_WIDTH
    assert stream_route_width(1270) == STREAM_ROUTE_TARGET_WIDTH
    assert stream_route_width(1184) == 289
    assert stream_route_width(800) == STREAM_ROUTE_MIN_WIDTH
