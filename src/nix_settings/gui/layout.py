from __future__ import annotations

TARGET_WIDTH = 1040
TARGET_HEIGHT = 760
MIN_WIDTH = 760
MIN_HEIGHT = 560
MONITOR_X_MARGIN = 80
MONITOR_Y_MARGIN = 100
HEADER_HEIGHT = 44
CARD_SPACING = 10
CONTENT_SPACING = 12
CONTROL_HEIGHT = 34
CARD_RADIUS = 10
WINDOW_RADIUS = 12


def window_size(monitor_width: int | None, monitor_height: int | None) -> tuple[int, int]:
    width = TARGET_WIDTH
    height = TARGET_HEIGHT
    if monitor_width is not None:
        width = min(TARGET_WIDTH, max(MIN_WIDTH, monitor_width - MONITOR_X_MARGIN))
    if monitor_height is not None:
        height = min(TARGET_HEIGHT, max(MIN_HEIGHT, monitor_height - MONITOR_Y_MARGIN))
    return width, height
