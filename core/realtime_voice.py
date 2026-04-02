"""
core/realtime_voice.py
豆包 Dialog 实时语音线程：
- 通过官方二进制 WebSocket 协议与服务端通信
- 连续上传麦克风音频
- 播放服务端返回的 PCM 音频
"""
from __future__ import annotations

import asyncio
import gzip
import json
import threading
import time
import uuid
from typing import Any

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal

from core.settings import AppSettings

try:
    import websockets
    from websockets.exceptions import ConnectionClosed

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    websockets = None
    ConnectionClosed = Exception
    WEBSOCKETS_AVAILABLE = False


# ---- Dialog protocol -------------------------------------------------------

PROTOCOL_VERSION = 0b0001
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_AUDIO_ONLY_RESPONSE = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

MSG_WITH_EVENT = 0b0100
NEG_SEQUENCE = 0b0010

NO_SERIALIZATION = 0b0000
JSON_SERIALIZATION = 0b0001

NO_COMPRESSION = 0b0000
GZIP_COMPRESSION = 0b0001

EVENT_START_CONNECTION = 1
EVENT_FINISH_CONNECTION = 2
EVENT_TASK_REQUEST = 200
EVENT_START_SESSION = 100
EVENT_FINISH_SESSION = 102
EVENT_CHAT_TEXT_QUERY = 501
EVENT_CLIENT_INTERRUPT = 515

EVENT_CONNECTION_STARTED = 50
EVENT_CONNECTION_FINISHED = 52
EVENT_SESSION_STARTED = 150
EVENT_SESSION_FINISHED = 152
EVENT_SESSION_FAILED = 153
EVENT_TTS_SENTENCE_START = 350
EVENT_TTS_RESPONSE = 352
EVENT_TTS_ENDED = 359
EVENT_ASR_INFO = 450
EVENT_ASR_RESPONSE = 451
EVENT_ASR_ENDED = 459
EVENT_CHAT_RESPONSE = 550
EVENT_CHAT_TEXT_QUERY_CONFIRMED = 553
EVENT_CHAT_ENDED = 559
EVENT_DIALOG_ERROR = 599


def generate_header(
    message_type: int,
    message_type_specific_flags: int = MSG_WITH_EVENT,
    serial_method: int = JSON_SERIALIZATION,
    compression_type: int = GZIP_COMPRESSION,
) -> bytearray:
    header = bytearray()
    header.append((PROTOCOL_VERSION << 4) | 0b0001)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(0x00)
    return header


def build_full_request(event: int, payload: dict[str, Any], session_id: str | None = None) -> bytes:
    request = bytearray(generate_header(CLIENT_FULL_REQUEST))
    request.extend(int(event).to_bytes(4, "big"))

    if session_id is not None:
        session_id_bytes = session_id.encode("utf-8")
        request.extend(len(session_id_bytes).to_bytes(4, "big"))
        request.extend(session_id_bytes)

    payload_bytes = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    request.extend(len(payload_bytes).to_bytes(4, "big"))
    request.extend(payload_bytes)
    return bytes(request)


def build_audio_request(event: int, audio: bytes, session_id: str) -> bytes:
    request = bytearray(
        generate_header(
            CLIENT_AUDIO_ONLY_REQUEST,
            serial_method=NO_SERIALIZATION,
            compression_type=GZIP_COMPRESSION,
        )
    )
    request.extend(int(event).to_bytes(4, "big"))
    session_id_bytes = session_id.encode("utf-8")
    request.extend(len(session_id_bytes).to_bytes(4, "big"))
    request.extend(session_id_bytes)

    payload_bytes = gzip.compress(audio)
    request.extend(len(payload_bytes).to_bytes(4, "big"))
    request.extend(payload_bytes)
    return bytes(request)


def parse_response(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, str):
        return {}

    header_size = raw[0] & 0x0F
    message_type = raw[1] >> 4
    message_flags = raw[1] & 0x0F
    serial_method = raw[2] >> 4
    compression = raw[2] & 0x0F

    payload = raw[header_size * 4 :]
    result: dict[str, Any] = {"message_type_code": message_type}
    payload_msg: bytes | dict[str, Any] | str | None = None
    payload_size = 0

    if message_type in (SERVER_FULL_RESPONSE, SERVER_AUDIO_ONLY_RESPONSE):
        result["message_type"] = (
            "SERVER_FULL_RESPONSE" if message_type == SERVER_FULL_RESPONSE else "SERVER_AUDIO_ONLY_RESPONSE"
        )
        offset = 0
        if message_flags & NEG_SEQUENCE:
            result["seq"] = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
            offset += 4
        if message_flags & MSG_WITH_EVENT:
            result["event"] = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
            offset += 4

        session_size = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        session_id = payload[offset : offset + session_size]
        offset += session_size
        result["session_id"] = session_id.decode("utf-8", errors="ignore")

        payload_size = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        payload_msg = payload[offset:]
    elif message_type == SERVER_ERROR_RESPONSE:
        result["message_type"] = "SERVER_ERROR"
        result["code"] = int.from_bytes(payload[:4], "big", signed=False)
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]
    else:
        result["message_type"] = "UNKNOWN"
        return result

    if payload_msg is None:
        return result

    if compression == GZIP_COMPRESSION and payload_msg:
        payload_msg = gzip.decompress(payload_msg)

    if serial_method == JSON_SERIALIZATION and payload_msg:
        payload_msg = json.loads(payload_msg.decode("utf-8"))
    elif serial_method != NO_SERIALIZATION and payload_msg:
        payload_msg = payload_msg.decode("utf-8", errors="ignore")

    result["payload_msg"] = payload_msg
    result["payload_size"] = payload_size
    return result


# ---- Audio -----------------------------------------------------------------


class PCMStreamPlayer:
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None
        self._last_sample = 0
        self._release_frames = 0
        self._primed = False
        self._prebuffer_bytes = max(1, int(self.sample_rate * 2 * 0.12))
        self._blocksize = max(480, int(self.sample_rate * 0.04))

    def start(self):
        if self._stream is not None:
            return
        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self._blocksize,
            latency="high",
            callback=self._callback,
        )
        self._stream.start()

    def enqueue(self, pcm_bytes: bytes):
        if not pcm_bytes:
            return
        with self._lock:
            self._buffer.extend(pcm_bytes)

    def clear(self, fade_ms: int = 48):
        with self._lock:
            self._buffer.clear()
            self._release_frames = max(1, int(self.sample_rate * max(0, fade_ms) / 1000))
            self._primed = False

    def begin_stream(self):
        with self._lock:
            self._primed = False

    def buffered_seconds(self) -> float:
        with self._lock:
            pending_bytes = len(self._buffer)
        bytes_per_second = max(1, self.sample_rate * 2)
        return pending_bytes / bytes_per_second

    def stop(self):
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self.clear()

    def _callback(self, outdata, frames, _time_info, _status):
        with self._lock:
            buffered_bytes = len(self._buffer)
            release_frames = self._release_frames
            primed = self._primed

        if not primed and buffered_bytes < self._prebuffer_bytes and release_frames == 0:
            outdata.fill(0)
            return

        required = frames * 2
        with self._lock:
            self._primed = True
            chunk = bytes(self._buffer[:required])
            del self._buffer[: len(chunk)]
            release_frames = self._release_frames
            last_sample = self._last_sample
        actual_frame_count = len(chunk) // 2

        if chunk:
            samples = np.frombuffer(chunk, dtype=np.int16).copy().reshape(-1, 1)
        else:
            samples = np.zeros((0, 1), dtype=np.int16)

        if release_frames > 0 and len(samples) > 0:
            ramp_len = min(len(samples), release_frames)
            ramp = np.linspace(last_sample, 0, num=ramp_len, endpoint=False, dtype=np.float32)
            samples[:ramp_len, 0] = np.clip(ramp, -32768, 32767).astype(np.int16)
            with self._lock:
                self._release_frames = max(0, self._release_frames - ramp_len)

        if actual_frame_count < frames:
            tail_len = frames - actual_frame_count
            tail_start = int(samples[-1, 0]) if len(samples) else last_sample
            tail = np.linspace(tail_start, 0, num=tail_len, endpoint=False, dtype=np.float32)
            tail_samples = np.clip(tail, -32768, 32767).astype(np.int16).reshape(-1, 1)
            if len(samples):
                samples = np.vstack((samples, tail_samples))
            else:
                samples = tail_samples

        if len(samples) < frames:
            silence = np.zeros((frames - len(samples), 1), dtype=np.int16)
            samples = np.vstack((samples, silence))

        final_sample = int(samples[-1, 0]) if len(samples) else 0
        with self._lock:
            self._last_sample = final_sample
            if not self._buffer and self._release_frames == 0 and final_sample == 0:
                self._primed = False
        outdata[:] = samples


# ---- Thread ----------------------------------------------------------------


class RealtimeVoiceThread(QThread):
    status_changed = Signal(str)
    session_ready = Signal()
    user_transcript = Signal(str)
    assistant_partial = Signal(str)
    assistant_transcript = Signal(str)
    error = Signal(str)

    def __init__(self, settings: AppSettings, instructions: str):
        super().__init__()
        self.settings = settings
        self.instructions = instructions
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ws = None
        self._audio_queue: asyncio.Queue[bytes] | None = None
        self._player: PCMStreamPlayer | None = None
        self._capture_paused_by_local_tts = False
        self._capture_paused_by_assistant_tts = False
        self._capture_resume_at = 0.0
        self._session_id = str(uuid.uuid4())
        self._connect_id = str(uuid.uuid4())
        self._session_started = False
        self._assistant_partial_text = ""
        self._latest_asr_text = ""
        self._suppress_assistant_turn = False

    def run(self):
        if not WEBSOCKETS_AVAILABLE:
            self.error.emit("未安装 websockets，请先运行 `pip install -r requirements.txt`。")
            return
        try:
            asyncio.run(self._main())
        except Exception as exc:
            self.error.emit(f"Realtime 会话异常：{exc}")
        finally:
            try:
                if self._player:
                    self._player.stop()
            except Exception:
                pass
            self.status_changed.emit("会话已结束")

    def stop_session(self):
        self._capture_paused_by_local_tts = True
        self._capture_paused_by_assistant_tts = True
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    def request_response(self):
        # 豆包 Dialog 的麦克风模式会在 ASR 结束后自动生成回复，这里不需要额外触发。
        return

    def cancel_response(self):
        if self._player:
            self._player.clear()
        self._resume_capture_after_assistant(delay_sec=0.2)
        self._assistant_partial_text = ""
        self._suppress_assistant_turn = True
        self._submit(self._interrupt_assistant_turn())

    def send_text_query(self, content: str):
        content = content.strip()
        if not content:
            return
        self._assistant_partial_text = ""
        self._suppress_assistant_turn = False
        self._submit(self._send_text_query(content))

    def set_capture_paused(self, paused: bool):
        self._capture_paused_by_local_tts = paused
        if paused:
            self._drop_pending_audio()

    def _submit(self, coro):
        if not self._loop or not self.isRunning():
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception:
            pass

    async def _main(self):
        rt = self.settings.realtime
        if not rt.is_configured:
            self.error.emit("Realtime 配置不完整。请在 output/settings.json 里补充 app_id / app_key / access_key。")
            return

        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        self._audio_queue = asyncio.Queue()
        self._player = PCMStreamPlayer(rt.output_sample_rate)

        self.status_changed.emit("正在连接语音模型…")
        async with websockets.connect(
            rt.ws_url,
            extra_headers=self._build_headers(),
            ping_interval=None,
            max_size=None,
        ) as ws:
            self._ws = ws
            logid = ws.response_headers.get("X-Tt-Logid", "")
            if logid:
                self.status_changed.emit(f"连接成功，logid：{logid}")

            await self._perform_handshake()

            self._player.start()
            self.status_changed.emit("可以开始说话了")
            self.session_ready.emit()

            with sd.InputStream(
                samplerate=rt.input_sample_rate,
                channels=1,
                dtype="int16",
                blocksize=rt.input_block_size,
                callback=self._mic_callback,
            ):
                receiver_task = asyncio.create_task(self._recv_loop())
                mic_task = asyncio.create_task(self._mic_loop())
                ping_task = asyncio.create_task(self._ping_loop())

                await self._stop_event.wait()

                for task in (receiver_task, mic_task, ping_task):
                    task.cancel()
                await asyncio.gather(receiver_task, mic_task, ping_task, return_exceptions=True)
                await self._shutdown_remote()

    def _build_headers(self) -> dict[str, str]:
        rt = self.settings.realtime
        return {
            "X-Api-App-ID": rt.app_id,
            "X-Api-Access-Key": rt.access_key,
            "X-Api-Resource-Id": rt.resource_id,
            "X-Api-App-Key": rt.app_key,
            "X-Api-Connect-Id": self._connect_id,
        }

    async def _perform_handshake(self):
        if self._ws is None:
            raise RuntimeError("WebSocket 尚未建立。")

        await self._ws.send(build_full_request(EVENT_START_CONNECTION, {}))
        connection_response = parse_response(await self._ws.recv())
        if connection_response.get("event") != EVENT_CONNECTION_STARTED:
            raise RuntimeError(self._format_protocol_error(connection_response, "连接初始化失败"))

        await self._ws.send(
            build_full_request(
                EVENT_START_SESSION,
                self._build_start_session_payload(),
                session_id=self._session_id,
            )
        )
        session_response = parse_response(await self._ws.recv())
        if session_response.get("event") != EVENT_SESSION_STARTED:
            raise RuntimeError(self._format_protocol_error(session_response, "会话初始化失败"))

        self._session_started = True

    def _build_start_session_payload(self) -> dict[str, Any]:
        rt = self.settings.realtime
        return {
            "asr": {
                "extra": {
                    "end_smooth_window_ms": max(500, min(rt.vad_silence_ms, 50000)),
                }
            },
            "tts": {
                "speaker": rt.voice,
                "audio_config": {
                    "channel": 1,
                    "format": "pcm_s16le",
                    "sample_rate": rt.output_sample_rate,
                },
            },
            "dialog": {
                "bot_name": rt.bot_name or "豆包",
                "system_role": self.instructions,
                "speaking_style": "语气温和、耐心、口语化，像一直陪在身边的家人。",
                "extra": {
                    "strict_audit": False,
                    "recv_timeout": 30,
                    "input_mod": "keep_alive",
                },
            },
        }

    async def _recv_loop(self):
        try:
            async for message in self._ws:
                self._handle_server_message(parse_response(message))
        except asyncio.CancelledError:
            return
        except ConnectionClosed:
            if self._stop_event and not self._stop_event.is_set():
                self.error.emit("Realtime 连接已断开。")
                self._stop_event.set()
        except Exception as exc:
            if self._stop_event and not self._stop_event.is_set():
                self.error.emit(f"接收服务端消息失败：{exc}")
                self._stop_event.set()

    async def _mic_loop(self):
        try:
            while self._stop_event and not self._stop_event.is_set():
                chunk = await self._audio_queue.get()
                if not self._should_capture_input():
                    continue
                await self._send_audio_chunk(chunk)
        except asyncio.CancelledError:
            return

    def _handle_server_message(self, message: dict[str, Any]):
        if not message:
            return

        msg_type = message.get("message_type")
        if msg_type == "SERVER_ERROR":
            detail = self._format_protocol_error(message, "Realtime 返回错误")
            self.error.emit(detail)
            if self._stop_event:
                self._stop_event.set()
            return

        event = message.get("event")
        payload = message.get("payload_msg") or {}

        if msg_type == "SERVER_AUDIO_ONLY_RESPONSE" and event == EVENT_TTS_RESPONSE:
            if not self._suppress_assistant_turn and isinstance(payload, (bytes, bytearray)) and self._player:
                self._pause_capture_for_assistant()
                self._player.enqueue(bytes(payload))
            return

        if msg_type != "SERVER_FULL_RESPONSE":
            return

        if event == EVENT_ASR_INFO:
            self._latest_asr_text = ""
            self.status_changed.emit("正在听你说…")
            return

        if event == EVENT_ASR_RESPONSE:
            transcript = self._extract_asr_text(payload)
            if transcript:
                self._latest_asr_text = transcript
            return

        if event == EVENT_ASR_ENDED:
            transcript = self._latest_asr_text.strip()
            self._latest_asr_text = ""
            if transcript:
                self.user_transcript.emit(transcript)
            self.status_changed.emit("我听到了，正在整理…")
            return

        if event == EVENT_TTS_SENTENCE_START:
            if self._player:
                self._player.begin_stream()
            self._pause_capture_for_assistant()
            if not self._suppress_assistant_turn:
                self.status_changed.emit("正在回应你…")
            return

        if event == EVENT_CHAT_RESPONSE:
            if self._suppress_assistant_turn:
                return
            content = str(payload.get("content") or "")
            if content:
                self._assistant_partial_text += content
                self.assistant_partial.emit(self._assistant_partial_text.strip())
            return

        if event == EVENT_CHAT_TEXT_QUERY_CONFIRMED:
            self.status_changed.emit("正在提醒你…")
            return

        if event == EVENT_CHAT_ENDED:
            if self._suppress_assistant_turn:
                self._assistant_partial_text = ""
                return
            transcript = self._assistant_partial_text.strip()
            self._assistant_partial_text = ""
            if transcript:
                self.assistant_transcript.emit(transcript)
            return

        if event == EVENT_TTS_ENDED:
            self._resume_capture_after_assistant()
            if self._suppress_assistant_turn:
                self._suppress_assistant_turn = False
                self._assistant_partial_text = ""
                return
            self.status_changed.emit("我在听，你可以继续说")
            return

        if event == EVENT_DIALOG_ERROR:
            detail = self._format_protocol_error(message, "通话过程中出错")
            self.error.emit(detail)
            if self._stop_event:
                self._stop_event.set()
            return

        if event == EVENT_SESSION_FAILED:
            detail = self._format_protocol_error(message, "会话失败")
            self.error.emit(detail)
            if self._stop_event:
                self._stop_event.set()
            return

        if event in (EVENT_SESSION_FINISHED, EVENT_CONNECTION_FINISHED):
            if self._stop_event and not self._stop_event.is_set():
                self._stop_event.set()

    async def _send_audio_chunk(self, chunk: bytes):
        if self._ws is None:
            return
        await self._ws.send(build_audio_request(EVENT_TASK_REQUEST, chunk, self._session_id))

    async def _interrupt_assistant_turn(self):
        if self._ws is None or not self._session_started:
            return
        try:
            await self._ws.send(build_full_request(EVENT_CLIENT_INTERRUPT, {}, session_id=self._session_id))
        except Exception:
            return

    async def _send_text_query(self, content: str):
        if self._ws is None or not self._session_started:
            return
        payload = {"content": content}
        await self._ws.send(build_full_request(EVENT_CHAT_TEXT_QUERY, payload, session_id=self._session_id))

    async def _shutdown_remote(self):
        if self._ws is None:
            return

        try:
            if self._session_started:
                await self._ws.send(build_full_request(EVENT_FINISH_SESSION, {}, session_id=self._session_id))
                await asyncio.wait_for(self._ws.recv(), timeout=2)
        except Exception:
            pass

        try:
            await self._ws.send(build_full_request(EVENT_FINISH_CONNECTION, {}))
            await asyncio.wait_for(self._ws.recv(), timeout=2)
        except Exception:
            pass

        try:
            await self._ws.close()
        except Exception:
            pass

    async def _ping_loop(self):
        try:
            while self._stop_event and not self._stop_event.is_set():
                await asyncio.sleep(max(10, self.settings.realtime.ping_interval_sec))
                if self._ws is not None:
                    await self._ws.ping()
        except asyncio.CancelledError:
            return
        except Exception:
            return

    def _mic_callback(self, indata, _frames, _time_info, status):
        if status:
            return
        if not self._should_capture_input() or self._audio_queue is None or self._loop is None:
            return
        mono = np.array(indata[:, 0], dtype=np.int16, copy=True)
        try:
            self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, mono.tobytes())
        except RuntimeError:
            return

    def _should_capture_input(self) -> bool:
        return (
            not self._capture_paused_by_local_tts
            and not self._capture_paused_by_assistant_tts
            and time.monotonic() >= self._capture_resume_at
        )

    def _pause_capture_for_assistant(self):
        if not self.settings.assistant.pause_recording_while_speaking:
            return
        self._capture_paused_by_assistant_tts = True
        self._capture_resume_at = 0.0
        self._drop_pending_audio()

    def _resume_capture_after_assistant(self, delay_sec: float = 0.8):
        if not self.settings.assistant.pause_recording_while_speaking:
            return
        buffered_sec = self._player.buffered_seconds() if self._player else 0.0
        self._capture_paused_by_assistant_tts = False
        self._capture_resume_at = time.monotonic() + max(0.0, delay_sec + buffered_sec)
        self._drop_pending_audio()

    def _drop_pending_audio(self):
        if self._audio_queue is None:
            return
        if self._loop:
            self._loop.call_soon_threadsafe(self._drain_audio_queue)
            return
        self._drain_audio_queue()

    def _drain_audio_queue(self):
        if self._audio_queue is None:
            return
        try:
            while True:
                self._audio_queue.get_nowait()
        except asyncio.QueueEmpty:
            return

    @staticmethod
    def _extract_asr_text(payload: dict[str, Any]) -> str:
        results = payload.get("results") or []
        texts = [str(item.get("text") or "").strip() for item in results if item.get("text")]
        return texts[-1] if texts else ""

    @staticmethod
    def _format_protocol_error(message: dict[str, Any], prefix: str) -> str:
        payload = message.get("payload_msg") or {}
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("error") or payload.get("status_code")
            if not detail:
                detail = json.dumps(payload, ensure_ascii=False)
        else:
            detail = str(payload) if payload else json.dumps(message, ensure_ascii=False)
        return f"{prefix}：{detail}"
