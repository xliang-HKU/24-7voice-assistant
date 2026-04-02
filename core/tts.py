"""
core/tts.py
语音合成与播放队列。
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from config import TTS_CACHE_DIR
from core.settings import AppSettings, TTSSettings


@dataclass
class SpeechJob:
    text: str
    source: str = "assistant"
    emotion: str = ""


class BaseTTSEngine:
    def synthesize_to_file(self, text: str, emotion: str = "") -> str:
        raise NotImplementedError


class DoubaoTTSEngine(BaseTTSEngine):
    def __init__(self, settings: TTSSettings):
        self.settings = settings

    def synthesize_to_file(self, text: str, emotion: str = "") -> str:
        if not self.settings.is_doubao_configured:
            raise RuntimeError("豆包 TTS 配置不完整，请填写 app_id / access_token / cluster / voice_type")

        payload = {
            "app": {
                "appid": self.settings.app_id,
                "token": self.settings.access_token,
                "cluster": self.settings.cluster,
            },
            "user": {"uid": "voice-assistant"},
            "audio": {
                "voice_type": self.settings.voice_type,
                "encoding": self.settings.encoding,
                "speed_ratio": self.settings.speed_ratio,
                "volume_ratio": self.settings.volume_ratio,
                "pitch_ratio": self.settings.pitch_ratio,
                "rate": self.settings.sample_rate,
            },
            "request": {
                "reqid": str(uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
            },
        }
        if emotion and self.settings.enable_emotion:
            payload["audio"]["emotion"] = emotion

        request = urllib.request.Request(
            self.settings.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer;{self.settings.access_token}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"TTS 请求失败：HTTP {exc.code} {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"TTS 请求失败：{exc}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("TTS 返回内容不是合法 JSON") from exc

        code = data.get("code")
        if code not in (0, 3000):
            raise RuntimeError(data.get("message") or data.get("msg") or f"TTS 合成失败，code={code}")

        audio_b64 = data.get("data")
        if not audio_b64:
            raise RuntimeError("TTS 没有返回音频数据")

        encoding = self.settings.encoding.lower()
        if encoding not in {"mp3", "wav"}:
            raise RuntimeError("当前播放器只支持 mp3/wav，请先把 output/settings.json 里的 tts.encoding 设为 mp3 或 wav")

        suffix = f".{encoding}"
        path = self._temp_path(suffix)
        with open(path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return str(path)

    @staticmethod
    def _temp_path(suffix: str) -> Path:
        TTS_CACHE_DIR.mkdir(exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="voice_", suffix=suffix, dir=TTS_CACHE_DIR)
        os.close(fd)
        Path(name).unlink(missing_ok=True)
        Path(name).touch()
        return Path(name)


class SystemTTSEngine(BaseTTSEngine):
    PREFERRED_VOICES = (
        "Tingting",
        "Flo (中文（中国大陆）)",
        "Flo (中文（台湾）)",
        "Sin-ji",
        "Mei-Jia",
        "Grandma (中文（中国大陆）)",
        "Eddy (中文（中国大陆）)",
    )

    def __init__(self, preferred_voice: str = ""):
        self.say_path = shutil.which("say")
        if not self.say_path:
            raise RuntimeError("系统 TTS 不可用：未找到 say 命令")
        self.voice = preferred_voice.strip() or self._detect_voice()

    def synthesize_to_file(self, text: str, emotion: str = "") -> str:
        fd, name = tempfile.mkstemp(prefix="voice_", suffix=".aiff", dir=TTS_CACHE_DIR)
        os.close(fd)
        Path(name).unlink(missing_ok=True)
        path = Path(name)
        cmd = [self.say_path]
        if self.voice:
            cmd.extend(["-v", self.voice])
        cmd.extend(["-o", str(path), text])
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(exc.stderr.strip() or "系统 TTS 合成失败") from exc
        return str(path)

    def _detect_voice(self) -> str:
        try:
            result = subprocess.run(
                [self.say_path, "-v", "?"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ""

        available_lines = result.stdout.splitlines()
        for voice in self.PREFERRED_VOICES:
            if any(line.startswith(voice) for line in available_lines):
                return voice
        return ""


class SpeechWorker(QThread):
    file_ready = Signal(str)
    error = Signal(str)

    def __init__(self, settings: AppSettings, job: SpeechJob):
        super().__init__()
        self.settings = deepcopy(settings)
        self.job = job

    def run(self):
        try:
            engine = self._build_engine()
            path = engine.synthesize_to_file(self.job.text, emotion=self.job.emotion)
            self.file_ready.emit(path)
        except Exception as exc:
            self.error.emit(str(exc))

    def _build_engine(self) -> BaseTTSEngine:
        tts = self.settings.tts
        if self.job.source == "system":
            return SystemTTSEngine(tts.system_voice)
        if tts.provider == "doubao" and tts.is_doubao_configured:
            return DoubaoTTSEngine(tts)
        if tts.provider == "system":
            return SystemTTSEngine(tts.system_voice)
        if tts.fallback_to_system:
            return SystemTTSEngine(tts.system_voice)
        raise RuntimeError("没有可用的语音合成引擎")


class SpeechManager(QObject):
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.queue: deque[SpeechJob] = deque()
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.worker: SpeechWorker | None = None
        self.current_file: str = ""
        self._busy = False

    def update_settings(self, settings: AppSettings):
        self.settings = settings

    def enqueue(self, text: str, source: str = "assistant", emotion: str = ""):
        if not text or not self.settings.tts.enabled:
            return
        self.queue.append(SpeechJob(text=text, source=source, emotion=emotion))
        if not self.worker and self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
            self._process_next()

    def stop(self):
        self.queue.clear()
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(2000)
        self.player.stop()
        self._cleanup_current_file()
        self._set_busy(False)

    def _process_next(self):
        if self.worker or not self.queue:
            return
        job = self.queue.popleft()
        self.worker = SpeechWorker(self.settings.clone(), job)
        self.worker.file_ready.connect(self._on_file_ready)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_file_ready(self, path: str):
        self.current_file = path
        self._set_busy(True)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _on_worker_error(self, message: str):
        self.error.emit(message)
        if not self.current_file and not self.queue:
            self._set_busy(False)

    def _on_worker_finished(self):
        self.worker = None
        if not self.current_file:
            self._process_next()
        if not self.current_file and not self.queue:
            self._set_busy(False)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status in {
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
            QMediaPlayer.MediaStatus.NoMedia,
        }:
            self._cleanup_current_file()
            self._process_next()
            if not self.current_file and not self.worker and not self.queue:
                self._set_busy(False)

    def _cleanup_current_file(self):
        if not self.current_file:
            return
        try:
            Path(self.current_file).unlink(missing_ok=True)
        except Exception:
            pass
        self.current_file = ""

    def _set_busy(self, busy: bool):
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)
