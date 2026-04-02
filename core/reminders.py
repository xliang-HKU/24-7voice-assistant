"""
core/reminders.py
提醒事项的解析、持久化与轮询调度。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

try:
    from PySide6.QtCore import QObject, QTimer, Signal
except ImportError:
    class _DummyBoundSignal:
        def connect(self, *args, **kwargs):
            return None

        def emit(self, *args, **kwargs):
            return None

    class Signal:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            self._signal = _DummyBoundSignal()

        def __get__(self, instance, owner):
            return self._signal

    class QObject:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            super().__init__()

    class QTimer:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            self.timeout = _DummyBoundSignal()

        def setInterval(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def stop(self):
            return None

import config


@dataclass
class ReminderDraft:
    title: str
    content: str
    due_at: datetime
    speak_text: str
    confirm_text: str = ""
    memory_summary: str = ""


@dataclass
class ReminderParseResult:
    ok: bool
    draft: ReminderDraft | None = None
    error: str = ""


class ReminderParser:
    TIME_NUMBER_PATTERN = r"(?:\d{1,2}|[零〇一二两三四五六七八九十]{1,3})"
    INTENT_KEYWORDS = (
        "提醒",
        "提醒我",
        "提醒一下",
        "记得",
        "别忘",
        "帮我记得",
        "帮我提醒",
        "闹钟",
        "待办",
    )
    IMPORTANT_ACTION_KEYWORDS = (
        "吃药",
        "复诊",
        "看医生",
        "看病",
        "检查",
        "拿药",
        "喝水",
        "开会",
        "出门",
        "睡觉",
    )
    CONFIRM_COMMANDS = {
        "确认",
        "确认提醒",
        "创建提醒",
        "保存提醒",
        "好",
        "好的",
        "好啊",
        "可以",
        "行",
        "嗯",
        "记下吧",
        "记着吧",
        "确认创建",
    }
    CANCEL_COMMANDS = {
        "取消",
        "取消提醒",
        "不用了",
        "算了",
        "先不用",
        "不创建",
        "不需要",
        "不用记",
        "别记了",
        "不要提醒",
    }
    RELATIVE_PATTERN = re.compile(
        rf"(?P<num>\d+|[零〇一二两三四五六七八九十]{{1,3}})\s*(?P<unit>分钟|分|小时|个小时|天)后"
    )
    DATE_PATTERN = re.compile(
        r"(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2}|今天|今晚|明天|后天|周[一二三四五六日天]|下周[一二三四五六日天])?"
        r"\s*"
        r"(?P<ampm>凌晨|早上|上午|中午|下午|傍晚|晚上)?"
        r"\s*"
        rf"(?P<hour>{TIME_NUMBER_PATTERN})"
        rf"(?:(?P<sep>[:点时])(?P<minute>{TIME_NUMBER_PATTERN})?)?"
        r"(?:钟)?"
        r"(?P<half>半)?"
        r"(?:分)?"
    )

    @classmethod
    def parse(cls, text: str, now: datetime | None = None) -> ReminderParseResult:
        now = now or datetime.now()
        raw = cls._normalize(text)
        due_at = cls._parse_relative(raw, now) or cls._parse_absolute(raw, now)
        if not due_at:
            return ReminderParseResult(
                ok=False,
                error="没识别出提醒时间。可以试试“明天下午3点提醒我开会”或“30分钟后提醒我喝水”。",
            )

        content = cls._extract_content(raw)
        if not content:
            return ReminderParseResult(ok=False, error="我识别到了时间，但没识别出提醒内容。")

        title = content[:18]
        speak_text = f"提醒你，{content}"
        return ReminderParseResult(
            ok=True,
            draft=ReminderDraft(title=title, content=content, due_at=due_at, speak_text=speak_text),
        )

    @classmethod
    def looks_like_reminder_request(cls, text: str) -> bool:
        raw = cls._normalize(text)
        if not raw:
            return False

        result = cls.parse(raw)
        if not (result.ok and result.draft):
            return False

        has_keyword = any(keyword in raw for keyword in cls.INTENT_KEYWORDS)
        has_action = any(keyword in raw for keyword in cls.IMPORTANT_ACTION_KEYWORDS)
        return has_keyword or has_action

    @classmethod
    def is_confirm_command(cls, text: str) -> bool:
        raw = cls._normalize_command(text)
        if not raw:
            return False
        if cls._contains_cancel_intent(raw):
            return False
        return raw in cls.CONFIRM_COMMANDS or cls._contains_confirm_intent(raw)

    @classmethod
    def is_cancel_command(cls, text: str) -> bool:
        raw = cls._normalize_command(text)
        if not raw:
            return False
        if raw in cls.CANCEL_COMMANDS:
            return True
        return cls._contains_cancel_intent(raw)

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.strip()
        text = text.replace("：", ":").replace("，", " ").replace("。", " ")
        return re.sub(r"\s+", " ", text)

    @classmethod
    def _normalize_command(cls, text: str) -> str:
        raw = cls._normalize(text)
        return re.sub(r"[\s,，。.!！?？;；:：、~]+", "", raw)

    @staticmethod
    def _contains_confirm_intent(raw: str) -> bool:
        return any(
            token in raw
            for token in (
                "确认",
                "创建提醒",
                "保存提醒",
                "记下",
                "记着",
                "好的",
                "好呀",
                "好啊",
                "好呢",
                "可以",
                "行的",
                "行啊",
                "没问题",
                "是的",
            )
        ) or raw in {"好", "行", "嗯", "要"}

    @staticmethod
    def _contains_cancel_intent(raw: str) -> bool:
        return any(
            token in raw
            for token in (
                "取消",
                "不用",
                "先不用",
                "不需要",
                "不要",
                "算了",
                "别记",
                "不创建",
                "不记",
            )
        )

    @classmethod
    def _parse_relative(cls, text: str, now: datetime) -> datetime | None:
        m = cls.RELATIVE_PATTERN.search(text)
        if not m:
            return None

        num = cls._parse_time_number(m.group("num"))
        if num is None:
            return None
        unit = m.group("unit")
        if unit in {"分钟", "分"}:
            return now + timedelta(minutes=num)
        if unit in {"小时", "个小时"}:
            return now + timedelta(hours=num)
        if unit == "天":
            return now + timedelta(days=num)
        return None

    @classmethod
    def _parse_absolute(cls, text: str, now: datetime) -> datetime | None:
        m = cls.DATE_PATTERN.search(text)
        if not m:
            return None

        hour = cls._parse_time_number(m.group("hour"))
        minute = 30 if m.group("half") else cls._parse_time_number(m.group("minute"), default=0)
        if hour is None or minute is None or hour > 23 or minute > 59:
            return None
        ampm = m.group("ampm") or ""

        if ampm in {"下午", "傍晚", "晚上"} and hour < 12:
            hour += 12
        elif ampm == "中午" and hour < 11:
            hour += 12
        elif ampm == "凌晨" and hour == 12:
            hour = 0
        elif not ampm and 1 <= hour <= 6:
            hour += 12

        base_day = now.date()
        date_token = m.group("date") or ""
        if date_token == "今晚":
            if hour < 12:
                hour += 12
        elif date_token == "明天":
            base_day = (now + timedelta(days=1)).date()
        elif date_token == "后天":
            base_day = (now + timedelta(days=2)).date()
        elif date_token.startswith("下周"):
            target = cls._weekday_to_int(date_token[-1])
            if target is None:
                return None
            current = now.weekday()
            delta = (target - current) % 7
            delta = 7 if delta == 0 else delta + 7
            base_day = (now + timedelta(days=delta)).date()
        elif date_token.startswith("周"):
            target = cls._weekday_to_int(date_token[-1])
            if target is None:
                return None
            current = now.weekday()
            delta = (target - current) % 7
            base_day = (now + timedelta(days=delta)).date()
        elif date_token and date_token not in {"今天", "明天", "后天"}:
            try:
                base_day = datetime.strptime(date_token.replace("/", "-"), "%Y-%m-%d").date()
            except ValueError:
                return None

        try:
            due_at = datetime(
                year=base_day.year,
                month=base_day.month,
                day=base_day.day,
                hour=hour,
                minute=minute,
            )
        except ValueError:
            return None

        if not date_token and due_at <= now:
            due_at += timedelta(days=1)
        return due_at

    @staticmethod
    def _weekday_to_int(ch: str) -> int | None:
        mapping = {
            "一": 0,
            "二": 1,
            "三": 2,
            "四": 3,
            "五": 4,
            "六": 5,
            "日": 6,
            "天": 6,
        }
        return mapping.get(ch)

    @classmethod
    def _parse_time_number(cls, token: str | None, default: int | None = None) -> int | None:
        if token is None:
            return default

        token = token.strip()
        if not token:
            return default
        if token.isdigit():
            return int(token)

        normalized = token.replace("〇", "零").replace("两", "二")
        if "十" in normalized:
            left, right = normalized.split("十", 1)
            tens = 1 if not left else cls._parse_digit_string(left)
            ones = 0 if not right else cls._parse_digit_string(right)
            if tens is None or ones is None:
                return None
            return tens * 10 + ones

        return cls._parse_digit_string(normalized)

    @staticmethod
    def _parse_digit_string(token: str) -> int | None:
        mapping = {
            "零": "0",
            "一": "1",
            "二": "2",
            "三": "3",
            "四": "4",
            "五": "5",
            "六": "6",
            "七": "7",
            "八": "8",
            "九": "9",
        }
        digits = []
        for ch in token:
            digit = mapping.get(ch)
            if digit is None:
                return None
            digits.append(digit)
        return int("".join(digits)) if digits else None

    @classmethod
    def _extract_content(cls, text: str) -> str:
        cleaned = cls.RELATIVE_PATTERN.sub(" ", text)
        cleaned = cls.DATE_PATTERN.sub(" ", cleaned, count=1)
        cleaned = re.sub(
            r"(提醒我|提醒一下|提醒|记得|帮我记得|帮我提醒|到时候|别忘了?|设个闹钟|定个闹钟|设个提醒|定个提醒)",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"^(我|我要|我得|我得要|我想)\s*", "", cleaned)
        cleaned = re.sub(r"^(点钟|点|钟|时|的时候|时候)\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，。")
        return cleaned


class ReminderManager:
    def __init__(self, filepath: Path = config.REMINDERS_FILE):
        self.filepath = filepath
        self.records: list[dict] = []
        self._load()

    def _load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def _save(self):
        self.filepath.parent.mkdir(exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def add(self, draft: ReminderDraft) -> dict:
        now = datetime.now()
        reminder = {
            "id": str(uuid4()),
            "title": draft.title,
            "content": draft.content,
            "speak_text": draft.speak_text,
            "memory_summary": draft.memory_summary,
            "due_at": draft.due_at.isoformat(),
            "status": "pending",
            "created_at": now.isoformat(),
            "triggered_at": "",
        }
        self.records.append(reminder)
        self.records.sort(key=lambda item: item["due_at"])
        self._save()
        return reminder

    def update(self, reminder_id: str, **fields) -> dict | None:
        for reminder in self.records:
            if reminder.get("id") != reminder_id:
                continue
            for key, value in fields.items():
                reminder[key] = value
            self.records.sort(key=lambda item: item["due_at"])
            self._save()
            return reminder
        return None

    def get_pending(self) -> list[dict]:
        return [r for r in self.records if r.get("status") == "pending"]

    def due_now(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        due_items: list[dict] = []
        for reminder in self.get_pending():
            try:
                due_at = datetime.fromisoformat(reminder["due_at"])
            except Exception:
                continue
            if due_at <= now:
                due_items.append(reminder)
        return due_items

    def mark_triggered(self, reminder_id: str):
        now = datetime.now().isoformat()
        for reminder in self.records:
            if reminder["id"] == reminder_id:
                reminder["status"] = "triggered"
                reminder["triggered_at"] = now
                self._save()
                return

    @property
    def pending_count(self) -> int:
        return len(self.get_pending())

    def next_due(self) -> dict | None:
        pending = self.get_pending()
        return pending[0] if pending else None


class ReminderScheduler(QObject):
    reminder_due = Signal(dict)

    def __init__(self, manager: ReminderManager, interval_sec: int = config.REMINDER_POLL_INTERVAL_SEC):
        super().__init__()
        self.manager = manager
        self.timer = QTimer(self)
        self.timer.setInterval(max(5, interval_sec) * 1000)
        self.timer.timeout.connect(self.check_due)

    def start(self):
        self.timer.start()
        self.check_due()

    def stop(self):
        self.timer.stop()

    def check_due(self):
        for reminder in self.manager.due_now():
            self.manager.mark_triggered(reminder["id"])
            self.reminder_due.emit(reminder)
