from __future__ import annotations

import math

TARGET_WIDTH = 1480
TARGET_HEIGHT = 900
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080
MIN_WIDTH = 720
MIN_HEIGHT = 560
MAX_WIDTH = 1840
MAX_HEIGHT = 1120
MONITOR_MARGIN = 48
HEADER_HEIGHT = 52
CARD_SPACING = 10
CONTENT_SPACING = 12
CONTROL_HEIGHT = 30
CARD_RADIUS = 10
WINDOW_RADIUS = 14
COMPACT_BREAKPOINT_WIDTH = 1500
COMPACT_BREAKPOINT_HEIGHT = 850

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


def window_size(
    workarea_width: int | None,
    workarea_height: int | None,
    scale_factor: int = 1,
) -> tuple[int, int]:
    """Return one frozen logical window size for a GDK monitor workarea.

    GDK workareas are already expressed in logical pixels under Wayland. The
    scale factor is accepted explicitly so callers and tests cannot accidentally
    feed physical pixels; it is validated but intentionally not applied twice.
    """
    if workarea_width is None or workarea_height is None:
        return TARGET_WIDTH, TARGET_HEIGHT
    if workarea_width <= 0 or workarea_height <= 0:
        return TARGET_WIDTH, TARGET_HEIGHT
    if scale_factor < 1:
        raise ValueError("scale_factor must be at least 1")

    relative = min(workarea_width / REFERENCE_WIDTH, workarea_height / REFERENCE_HEIGHT)
    compact = (
        workarea_width < COMPACT_BREAKPOINT_WIDTH
        or workarea_height < COMPACT_BREAKPOINT_HEIGHT
    )
    if compact:
        growth = relative
    elif relative <= 1.0:
        growth = relative
    else:
        growth = math.sqrt(relative)

    width = round(TARGET_WIDTH * growth)
    height = round(TARGET_HEIGHT * growth)
    width = min(MAX_WIDTH, max(MIN_WIDTH, width), max(MIN_WIDTH, workarea_width - MONITOR_MARGIN))
    height = min(
        MAX_HEIGHT,
        max(MIN_HEIGHT, height),
        max(MIN_HEIGHT, workarea_height - MONITOR_MARGIN),
    )
    width = min(width, max(1, workarea_width - MONITOR_MARGIN))
    height = min(height, max(1, workarea_height - MONITOR_MARGIN))
    return width, height


def layout_mode(window_width: int, window_height: int) -> str:
    if window_width < 1160 or window_height < 700:
        return "compact"
    return "normal"


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
