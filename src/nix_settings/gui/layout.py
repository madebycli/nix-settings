from __future__ import annotations

TARGET_WIDTH = 1416
TARGET_HEIGHT = 980
MIN_WIDTH = 720
MIN_HEIGHT = 560
MONITOR_X_MARGIN = 120
MONITOR_Y_MARGIN = 160
NAVIGATION_WIDTH = 220
HEADER_HEIGHT = 44
CARD_SPACING = 12
CONTENT_SPACING = 14
CONTROL_HEIGHT = 36
LOG_AREA_HEIGHT = 260
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
