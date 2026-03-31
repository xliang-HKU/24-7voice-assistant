"""
配置文件
"""
from pathlib import Path

# ── 路径 ──────────────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
MODEL_DIR   = BASE_DIR / "model"
MEMORY_FILE = OUTPUT_DIR / "memory.json"

OUTPUT_DIR.mkdir(exist_ok=True)

# ── DeepSeek API ──────────────────────────────
# 在这里填写你的 API Key
DEEPSEEK_API_KEY  = "sk-f9f411001e644980880656dfde52e35b"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL    = "deepseek-chat"

# ── 语音识别 ──────────────────────────────────
STT_SAMPLE_RATE   = 16000
STT_BLOCK_SIZE    = 1600
STT_RULE1_MIN_TRAILING_SILENCE = 2.4
STT_RULE2_MIN_TRAILING_SILENCE = 1.2
STT_RULE3_MIN_UTTERANCE_LENGTH = 300

# ── UI ────────────────────────────────────────
APP_NAME    = "智能语音助手"
APP_VERSION = "2.0.0"
WINDOW_MIN_W = 960
WINDOW_MIN_H = 680

# ── 记忆 ──────────────────────────────────────
MEMORY_CONTEXT_TURNS  = 10
MEMORY_SEARCH_TOP_K   = 8
MEMORY_RESTORE_RECENT = 6