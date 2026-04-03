from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QObject, QEvent, QPropertyAnimation, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


class NeonGlow(QObject):
    def __init__(
        self,
        target: QWidget,
        base_color: QColor,
        hover_color: QColor,
        active_color: QColor,
    ):
        super().__init__(target)
        self._target = target
        self._base_color = base_color
        self._hover_color = hover_color
        self._active_color = active_color
        self._active = False

        effect = QGraphicsDropShadowEffect(target)
        effect.setOffset(0, 0)
        effect.setBlurRadius(0)
        effect.setColor(self._with_alpha(self._base_color, 0))
        target.setGraphicsEffect(effect)
        self._effect = effect

        self._blur_anim = QPropertyAnimation(effect, b"blurRadius", self)
        self._blur_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._blur_anim.setDuration(180)

        self._alpha_timer = QTimer(self)
        self._alpha_timer.setInterval(16)
        self._alpha_timer.timeout.connect(self._tick_pulse)
        self._pulse_phase = 0.0

        target.installEventFilter(self)

    @staticmethod
    def _with_alpha(c: QColor, alpha: int) -> QColor:
        out = QColor(c)
        out.setAlpha(max(0, min(255, alpha)))
        return out

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        if active:
            self._pulse_phase = 0.0
            self._alpha_timer.start()
            self._animate_to(28, 170, self._active_color)
        else:
            self._alpha_timer.stop()
            self._animate_to(0, 0, self._base_color)

    def _animate_to(self, blur: int, alpha: int, color: QColor) -> None:
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._effect.blurRadius())
        self._blur_anim.setEndValue(float(blur))
        self._blur_anim.start()
        self._effect.setColor(self._with_alpha(color, alpha))

    def _tick_pulse(self) -> None:
        self._pulse_phase += 0.06
        if self._pulse_phase > 6.283:
            self._pulse_phase -= 6.283

        import math

        t = (math.sin(self._pulse_phase) + 1.0) * 0.5
        alpha = int(110 + 90 * t)
        blur = float(22 + 10 * t)
        self._effect.setBlurRadius(blur)
        self._effect.setColor(self._with_alpha(self._active_color, alpha))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._target and not self._active:
            if event.type() == QEvent.Enter:
                self._animate_to(22, 140, self._hover_color)
            elif event.type() == QEvent.Leave:
                self._animate_to(0, 0, self._base_color)
            elif event.type() == QEvent.MouseButtonPress:
                self._animate_to(14, 120, self._hover_color)
            elif event.type() == QEvent.MouseButtonRelease:
                self._animate_to(22, 140, self._hover_color)
        return False

