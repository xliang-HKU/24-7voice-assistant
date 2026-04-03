from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap, QColor


def _pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    return pm


def mic_icon(size: int = 22, color: QColor | str = "#070A14") -> QIcon:
    if isinstance(color, str):
        color = QColor(color)

    pm = _pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    w = max(2.0, size * 0.10)
    pen = QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    cx = size * 0.5
    top = size * 0.20
    body_w = size * 0.34
    body_h = size * 0.44
    body_x = cx - body_w / 2
    body_y = top
    r = body_w * 0.50

    body = QPainterPath()
    body.addRoundedRect(body_x, body_y, body_w, body_h, r, r)
    p.drawPath(body)

    arc_x = cx - body_w * 0.72
    arc_y = top + body_h * 0.33
    arc_w = body_w * 1.44
    arc_h = body_h * 0.92
    p.drawArc(int(arc_x), int(arc_y), int(arc_w), int(arc_h), 0, -180 * 16)

    stem_top = top + body_h + size * 0.04
    stem_bottom = size * 0.86
    p.drawLine(int(cx), int(stem_top), int(cx), int(stem_bottom))

    base_w = size * 0.36
    p.drawLine(int(cx - base_w / 2), int(stem_bottom), int(cx + base_w / 2), int(stem_bottom))

    p.end()
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Selected)
    return icon


def stop_icon(size: int = 22, color: QColor | str = "#070A14") -> QIcon:
    if isinstance(color, str):
        color = QColor(color)

    pm = _pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    w = max(2.0, size * 0.10)
    pen = QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    inset = size * 0.26
    side = size - inset * 2
    p.drawRoundedRect(inset, inset, side, side, size * 0.12, size * 0.12)

    p.end()
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Selected)
    return icon


def icon_size_for_button(bp: str) -> QSize:
    if bp == "sm":
        return QSize(20, 20)
    if bp == "md":
        return QSize(22, 22)
    return QSize(24, 24)

