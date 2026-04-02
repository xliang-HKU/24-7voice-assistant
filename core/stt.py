"""
core/stt.py
实时语音识别线程（基于 sherpa-onnx）
兼容新旧版本 API
"""
import queue
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except ImportError:
    SHERPA_AVAILABLE = False

from PySide6.QtCore import QThread, Signal

from config import (
    MODEL_DIR,
    STT_SAMPLE_RATE,
    STT_BLOCK_SIZE,
    STT_RULE1_MIN_TRAILING_SILENCE,
    STT_RULE2_MIN_TRAILING_SILENCE,
    STT_RULE3_MIN_UTTERANCE_LENGTH,
)


def _get_text(result) -> str:
    """兼容不同版本：result 可能是 str 或带 .text 属性的对象"""
    if isinstance(result, str):
        return result.strip()
    return result.text.strip()


class STTThread(QThread):
    text_partial = Signal(str)
    text_final   = Signal(str)
    error        = Signal(str)

    def __init__(self):
        super().__init__()
        self.running      = False
        self.recognizer   = None
        self.device_index: Optional[int] = None
        self._input_sample_rate = STT_SAMPLE_RATE
        self._audio_q: queue.Queue = queue.Queue()
        self._decode_fn   = None   # 兼容新旧 decode API

    # ── 设备 ──────────────────────────────────

    @staticmethod
    def list_devices() -> list[tuple[int, str]]:
        devices = []
        try:
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    devices.append((i, d["name"]))
        except Exception:
            pass
        return devices

    def set_device(self, device_index: int):
        self.device_index = device_index

    def _query_input_device(self) -> tuple[Optional[int], dict]:
        """
        返回当前选中的输入设备配置；如果未选中则回退到系统默认输入设备。
        """
        try:
            if self.device_index is not None:
                info = sd.query_devices(self.device_index, "input")
                return self.device_index, info

            default_input = sd.default.device[0]
            if default_input is not None and default_input != -1:
                info = sd.query_devices(default_input, "input")
                return int(default_input), info
        except Exception:
            pass

        try:
            info = sd.query_devices(kind="input")
            return None, info
        except Exception as e:
            raise RuntimeError(f"无法读取麦克风信息：{e}") from e

    @staticmethod
    def _resample_audio(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        if src_rate == dst_rate or len(audio) == 0:
            return audio.astype(np.float32, copy=False)

        new_length = max(1, int(round(len(audio) * dst_rate / src_rate)))
        old_points = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
        new_points = np.linspace(0.0, 1.0, num=new_length, endpoint=False)
        resampled = np.interp(new_points, old_points, audio)
        return resampled.astype(np.float32, copy=False)

    def _stream_candidates(self) -> list[dict]:
        """
        生成一组较稳妥的 InputStream 配置：
        1. 当前设备默认采样率
        2. 当前设备 48k
        3. 当前设备 44.1k
        """
        device_index, info = self._query_input_device()
        default_sr = int(round(info.get("default_samplerate") or STT_SAMPLE_RATE))
        max_channels = max(1, int(info.get("max_input_channels") or 1))

        candidates: list[dict] = []
        for sample_rate in (default_sr, 48000, 44100):
            blocksize = max(256, int(round(STT_BLOCK_SIZE * sample_rate / STT_SAMPLE_RATE)))
            config = {
                "device": device_index,
                "samplerate": sample_rate,
                "channels": min(1, max_channels),
                "dtype": "float32",
                "blocksize": blocksize,
            }
            if config not in candidates:
                candidates.append(config)
        return candidates

    @staticmethod
    def _format_stream_error(exc: Exception) -> str:
        message = str(exc)
        hints = [
            "请确认 macOS 已允许此应用访问麦克风",
            "请确认当前麦克风没有被其他程序独占",
            "如果你外接了耳机/麦克风，重新选择一次输入设备后再试",
        ]
        if "PaErrorCode -9986" in message or "Internal PortAudio error" in message:
            hints.insert(0, "当前麦克风可能不支持程序尝试的采样率，程序已尝试自动回退")
        return "录音错误：{}\n\n{}".format(message, "\n".join(f"• {hint}" for hint in hints))

    # ── 模型加载 ──────────────────────────────

    def load_model(self) -> bool:
        if not SHERPA_AVAILABLE:
            self.error.emit("未找到 sherpa_onnx 模块\n请安装：pip install sherpa-onnx")
            return False

        if not MODEL_DIR.exists():
            self.error.emit(
                f"找不到模型目录：{MODEL_DIR.absolute()}\n\n"
                "请下载模型并放入 model/ 目录，参见 README.md"
            )
            return False

        encoder = self._find(MODEL_DIR, ["encoder-*.int8.onnx", "encoder-*.onnx", "encoder.int8.onnx", "encoder.onnx"])
        decoder = self._find(MODEL_DIR, ["decoder-*.int8.onnx", "decoder-*.onnx", "decoder.int8.onnx", "decoder.onnx"])
        joiner  = self._find(MODEL_DIR, ["joiner-*.int8.onnx",  "joiner-*.onnx",  "joiner.int8.onnx",  "joiner.onnx"])
        tokens  = self._find(MODEL_DIR, ["tokens.txt"])

        if encoder and decoder and joiner and tokens:
            try:
                self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                    encoder=str(encoder),
                    decoder=str(decoder),
                    joiner=str(joiner),
                    tokens=str(tokens),
                    num_threads=2,
                    sample_rate=STT_SAMPLE_RATE,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    enable_endpoint_detection=True,
                    rule1_min_trailing_silence=STT_RULE1_MIN_TRAILING_SILENCE,
                    rule2_min_trailing_silence=STT_RULE2_MIN_TRAILING_SILENCE,
                    rule3_min_utterance_length=STT_RULE3_MIN_UTTERANCE_LENGTH,
                )
                self._setup_decode_fn()
                print(f"[STT] Transducer 模型加载成功: {encoder.name}")
                return True
            except Exception as e:
                print(f"[STT] Transducer 加载失败: {e}")

        self.error.emit(
            "model/ 目录中未找到可用模型文件\n\n"
            "需要：encoder*.onnx + decoder*.onnx + joiner*.onnx + tokens.txt"
        )
        return False

    def _setup_decode_fn(self):
        """检测并绑定正确的 decode 方法（新版叫 decode_stream，旧版叫 decode）"""
        if hasattr(self.recognizer, 'decode_stream'):
            self._decode_fn = self.recognizer.decode_stream
        elif hasattr(self.recognizer, 'decode_streams'):
            # 部分版本只有 decode_streams（复数，接受列表）
            self._decode_fn = lambda s: self.recognizer.decode_streams([s])
        elif hasattr(self.recognizer, 'decode'):
            self._decode_fn = self.recognizer.decode
        else:
            # 找不到任何 decode 方法，列出所有方法供调试
            methods = [m for m in dir(self.recognizer) if not m.startswith('_')]
            raise AttributeError(f"找不到 decode 方法，可用方法：{methods}")

    @staticmethod
    def _find(directory: Path, patterns: list[str]) -> Optional[Path]:
        for pattern in patterns:
            matches = list(directory.glob(pattern))
            if matches:
                return matches[0]
        return None

    # ── 录音主循环 ────────────────────────────

    def start_recording(self):
        self.running = True
        self.start()

    def stop_recording(self):
        self.running = False

    def run(self):
        if self.recognizer is None:
            if not self.load_model():
                return

        stream    = self.recognizer.create_stream()
        last_text = ""

        def _audio_cb(indata, frames, time_info, status):
            mono = indata[:, 0].astype(np.float32, copy=False)
            if self._input_sample_rate != STT_SAMPLE_RATE:
                mono = self._resample_audio(mono, self._input_sample_rate, STT_SAMPLE_RATE)
            self._audio_q.put(mono)

        last_error: Exception | None = None
        for cfg in self._stream_candidates():
            try:
                self._input_sample_rate = int(cfg["samplerate"])
                print(f"[STT] 尝试打开麦克风: device={cfg['device']} samplerate={cfg['samplerate']}")
                with sd.InputStream(
                    samplerate=cfg["samplerate"],
                    channels=cfg["channels"],
                    dtype=cfg["dtype"],
                    blocksize=cfg["blocksize"],
                    device=cfg["device"],
                    callback=_audio_cb,
                ):
                    while self.running:
                        try:
                            chunk = self._audio_q.get(timeout=0.1)
                        except queue.Empty:
                            continue

                        stream.accept_waveform(STT_SAMPLE_RATE, chunk)

                        while self.recognizer.is_ready(stream):
                            self._decode_fn(stream)

                        result = self.recognizer.get_result(stream)
                        text   = _get_text(result)

                        if text and text != last_text:
                            self.text_partial.emit(text)
                            last_text = text

                        if self.recognizer.is_endpoint(stream):
                            if text:
                                self.text_final.emit(text)
                            self.recognizer.reset(stream)
                            stream    = self.recognizer.create_stream()
                            last_text = ""
                return
            except Exception as e:
                last_error = e
                print(f"[STT] 打开麦克风失败: {e}")

        if last_error is not None:
            self.error.emit(self._format_stream_error(last_error))
