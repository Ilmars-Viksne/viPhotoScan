# ruff: noqa: N802

import numpy as np
from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from photoscan.domain.models import Corner, OrderedCorners


class CornerEditor(QWidget):
    """
    Interactive widget that displays an image and overlays four draggable handle corners.
    Handles coordinate conversions and keeps positions normalized [0.0, 1.0].
    """
    corners_changed = Signal(object)  # Emits OrderedCorners

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.pixmap: QPixmap | None = None
        self.corners: OrderedCorners | None = None
        self.active_handle_idx: int = -1
        self.handle_radius: int = 12

    def set_image(self, pixmap: QPixmap, corners: OrderedCorners) -> None:
        """Sets the background image and resets corners overlay."""
        self.pixmap = pixmap
        self.corners = corners
        self.active_handle_idx = -1
        self.update()

    def get_corners(self) -> OrderedCorners | None:
        return self.corners

    def _get_image_rect(self) -> QRectF:
        """Calculates the rectangle where the scaled image actually sits inside the widget."""
        if not self.pixmap:
            return QRectF(self.rect())

        pw = self.pixmap.width()
        ph = self.pixmap.height()
        ww = self.width()
        wh = self.height()

        # Scale to fit
        scale = min(ww / pw, wh / ph)
        iw = pw * scale
        ih = ph * scale

        # Center
        ix = (ww - iw) / 2.0
        iy = (wh - ih) / 2.0
        return QRectF(ix, iy, iw, ih)

    def _norm_to_widget(self, norm_x: float, norm_y: float) -> QPoint:
        """Converts normalized [0.0, 1.0] coordinates to widget pixels."""
        rect = self._get_image_rect()
        wx = rect.x() + norm_x * rect.width()
        wy = rect.y() + norm_y * rect.height()
        return QPoint(int(wx), int(wy))

    def _widget_to_norm(self, wx: float, wy: float) -> tuple[float, float]:
        """Converts widget pixels back to normalized [0.0, 1.0] coordinates."""
        rect = self._get_image_rect()
        if rect.width() == 0 or rect.height() == 0:
            return 0.0, 0.0
        norm_x = (wx - rect.x()) / rect.width()
        norm_y = (wy - rect.y()) / rect.height()
        return float(np.clip(norm_x, 0.0, 1.0)), float(np.clip(norm_y, 0.0, 1.0))

    def _get_handle_positions(self) -> list[QPoint]:
        if not self.corners:
            return []
        return [
            self._norm_to_widget(self.corners.top_left.x, self.corners.top_left.y),
            self._norm_to_widget(self.corners.top_right.x, self.corners.top_right.y),
            self._norm_to_widget(self.corners.bottom_right.x, self.corners.bottom_right.y),
            self._norm_to_widget(self.corners.bottom_left.x, self.corners.bottom_left.y),
        ]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw the centered/scaled pixmap
        if self.pixmap:
            rect = self._get_image_rect()
            painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            # Draw placeholder state
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignCenter, "No document loaded.")
            return

        if not self.corners:
            return

        # 2. Draw connecting lines (the quadrilateral)
        handles = self._get_handle_positions()
        pen = QPen(QColor(46, 204, 113), 3, Qt.SolidLine)
        painter.setPen(pen)

        painter.drawLine(handles[0], handles[1])
        painter.drawLine(handles[1], handles[2])
        painter.drawLine(handles[2], handles[3])
        painter.drawLine(handles[3], handles[0])

        # 3. Draw draggable corner handles
        brush = QBrush(QColor(46, 204, 113, 150))
        painter.setBrush(brush)
        painter.setPen(QPen(QColor(255, 255, 255), 2))

        for idx, pt in enumerate(handles):
            if idx == self.active_handle_idx:
                painter.setBrush(QBrush(QColor(231, 76, 60, 200))) # Red when dragged
            else:
                painter.setBrush(brush)
            painter.drawEllipse(pt, self.handle_radius, self.handle_radius)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.corners:
            return

        handles = self._get_handle_positions()
        pos = event.position().toPoint()

        # Determine if a handle is clicked
        for idx, pt in enumerate(handles):
            dist = np.hypot(pt.x() - pos.x(), pt.y() - pos.y())
            if dist <= self.handle_radius + 5:
                self.active_handle_idx = idx
                self.update()
                break

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.active_handle_idx < 0 or not self.corners:
            return

        pos = event.position().toPoint()
        nx, ny = self._widget_to_norm(pos.x(), pos.y())

        # Safely assign back to active corner
        if self.active_handle_idx == 0:
            self.corners.top_left = Corner(x=nx, y=ny)
        elif self.active_handle_idx == 1:
            self.corners.top_right = Corner(x=nx, y=ny)
        elif self.active_handle_idx == 2:
            self.corners.bottom_right = Corner(x=nx, y=ny)
        elif self.active_handle_idx == 3:
            self.corners.bottom_left = Corner(x=nx, y=ny)

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.active_handle_idx >= 0:
            self.active_handle_idx = -1
            self.corners_changed.emit(self.corners)
            self.update()
