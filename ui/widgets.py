"""
ui/widgets.py
可复用 UI 组件：消息气泡、状态指示灯等
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from ui.theme import TOKENS


# ── 颜色主题 ──────────────────────────────────
COLORS = {
    "user_bg": "#0B1E3A",
    "user_border": TOKENS.neon_cyan,
    "ai_bg": "#180C2F",
    "ai_border": TOKENS.neon_purple,
    "system_bg": "#1D120A",
    "system_border": TOKENS.neon_orange,
    "text": TOKENS.text_0,
    "muted": TOKENS.text_2,
    "timestamp": TOKENS.text_2,
}


class MessageWidget(QFrame):
    """
    单条对话气泡
    role:   "user" | "assistant" | "system"
    source: "voice" | "text"
    """

    def __init__(self, role: str, content: str, timestamp: str = "", source: str = "text"):
        super().__init__()
        self.role = role
        self._content_label: QLabel | None = None
        self._build(role, content, timestamp, source)

    def _build(self, role: str, content: str, timestamp: str, source: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        # ── 样式 & 边距
        if role == "user":
            label = "你"
            self.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['user_bg']};
                    border: 1px solid {COLORS['user_border']};
                    border-radius: 12px;
                    margin: 2px 60px 2px 8px;
                }}
            """)
        elif role == "assistant":
            label = "助手"
            self.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['ai_bg']};
                    border: 1px solid {COLORS['ai_border']};
                    border-radius: 12px;
                    margin: 2px 8px 2px 60px;
                }}
            """)
        else:
            label = "系统"
            self.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['system_bg']};
                    border: 1px solid {COLORS['system_border']};
                    border-radius: 10px;
                    margin: 2px 80px 2px 80px;
                }}
            """)

        # ── Header（角色名 + 时间）
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color: {COLORS['muted']}; font-size: 11px; font-weight: 600; background: transparent; border: none;"
        )
        header.addWidget(name_lbl)
        header.addStretch()

        if timestamp:
            ts_lbl = QLabel(timestamp)
            ts_lbl.setStyleSheet(
                f"color: {COLORS['timestamp']}; font-size: 10px; background: transparent; border: none;"
            )
            header.addWidget(ts_lbl)

        layout.addLayout(header)

        # ── 内容
        self._content_label = QLabel(content)
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._content_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 14px; line-height: 1.6; background: transparent; border: none;"
        )
        layout.addWidget(self._content_label)

    def update_content(self, new_content: str):
        """流式更新文字内容（打字机效果）"""
        if self._content_label:
            self._content_label.setText(new_content)


class PulsingDot(QLabel):
    """录音状态指示灯（红色圆点，用 CSS animation 模拟）"""

    def __init__(self):
        super().__init__("●")
        self.setStyleSheet("""
            QLabel {
                color: #fc8181;
                font-size: 14px;
                padding: 0 4px;
            }
        """)
        self.setVisible(False)

    def set_active(self, active: bool):
        self.setVisible(active)
