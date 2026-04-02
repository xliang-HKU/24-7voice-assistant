"""
项目配置
"""
import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ── 路径 ──────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
MODEL_DIR = BASE_DIR / "model"
MEMORY_FILE = OUTPUT_DIR / "memory.json"
PROFILE_MEMORY_FILE = OUTPUT_DIR / "profile_memory.json"
SETTINGS_FILE = OUTPUT_DIR / "settings.json"
REMINDERS_FILE = OUTPUT_DIR / "reminders.json"
TTS_CACHE_DIR = OUTPUT_DIR / "tts_cache"

OUTPUT_DIR.mkdir(exist_ok=True)
TTS_CACHE_DIR.mkdir(exist_ok=True)

# ── LLM 默认配置 ──────────────────────────────
LLM_PROVIDER = os.getenv("VOICE_ASSISTANT_LLM_PROVIDER", "openai_compatible")
LLM_API_KEY = os.getenv("VOICE_ASSISTANT_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("VOICE_ASSISTANT_LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("VOICE_ASSISTANT_LLM_MODEL", "deepseek-chat")

# 兼容旧代码命名
DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_BASE_URL = LLM_BASE_URL
DEEPSEEK_MODEL = LLM_MODEL

# ── 豆包 Realtime 默认配置 ────────────────────
REALTIME_PROVIDER = os.getenv("VOICE_ASSISTANT_REALTIME_PROVIDER", "doubao_dialog")
REALTIME_ENABLED = _env_bool("VOICE_ASSISTANT_REALTIME_ENABLED", True)
REALTIME_API_KEY = os.getenv("VOICE_ASSISTANT_REALTIME_API_KEY", "")
REALTIME_WS_URL = os.getenv(
    "VOICE_ASSISTANT_REALTIME_WS_URL",
    "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
)
REALTIME_MODEL = os.getenv("VOICE_ASSISTANT_REALTIME_MODEL", "AG-voice-chat-agent")
REALTIME_VOICE = os.getenv(
    "VOICE_ASSISTANT_REALTIME_VOICE",
    "zh_female_vv_jupiter_bigtts",
)
REALTIME_APP_ID = os.getenv("VOICE_ASSISTANT_REALTIME_APP_ID", "")
REALTIME_APP_KEY = os.getenv("VOICE_ASSISTANT_REALTIME_APP_KEY", "PlgvMymc7f3tQnJ6")
REALTIME_ACCESS_KEY = os.getenv("VOICE_ASSISTANT_REALTIME_ACCESS_KEY", "")
REALTIME_RESOURCE_ID = os.getenv("VOICE_ASSISTANT_REALTIME_RESOURCE_ID", "volc.speech.dialog")
REALTIME_BOT_NAME = os.getenv("VOICE_ASSISTANT_REALTIME_BOT_NAME", "豆包")
REALTIME_INPUT_SAMPLE_RATE = int(os.getenv("VOICE_ASSISTANT_REALTIME_INPUT_SAMPLE_RATE", "16000"))
REALTIME_OUTPUT_SAMPLE_RATE = int(
    os.getenv("VOICE_ASSISTANT_REALTIME_OUTPUT_SAMPLE_RATE", "24000")
)
REALTIME_INPUT_BLOCK_SIZE = int(os.getenv("VOICE_ASSISTANT_REALTIME_INPUT_BLOCK_SIZE", "320"))
REALTIME_VAD_THRESHOLD = int(os.getenv("VOICE_ASSISTANT_REALTIME_VAD_THRESHOLD", "650"))
REALTIME_VAD_SILENCE_MS = int(os.getenv("VOICE_ASSISTANT_REALTIME_VAD_SILENCE_MS", "900"))
REALTIME_MIN_SPEECH_MS = int(os.getenv("VOICE_ASSISTANT_REALTIME_MIN_SPEECH_MS", "350"))
REALTIME_PING_INTERVAL_SEC = int(os.getenv("VOICE_ASSISTANT_REALTIME_PING_INTERVAL_SEC", "30"))
REALTIME_SILENT_ON_UNRECOGNIZED = _env_bool(
    "VOICE_ASSISTANT_REALTIME_SILENT_ON_UNRECOGNIZED",
    True,
)

# ── TTS 默认配置 ──────────────────────────────
TTS_PROVIDER = os.getenv("VOICE_ASSISTANT_TTS_PROVIDER", "system")
TTS_AUTO_PLAY = _env_bool("VOICE_ASSISTANT_TTS_AUTO_PLAY", True)
TTS_ENABLED = _env_bool("VOICE_ASSISTANT_TTS_ENABLED", True)
TTS_ENDPOINT = os.getenv(
    "VOICE_ASSISTANT_TTS_ENDPOINT",
    "https://openspeech.bytedance.com/api/v1/tts",
)
TTS_FALLBACK_SYSTEM = _env_bool("VOICE_ASSISTANT_TTS_FALLBACK_SYSTEM", True)

DOUBAO_TTS_APP_ID = os.getenv("DOUBAO_TTS_APP_ID", "")
DOUBAO_TTS_ACCESS_TOKEN = os.getenv("DOUBAO_TTS_ACCESS_TOKEN", "")
DOUBAO_TTS_CLUSTER = os.getenv("DOUBAO_TTS_CLUSTER", "volcano_tts")
DOUBAO_TTS_VOICE_TYPE = os.getenv("DOUBAO_TTS_VOICE_TYPE", "zh_female_meilinvyou_moon_bigtts")
DOUBAO_TTS_ENCODING = os.getenv("DOUBAO_TTS_ENCODING", "mp3")
DOUBAO_TTS_RATE = int(os.getenv("DOUBAO_TTS_RATE", "24000"))
DOUBAO_TTS_SPEED_RATIO = float(os.getenv("DOUBAO_TTS_SPEED_RATIO", "1.0"))
DOUBAO_TTS_VOLUME_RATIO = float(os.getenv("DOUBAO_TTS_VOLUME_RATIO", "1.0"))
DOUBAO_TTS_PITCH_RATIO = float(os.getenv("DOUBAO_TTS_PITCH_RATIO", "1.0"))
SYSTEM_TTS_VOICE = os.getenv("VOICE_ASSISTANT_SYSTEM_TTS_VOICE", "Tingting")

# ── 旧版本地 STT 兼容配置 ─────────────────────
STT_SAMPLE_RATE = 16000
STT_BLOCK_SIZE = 1600
STT_RULE1_MIN_TRAILING_SILENCE = 2.4
STT_RULE2_MIN_TRAILING_SILENCE = 1.2
STT_RULE3_MIN_UTTERANCE_LENGTH = 300

# ── UI ────────────────────────────────────────
APP_NAME = "老年人语音助手"
APP_VERSION = "3.0.0"
WINDOW_MIN_W = 980
WINDOW_MIN_H = 680

# ── 记忆 ──────────────────────────────────────
MEMORY_CONTEXT_TURNS = 10
MEMORY_SEARCH_TOP_K = 8
MEMORY_RESTORE_RECENT = 6
PROFILE_MEMORY_TOP_K = 10

# ── 提醒 ──────────────────────────────────────
REMINDER_POLL_INTERVAL_SEC = int(os.getenv("VOICE_ASSISTANT_REMINDER_POLL_INTERVAL_SEC", "15"))
