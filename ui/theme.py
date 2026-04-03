from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ThemeTokens:
    bg_0: str = "#070A14"
    bg_1: str = "#0B1020"
    surface_0: str = "#0E1733"
    surface_1: str = "#0A1228"
    text_0: str = "#EAF1FF"
    text_1: str = "#A8B7DB"
    text_2: str = "#7C8DB8"

    neon_cyan: str = "#00F5FF"
    neon_purple: str = "#B44BFF"
    neon_green: str = "#00FFA8"
    neon_orange: str = "#FF7A45"

    danger: str = "#FF4D6D"

    radius_l: int = 26
    radius_m: int = 20
    radius_s: int = 14


TOKENS = ThemeTokens()


def qcolor(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def app_stylesheet(tokens: ThemeTokens = TOKENS) -> str:
    r_l = tokens.radius_l
    r_m = tokens.radius_m
    r_s = tokens.radius_s
    return f"""
        QMainWindow, QWidget#root {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {tokens.bg_1},
                stop:1 {tokens.bg_0}
            );
            color: {tokens.text_0};
            font-family: "PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
        }}

        QWidget#root[bp="sm"] {{
            font-size: 13px;
        }}
        QWidget#root[bp="md"] {{
            font-size: 14px;
        }}
        QWidget#root[bp="lg"] {{
            font-size: 15px;
        }}

        QFrame[card="true"] {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(14, 23, 51, 245),
                stop:1 rgba(10, 18, 40, 245)
            );
            border: 1px solid rgba(0, 245, 255, 46);
            border-radius: {r_l}px;
        }}

        QLabel[role="appTitle"] {{
            color: {tokens.text_0};
            font-weight: 900;
            letter-spacing: 0.5px;
        }}
        QWidget#root[bp="sm"] QLabel[role="appTitle"] {{ font-size: 26px; }}
        QWidget#root[bp="md"] QLabel[role="appTitle"] {{ font-size: 30px; }}
        QWidget#root[bp="lg"] QLabel[role="appTitle"] {{ font-size: 34px; }}

        QLabel[role="subtitle"] {{
            color: {tokens.text_1};
            line-height: 1.6;
        }}
        QWidget#root[bp="sm"] QLabel[role="subtitle"] {{ font-size: 15px; }}
        QWidget#root[bp="md"] QLabel[role="subtitle"] {{ font-size: 16px; }}
        QWidget#root[bp="lg"] QLabel[role="subtitle"] {{ font-size: 18px; }}

        QLabel[role="cardTitle"] {{
            color: {tokens.text_0};
            font-weight: 800;
            letter-spacing: 0.3px;
        }}
        QWidget#root[bp="sm"] QLabel[role="cardTitle"] {{ font-size: 18px; }}
        QWidget#root[bp="md"] QLabel[role="cardTitle"] {{ font-size: 19px; }}
        QWidget#root[bp="lg"] QLabel[role="cardTitle"] {{ font-size: 20px; }}

        QLabel[role="state"] {{
            color: {tokens.neon_orange};
            font-weight: 800;
            line-height: 1.45;
        }}
        QWidget#root[bp="sm"] QLabel[role="state"] {{ font-size: 18px; }}
        QWidget#root[bp="md"] QLabel[role="state"] {{ font-size: 20px; }}
        QWidget#root[bp="lg"] QLabel[role="state"] {{ font-size: 22px; }}

        QLabel[role="meta"] {{
            color: {tokens.text_2};
            line-height: 1.7;
        }}
        QWidget#root[bp="sm"] QLabel[role="meta"] {{ font-size: 12px; }}
        QWidget#root[bp="md"] QLabel[role="meta"] {{ font-size: 13px; }}
        QWidget#root[bp="lg"] QLabel[role="meta"] {{ font-size: 14px; }}

        QLabel[role="footer"] {{
            color: rgba(168, 183, 219, 160);
            font-size: 12px;
        }}

        QPlainTextEdit[role="reminderBox"] {{
            background: rgba(7, 10, 20, 190);
            color: {tokens.text_0};
            border: 1px solid rgba(180, 75, 255, 48);
            border-radius: {r_m}px;
            padding: 12px;
            font-size: 15px;
            line-height: 1.75;
            selection-background-color: rgba(0, 245, 255, 70);
            selection-color: {tokens.text_0};
        }}

        QLabel[role="liveUser"] {{
            background: rgba(0, 245, 255, 18);
            color: {tokens.text_0};
            border: 1px solid rgba(0, 245, 255, 44);
            border-radius: {r_m}px;
            padding: 18px;
            line-height: 1.7;
        }}
        QLabel[role="liveAssistant"] {{
            background: rgba(180, 75, 255, 18);
            color: {tokens.text_0};
            border: 1px solid rgba(180, 75, 255, 44);
            border-radius: {r_m}px;
            padding: 18px;
            line-height: 1.7;
        }}
        QWidget#root[bp="sm"] QLabel[role="liveUser"], QWidget#root[bp="sm"] QLabel[role="liveAssistant"] {{
            font-size: 16px;
            padding: 14px;
        }}
        QWidget#root[bp="md"] QLabel[role="liveUser"], QWidget#root[bp="md"] QLabel[role="liveAssistant"] {{
            font-size: 18px;
        }}
        QWidget#root[bp="lg"] QLabel[role="liveUser"], QWidget#root[bp="lg"] QLabel[role="liveAssistant"] {{
            font-size: 20px;
        }}

        QPushButton[variant="primary"] {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(0, 245, 255, 210),
                stop:0.5 rgba(180, 75, 255, 210),
                stop:1 rgba(0, 255, 168, 210)
            );
            color: {tokens.bg_0};
            border: 1px solid rgba(0, 245, 255, 110);
            border-radius: {r_l}px;
            font-weight: 900;
            letter-spacing: 0.8px;
        }}
        QWidget#root[bp="sm"] QPushButton[variant="primary"] {{ font-size: 22px; }}
        QWidget#root[bp="md"] QPushButton[variant="primary"] {{ font-size: 25px; }}
        QWidget#root[bp="lg"] QPushButton[variant="primary"] {{ font-size: 28px; }}

        QPushButton[variant="primary"]:hover {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(0, 245, 255, 235),
                stop:0.5 rgba(180, 75, 255, 235),
                stop:1 rgba(0, 255, 168, 235)
            );
            border: 1px solid rgba(0, 245, 255, 160);
        }}

        QPushButton[variant="primary"][state="active"] {{
            color: {tokens.text_0};
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(255, 122, 69, 220),
                stop:0.5 rgba(180, 75, 255, 220),
                stop:1 rgba(0, 245, 255, 220)
            );
            border: 1px solid rgba(255, 122, 69, 170);
        }}

        QPushButton[variant="primary"]:disabled {{
            background: rgba(124, 141, 184, 50);
            color: rgba(234, 241, 255, 120);
            border: 1px solid rgba(124, 141, 184, 60);
        }}

        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 8px 4px 8px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(0, 245, 255, 80);
            border-radius: 5px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(0, 245, 255, 120);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            width: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QPlainTextEdit {{
            outline: none;
        }}

        QPlainTextEdit:focus {{
            border: 1px solid rgba(0, 245, 255, 120);
        }}
    """
