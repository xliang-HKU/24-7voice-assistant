"""
core/settings.py
运行时设置：统一管理 Realtime / TTS / 提醒参数。
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path

import config


@dataclass
class LLMSettings:
    provider: str = config.LLM_PROVIDER
    api_key: str = config.LLM_API_KEY
    base_url: str = config.LLM_BASE_URL
    model: str = config.LLM_MODEL
    timeout_sec: int = 60

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


@dataclass
class RealtimeSettings:
    provider: str = config.REALTIME_PROVIDER
    enabled: bool = config.REALTIME_ENABLED
    api_key: str = config.REALTIME_API_KEY
    ws_url: str = config.REALTIME_WS_URL
    model: str = config.REALTIME_MODEL
    voice: str = config.REALTIME_VOICE
    app_id: str = config.REALTIME_APP_ID
    app_key: str = config.REALTIME_APP_KEY
    access_key: str = config.REALTIME_ACCESS_KEY
    resource_id: str = config.REALTIME_RESOURCE_ID
    bot_name: str = config.REALTIME_BOT_NAME
    input_sample_rate: int = config.REALTIME_INPUT_SAMPLE_RATE
    output_sample_rate: int = config.REALTIME_OUTPUT_SAMPLE_RATE
    input_block_size: int = config.REALTIME_INPUT_BLOCK_SIZE
    vad_threshold: int = config.REALTIME_VAD_THRESHOLD
    vad_silence_ms: int = config.REALTIME_VAD_SILENCE_MS
    min_speech_ms: int = config.REALTIME_MIN_SPEECH_MS
    ping_interval_sec: int = config.REALTIME_PING_INTERVAL_SEC
    silent_on_unrecognized_input: bool = config.REALTIME_SILENT_ON_UNRECOGNIZED

    @property
    def is_configured(self) -> bool:
        if self.provider == "doubao_dialog":
            return bool(
                self.enabled
                and self.ws_url
                and self.app_id
                and self.app_key
                and self.access_key
                and self.resource_id
            )
        return bool(self.enabled and self.api_key and self.ws_url and self.model)


@dataclass
class TTSSettings:
    provider: str = config.TTS_PROVIDER
    enabled: bool = config.TTS_ENABLED
    auto_play_reply: bool = config.TTS_AUTO_PLAY
    reminder_voice: bool = True
    fallback_to_system: bool = config.TTS_FALLBACK_SYSTEM
    endpoint: str = config.TTS_ENDPOINT
    system_voice: str = config.SYSTEM_TTS_VOICE

    app_id: str = config.DOUBAO_TTS_APP_ID
    access_token: str = config.DOUBAO_TTS_ACCESS_TOKEN
    cluster: str = config.DOUBAO_TTS_CLUSTER
    voice_type: str = config.DOUBAO_TTS_VOICE_TYPE
    encoding: str = config.DOUBAO_TTS_ENCODING
    sample_rate: int = config.DOUBAO_TTS_RATE
    speed_ratio: float = config.DOUBAO_TTS_SPEED_RATIO
    volume_ratio: float = config.DOUBAO_TTS_VOLUME_RATIO
    pitch_ratio: float = config.DOUBAO_TTS_PITCH_RATIO
    enable_emotion: bool = False

    @property
    def is_doubao_configured(self) -> bool:
        return bool(self.app_id and self.access_token and self.cluster and self.voice_type)


@dataclass
class AssistantSettings:
    reminder_poll_interval_sec: int = config.REMINDER_POLL_INTERVAL_SEC
    pause_recording_while_speaking: bool = True


@dataclass
class AppSettings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    realtime: RealtimeSettings = field(default_factory=RealtimeSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    assistant: AssistantSettings = field(default_factory=AssistantSettings)

    def clone(self) -> "AppSettings":
        return deepcopy(self)

    def to_dict(self) -> dict:
        return asdict(self)


class SettingsManager:
    """
    统一处理 settings.json，兼容旧版结构。
    """

    def __init__(self, filepath: Path = config.SETTINGS_FILE):
        self.filepath = filepath
        self.settings = AppSettings()
        self.load()

    def load(self) -> AppSettings:
        data: dict = {}
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}

        self.settings = self._from_dict(data)
        self.save()
        return self.settings

    def save(self):
        self.filepath.parent.mkdir(exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.settings.to_dict(), f, ensure_ascii=False, indent=2)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()

    @staticmethod
    def _merge_dataclass(instance, values: dict | None):
        values = values or {}
        for key, value in values.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

    def _from_dict(self, data: dict) -> AppSettings:
        settings = AppSettings()

        legacy_api_key = data.get("api_key", "")
        if legacy_api_key and not data.get("llm"):
            settings.llm.api_key = legacy_api_key

        self._merge_dataclass(settings.llm, data.get("llm"))
        self._merge_dataclass(settings.realtime, data.get("realtime"))
        self._merge_dataclass(settings.tts, data.get("tts"))
        self._merge_dataclass(settings.assistant, data.get("assistant"))
        if not settings.realtime.api_key and settings.llm.api_key:
            settings.realtime.api_key = settings.llm.api_key
        if not settings.realtime.access_key and settings.tts.access_token:
            settings.realtime.access_key = settings.tts.access_token
        return settings
