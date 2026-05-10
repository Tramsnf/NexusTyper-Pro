"""Lucide-style icon helpers for NexusTyper Pro.

``LUCIDE_PATHS`` maps short icon names to SVG path data (24x24 viewBox,
stroke-width 2, round caps/joins).  Pass a name to ``make_lucide_icon`` to
get a tinted ``QIcon``.
"""
from nexustyper.services.logging_setup import _log_caught

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter


# Lucide-style icon paths (24x24 viewBox). Stroke 2, round caps/joins.
# Render with `make_lucide_icon(name, color, size)` to get a tinted QIcon.
LUCIDE_PATHS = {
    # folder-open
    "open": "M6 14l1.5-2.9A2 2 0 0 1 9.3 10H21l-2.5 6.1A2 2 0 0 1 16.7 17H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.7 1l.8 1a2 2 0 0 0 1.7 1H18a2 2 0 0 1 2 2v2",
    # save (floppy)
    "save": "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8 M7 3v5h8",
    # wand-sparkles (format)
    "format": "M15 4V2 M15 16v-2 M8 9h2 M20 9h2 M17.8 11.8 19 13 M15 9h0 M17.8 6.2 19 5 M3 21l9-9 M12.2 6.2 11 5",
    # code-2 (macros / code)
    "macros": "m18 16 4-4-4-4 M6 8l-4 4 4 4 M14.5 4l-5 16",
    # eraser (clean)
    "clean": "m7 21-4.3-4.3a1 1 0 0 1 0-1.4l9.6-9.6a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L13 21 M22 21H7 M5 11l9 9",
    # x (clear / trash-ish)
    "clear": "M18 6 6 18 M6 6l12 12",
    # play (start)
    "play": "M6 3v18l15-9z",
    # pause (two bars)
    "pause": "M14 4h4v16h-4z M6 4h4v16H6z",
    # square (stop)
    "stop": "M5 5h14v14H5z",
    # info
    "info": "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z M12 8h0 M11 12h1v4h1",
    # settings
    "settings": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
}


def make_lucide_icon(name, color="#94A3B8", size=20, stroke_width=1.8):
    """Render a Lucide-style icon to a QIcon, tinted to ``color``.

    Uses QSvgRenderer so SVG arc/bezier commands (which Lucide relies on)
    render correctly.
    """
    path_data = LUCIDE_PATHS.get(name)
    if not path_data:
        return QIcon()
    filled = name in ("play", "stop", "pause")
    if filled:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path d="{path_data}" fill="{color}" stroke="none"/></svg>'
        )
    else:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path d="{path_data}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg>'
        )
    try:
        from PyQt5.QtSvg import QSvgRenderer
    except Exception:
        _log_caught('make_lucide_icon@L64')
        return QIcon()
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    renderer = QSvgRenderer(svg.encode("utf-8"))
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter)
    finally:
        painter.end()
    return QIcon(pix)


