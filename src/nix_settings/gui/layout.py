from __future__ import annotations

TARGET_WIDTH = 1480
TARGET_HEIGHT = 900
MIN_WIDTH = 720
MIN_HEIGHT = 560
MONITOR_X_MARGIN = 96
MONITOR_Y_MARGIN = 96
HEADER_HEIGHT = 52
CARD_SPACING = 10
CONTENT_SPACING = 12
CONTROL_HEIGHT = 30
CARD_RADIUS = 10
WINDOW_RADIUS = 14

# The 300 logical-pixel selector is the geometry shown by the LibreWolf row
# on the reference monitor. It remains fixed at that width whenever the panel
# has enough room and only shrinks on genuinely narrow displays.
STREAM_ROUTE_TARGET_WIDTH = 300
STREAM_ROUTE_MIN_WIDTH = 160
STREAM_APP_MIN_WIDTH = 190
STREAM_ROUTE_LABEL_WIDTH = 46
STREAM_ROUTE_LABEL_GAP = 8
STREAM_ROW_COLUMN_GAP = 12
CONTENT_HORIZONTAL_PADDING = 28
MAIN_GRID_GAP = 10
CARD_HORIZONTAL_PADDING = 20
STREAM_ROWS_RIGHT_MARGIN = 8


def window_size(monitor_width: int | None, monitor_height: int | None) -> tuple[int, int]:
    width = TARGET_WIDTH
    height = TARGET_HEIGHT
    if monitor_width is not None:
        width = min(TARGET_WIDTH, max(MIN_WIDTH, monitor_width - MONITOR_X_MARGIN))
    if monitor_height is not None:
        height = min(TARGET_HEIGHT, max(MIN_HEIGHT, monitor_height - MONITOR_Y_MARGIN))
    return width, height


def stream_route_width(window_width: int) -> int:
    """Return the fixed LibreWolf route width with a narrow-monitor fallback."""
    panel_width = (window_width - CONTENT_HORIZONTAL_PADDING - MAIN_GRID_GAP) // 2
    row_width = panel_width - CARD_HORIZONTAL_PADDING - STREAM_ROWS_RIGHT_MARGIN
    available = (
        row_width
        - STREAM_APP_MIN_WIDTH
        - STREAM_ROW_COLUMN_GAP
        - STREAM_ROUTE_LABEL_WIDTH
        - STREAM_ROUTE_LABEL_GAP
    )
    return max(STREAM_ROUTE_MIN_WIDTH, min(STREAM_ROUTE_TARGET_WIDTH, available))
