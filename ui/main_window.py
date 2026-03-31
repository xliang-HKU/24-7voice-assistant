"""
ui/main_window.py
主窗口 —— 三个独立按钮：录音 / AI对话 / 查询历史
"""
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QComboBox,
    QScrollArea, QGroupBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

from config import (
    APP_NAME, APP_VERSION,
    WINDOW_MIN_W, WINDOW_MIN_H,
    MEMORY_RESTORE_RECENT,
    DEEPSEEK_API_KEY,
)
from core.memory import MemoryManager
from core.ai import AIProcessor
from core.stt import STTThread
from ui.widgets import MessageWidget, PulsingDot


# ── AI 回复线程 ───────────────────────────────

class AIThread(QThread):
    chunk_ready = Signal(str)
    reply_done  = Signal(str)

    def __init__(self, ai: AIProcessor, message: str, mode: str = "chat"):
        super().__init__()
        self.ai      = ai
        self.message = message
        self.mode    = mode

    def run(self):
        full = ""
        def on_chunk(text: str):
            nonlocal full
            full += text
            self.chunk_ready.emit(text)

        if self.mode == "search":
            result = self.ai.search_and_reply(self.message, on_chunk=on_chunk)
        else:
            result = self.ai.chat(self.message, on_chunk=on_chunk)
        self.reply_done.emit(full or result)


# ── 主窗口 ────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.memory = MemoryManager()
        self.ai     = AIProcessor(self.memory, api_key=DEEPSEEK_API_KEY)
        self.stt    = STTThread()

        self.is_recording             = False
        self.ai_thread: Optional[AIThread]           = None
        self._cur_ai_widget: Optional[MessageWidget] = None
        self._cur_ai_text                            = ""

        self._setup_ui()
        self._connect_signals()
        self._load_mic_devices()
        self._restore_history()
        self._add_system_msg(
            f"欢迎使用 {APP_NAME} v{APP_VERSION}\n"
            "• 🎙️ 录音：开始/停止实时语音转文字\n"
            "• 🤖 AI 对话：将输入内容发送给 AI\n"
            "• 🔍 查询历史：搜索历史记录并整理回复\n"
            f"• 已加载 {self.memory.total} 条历史记录"
        )

    # ══════════════════════════════════════════
    # UI 构建
    # ══════════════════════════════════════════

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_W, WINDOW_MIN_H)
        self.resize(1100, 760)
        self.setStyleSheet(self._app_style())

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_main_area(), 1)

        self.statusBar().setStyleSheet(
            "QStatusBar { background:#161b22; color:#666; font-size:11px; }"
        )
        self.statusBar().showMessage("就绪")

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(220)
        sb.setStyleSheet("QWidget { background:#161b22; border-right:1px solid #21262d; }")
        lay = QVBoxLayout(sb)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(10)

        # Logo
        logo = QLabel(f"🎙️  {APP_NAME}")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("color:#58a6ff; font-size:15px; font-weight:700; padding:6px 0;")
        lay.addWidget(logo)

        # ── 三个核心按钮 ──
        self.record_btn = QPushButton("🎙️  开始录音")
        self.record_btn.setFixedHeight(46)
        self.record_btn.setStyleSheet(self._btn("#238636", "#2ea043"))
        self.record_btn.setToolTip("开始/停止实时语音转文字")
        lay.addWidget(self.record_btn)

        self.ai_btn = QPushButton("🤖  AI 对话")
        self.ai_btn.setFixedHeight(46)
        self.ai_btn.setStyleSheet(self._btn("#1f6feb", "#388bfd"))
        self.ai_btn.setToolTip("将输入框内容发送给 AI 助手")
        lay.addWidget(self.ai_btn)

        self.search_btn = QPushButton("🔍  查询历史")
        self.search_btn.setFixedHeight(46)
        self.search_btn.setStyleSheet(self._btn("#6e40c9", "#8957e5"))
        self.search_btn.setToolTip("搜索历史记录并由 AI 整理回复")
        lay.addWidget(self.search_btn)

        # 实时识别预览
        partial_group = self._group("实时识别")
        pg_lay = QVBoxLayout(partial_group)
        self.partial_label = QLabel("（等待语音...）")
        self.partial_label.setWordWrap(True)
        self.partial_label.setMinimumHeight(60)
        self.partial_label.setStyleSheet(
            "color:#8b949e; font-size:12px; font-style:italic;"
        )
        pg_lay.addWidget(self.partial_label)
        lay.addWidget(partial_group)

        # 麦克风
        mic_group = self._group("麦克风")
        mg_lay = QVBoxLayout(mic_group)
        self.mic_combo = QComboBox()
        self.mic_combo.setStyleSheet(self._combo_style())
        mg_lay.addWidget(self.mic_combo)
        lay.addWidget(mic_group)

        lay.addStretch()

        # 统计
        self.stats_label = QLabel()
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.stats_label.setStyleSheet("color:#4a5568; font-size:10px;")
        self._refresh_stats()
        lay.addWidget(self.stats_label)

        return sb

    def _build_main_area(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_header())

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("QScrollArea { border:none; background:#0d1117; }")

        self.chat_container = QWidget()
        self.chat_layout    = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(6)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        lay.addWidget(self.chat_scroll, 1)
        lay.addWidget(self._build_input_bar())
        return w

    def _build_header(self) -> QWidget:
        h = QWidget()
        h.setFixedHeight(48)
        h.setStyleSheet("background:#161b22; border-bottom:1px solid #21262d;")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel("💬 对话")
        title.setStyleSheet("color:#c9d1d9; font-size:14px; font-weight:600;")
        lay.addWidget(title)
        lay.addStretch()

        self.pulsing_dot = PulsingDot()
        lay.addWidget(self.pulsing_dot)

        clear_btn = QPushButton("清空对话")
        clear_btn.setFixedHeight(30)
        clear_btn.setStyleSheet(self._btn("#30363d", "#3f4954"))
        clear_btn.clicked.connect(self._clear_chat)
        lay.addWidget(clear_btn)

        return h

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#161b22; border-top:1px solid #21262d;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText(
            "输入文字，或用左侧录音按钮… (Enter = AI 对话)"
        )
        self.text_input.setFixedHeight(42)
        self.text_input.setStyleSheet("""
            QLineEdit {
                background:#0d1117; color:#c9d1d9;
                border:1px solid #30363d; border-radius:8px;
                padding:0 12px; font-size:14px;
            }
            QLineEdit:focus { border-color:#58a6ff; }
        """)
        lay.addWidget(self.text_input, 1)
        return bar

    # ══════════════════════════════════════════
    # 信号 & 槽
    # ══════════════════════════════════════════

    def _connect_signals(self):
        self.record_btn.clicked.connect(self._toggle_recording)
        self.ai_btn.clicked.connect(self._on_ai_btn)
        self.search_btn.clicked.connect(self._on_search_btn)
        self.text_input.returnPressed.connect(self._on_ai_btn)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)

        self.stt.text_partial.connect(self._on_partial)
        self.stt.text_final.connect(self._on_stt_final)
        self.stt.error.connect(self._on_stt_error)

    def _load_mic_devices(self):
        for idx, name in STTThread.list_devices():
            self.mic_combo.addItem(name[:34], idx)

    def _on_mic_changed(self, combo_idx: int):
        device_idx = self.mic_combo.itemData(combo_idx)
        if device_idx is not None:
            self.stt.set_device(device_idx)

    # ── 录音 ──────────────────────────────────

    def _toggle_recording(self):
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.is_recording = True
        self.record_btn.setText("⏹  停止录音")
        self.record_btn.setStyleSheet(self._btn("#da3633", "#f85149"))
        self.pulsing_dot.set_active(True)
        self.statusBar().showMessage("🔴 录音中…")
        self.partial_label.setText("（聆听中...）")
        self.stt.start_recording()

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.setText("🎙️  开始录音")
        self.record_btn.setStyleSheet(self._btn("#238636", "#2ea043"))
        self.pulsing_dot.set_active(False)
        self.statusBar().showMessage("就绪")
        self.partial_label.setText("（等待语音...）")
        self.stt.stop_recording()

    # ── STT 事件 ──────────────────────────────

    def _on_partial(self, text: str):
        self.partial_label.setText(text)
        self.text_input.setText(text)

    def _on_stt_final(self, text: str):
        """语音识别完成：只记录和显示，不自动调用 AI"""
        self.partial_label.setText("（等待下一句...）")
        self.text_input.setText(text)
        ts = datetime.now().strftime("%H:%M")
        self.memory.add("user", text, source="voice")
        self._refresh_stats()
        self._insert_msg(MessageWidget("user", text, ts, source="voice"))

    def _on_stt_error(self, msg: str):
        self._add_system_msg(f"⚠️ 语音识别错误：\n{msg}")
        self._stop_recording()

    # ── 三个按钮 ──────────────────────────────

    def _on_ai_btn(self):
        text = self.text_input.text().strip()
        if not text:
            self._add_system_msg("⚠️ 请先输入内容或录音")
            return
        self.text_input.clear()

        ts = datetime.now().strftime("%H:%M")
        # 避免语音已记录的内容重复入库
        recent = self.memory.get_recent(n=1)
        already = recent and recent[-1]["content"] == text and recent[-1]["role"] == "user"
        if not already:
            self.memory.add("user", text, source="text")
            self._refresh_stats()
            self._insert_msg(MessageWidget("user", text, ts, source="text"))

        self._start_ai(text, mode="chat")

    def _on_search_btn(self):
        text = self.text_input.text().strip()
        if not text:
            self._add_system_msg("⚠️ 请先输入搜索关键词，例如：明天的行程")
            return
        self.text_input.clear()
        ts = datetime.now().strftime("%H:%M")
        self._insert_msg(MessageWidget("user", f"🔍 {text}", ts, source="text"))
        self._start_ai(text, mode="search")

    # ── AI 调用 ───────────────────────────────

    def _start_ai(self, user_message: str, mode: str = "chat"):
        self._set_btns_enabled(False)
        self.statusBar().showMessage("🤖 AI 思考中…" if mode == "chat" else "🔍 搜索中…")

        ts = datetime.now().strftime("%H:%M")
        self._cur_ai_widget = MessageWidget("assistant", "▌", ts)
        self._cur_ai_text   = ""
        self._insert_msg(self._cur_ai_widget)

        self.ai_thread = AIThread(self.ai, user_message, mode=mode)
        self.ai_thread.chunk_ready.connect(self._on_ai_chunk)
        self.ai_thread.reply_done.connect(self._on_ai_done)
        self.ai_thread.start()

    def _on_ai_chunk(self, chunk: str):
        self._cur_ai_text += chunk
        if self._cur_ai_widget:
            self._cur_ai_widget.update_content(self._cur_ai_text + "▌")
        self._scroll_bottom()

    def _on_ai_done(self, full_reply: str):
        final = self._cur_ai_text or full_reply
        if self._cur_ai_widget:
            self._cur_ai_widget.update_content(final)
        self.memory.add("assistant", final)
        self._cur_ai_widget = None
        self._cur_ai_text   = ""
        self._set_btns_enabled(True)
        self.statusBar().showMessage("就绪")
        self._refresh_stats()
        self._scroll_bottom()

    def _set_btns_enabled(self, enabled: bool):
        self.ai_btn.setEnabled(enabled)
        self.search_btn.setEnabled(enabled)

    # ── 聊天工具 ──────────────────────────────

    def _insert_msg(self, widget: QWidget):
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)
        QTimer.singleShot(30, self._scroll_bottom)

    def _add_system_msg(self, text: str):
        ts = datetime.now().strftime("%H:%M")
        self._insert_msg(MessageWidget("system", text, ts))

    def _scroll_bottom(self):
        sb = self.chat_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_system_msg("对话已清空（历史文件仍保留）")

    def _restore_history(self):
        for r in self.memory.get_recent(n=MEMORY_RESTORE_RECENT):
            ts = r.get("time", "")[:5]
            self._insert_msg(
                MessageWidget(r["role"], r["content"], ts, r.get("source", "text"))
            )

    def _refresh_stats(self):
        self.stats_label.setText(
            f"历史记录：{self.memory.total} 条\n用户消息：{self.memory.user_count} 条"
        )

    # ── 样式 ──────────────────────────────────

    @staticmethod
    def _group(title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                color:#718096; font-size:11px;
                border:1px solid #21262d; border-radius:6px;
                margin-top:8px; padding-top:8px;
            }
            QGroupBox::title { subcontrol-origin:margin; padding:0 4px; }
        """)
        return g

    @staticmethod
    def _btn(bg: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background:{bg}; color:#fff; border:none;
                border-radius:6px; font-size:13px; font-weight:500; padding:0 12px;
            }}
            QPushButton:hover {{ background:{hover}; }}
            QPushButton:disabled {{ background:#21262d; color:#555; }}
        """

    @staticmethod
    def _combo_style() -> str:
        return """
            QComboBox {
                background:#0d1117; color:#c9d1d9;
                border:1px solid #30363d; border-radius:4px;
                padding:4px; font-size:11px;
            }
            QComboBox::drop-down { border:none; }
            QComboBox QAbstractItemView {
                background:#161b22; color:#c9d1d9;
                selection-background-color:#1f6feb;
            }
        """

    @staticmethod
    def _app_style() -> str:
        return """
            QMainWindow, QWidget {
                background:#0d1117; color:#c9d1d9;
                font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;
            }
            QScrollBar:vertical {
                background:#161b22; width:6px; border-radius:3px;
            }
            QScrollBar::handle:vertical {
                background:#30363d; border-radius:3px; min-height:24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """