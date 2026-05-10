"""Splitter widgets with a clickable chevron handle.

The handle paints a small chevron in the middle and emits a ``toggleRequested``
signal on click (without drag) so callers can collapse/expand the sidebar
without forcing the user to drag a 1-px hit target. The chevron flips
direction based on whether the left pane is collapsed, giving the user a
clear "click here to show/hide" affordance even when the sidebar has been
dragged to zero width.

``ToggleSplitter`` is the public name for the splitter; ``ChevronSplitter``
is kept as a backwards-compatible alias because the original monolithic
script used that name.
"""

from __future__ import annotations
from nexustyper.services.logging_setup import _log_caught

from PyQt5.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QSplitter, QSplitterHandle


class ChevronSplitterHandle(QSplitterHandle):
    """A splitter handle that paints a small chevron in the middle.

    The chevron flips direction based on whether the left pane is collapsed,
    giving the user a clear "click here to show/hide" affordance even when the
    sidebar has been dragged to zero width. Clicking the handle (without
    dragging) calls ``request_toggle()`` on the parent splitter.
    """

    HANDLE_WIDTH = 14

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._press_pos = None
        self._hovered = False

    def sizeHint(self):
        return QSize(self.HANDLE_WIDTH, super().sizeHint().height())

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # If the mouse barely moved between press and release, treat it as a
        # click and ask the parent splitter to toggle.
        try:
            moved = (
                self._press_pos is None
                or (event.pos() - self._press_pos).manhattanLength() > 4
            )
        except Exception:
            _log_caught('mouseReleaseEvent@L64')
            moved = True
        super().mouseReleaseEvent(event)
        self._press_pos = None
        if not moved:
            sp = self.splitter()
            if hasattr(sp, "request_toggle"):
                sp.request_toggle()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        # Determine collapsed state from sibling sizes.
        sp = self.splitter()
        sizes = sp.sizes() if sp else [1, 1]
        collapsed = bool(sizes) and sizes[0] <= 1
        # Theme-aware colors via app palette / stylesheet sniff.
        app = QApplication.instance()
        is_dark = False
        try:
            ss = app.styleSheet() if app else ""
            is_dark = "DARK" in ss[:120].upper() or "#0F172A" in ss[:200]
        except Exception:
            _log_caught('paintEvent@L88')
            pass
        accent = QColor("#06B6D4")
        rail = QColor("#1E293B" if is_dark else "#E2E8F0")
        chevron = QColor(accent if (self._hovered or collapsed) else
                         QColor("#64748B" if is_dark else "#94A3B8"))
        # Subtle center spine instead of filling the whole 14px handle — keeps
        # the splitter quiet so it doesn't compete with the scrollbar next to it.
        cx = rect.center().x()
        cy = rect.center().y()
        spine_w = 1
        spine_h = max(rect.height() - 24, 0)
        if self._hovered or collapsed:
            spine_color = QColor(accent)
            spine_color.setAlphaF(0.30 if not collapsed else 0.55)
            painter.fillRect(int(cx - spine_w / 2), int(cy - spine_h / 2),
                             spine_w, spine_h, spine_color)
        else:
            spine_color = QColor(rail)
            spine_color.setAlphaF(0.7)
            painter.fillRect(int(cx - spine_w / 2), int(cy - spine_h / 2),
                             spine_w, spine_h, spine_color)
        # Chevron — 5px wide, 10px tall, pointing left when expanded,
        # right when collapsed.
        pen = QPen(chevron)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        if collapsed:
            path.moveTo(cx - 2.5, cy - 5)
            path.lineTo(cx + 2.5, cy)
            path.lineTo(cx - 2.5, cy + 5)
        else:
            path.moveTo(cx + 2.5, cy - 5)
            path.lineTo(cx - 2.5, cy)
            path.lineTo(cx + 2.5, cy + 5)
        painter.drawPath(path)
        # A subtle dot pair above and below the chevron acts as a grip
        # indicator.
        dot = QColor(chevron)
        dot.setAlphaF(0.55)
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot)
        for dy in (-14, 14):
            painter.drawEllipse(QPoint(cx, cy + dy), 1, 1)
        painter.end()


class ToggleSplitter(QSplitter):
    """Horizontal splitter that uses :class:`ChevronSplitterHandle`.

    Emits ``toggleRequested`` when the user clicks (without dragging) on the
    handle. The owning controller decides what "toggle" means — typically
    collapse/expand the left pane.
    """

    toggleRequested = pyqtSignal()

    def createHandle(self):
        return ChevronSplitterHandle(self.orientation(), self)

    def request_toggle(self):
        self.toggleRequested.emit()


# Backwards-compatible alias for the original name used in the script.
ChevronSplitter = ToggleSplitter


__all__ = ["ChevronSplitterHandle", "ToggleSplitter", "ChevronSplitter"]


