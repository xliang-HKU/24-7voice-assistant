"""
core/memory.py
记忆管理器 —— 持久化所有对话，支持关键词 + 时间过滤搜索
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import MEMORY_FILE, MEMORY_CONTEXT_TURNS, MEMORY_SEARCH_TOP_K


class MemoryManager:
    """
    将每条对话以 JSON 行存储到 memory.json。
    提供:
      - add()         添加一条记录
      - search()      关键词 + 时间过滤搜索
      - get_recent()  取最近 N 条原始记录
      - get_ai_messages()  格式化为 AI messages 列表
    """

    def __init__(self, filepath: Path = MEMORY_FILE):
        self.filepath = filepath
        self.records: list[dict] = []
        self._load()

    # ── 持久化 ────────────────────────────────

    def _load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    # ── 写入 ──────────────────────────────────

    def add(self, role: str, content: str, source: str = "text") -> dict:
        """
        添加一条记录
        :param role:    "user" | "assistant" | "system"
        :param content: 文本内容
        :param source:  "voice" | "text"
        :return: 新记录 dict
        """
        now = datetime.now()
        record = {
            "id":        len(self.records),
            "role":      role,
            "content":   content,
            "source":    source,
            "timestamp": now.isoformat(),
            "date":      now.strftime("%Y-%m-%d"),
            "time":      now.strftime("%H:%M:%S"),
        }
        self.records.append(record)
        self._save()
        return record

    # ── 搜索 ──────────────────────────────────

    def search(self, query: str, top_k: int = MEMORY_SEARCH_TOP_K) -> list[dict]:
        """
        关键词搜索 + 日期过滤。
        支持"今天 / 明天 / 昨天"等自然语言时间词。
        """
        date_filter = self._parse_date_filter(query)
        keywords    = self._extract_keywords(query)

        results: list[tuple[float, dict]] = []
        for rec in self.records:
            # 日期过滤
            if date_filter and rec["date"] != date_filter:
                continue

            text  = rec["content"].lower()
            score = 0.0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in text:
                    score += 2.0
                else:
                    # 部分字符命中（中文逐字匹配）
                    hits = sum(1 for ch in kw_lower if ch in text)
                    score += hits * 0.3

            if score > 0:
                results.append((score, rec))

        results.sort(key=lambda x: -x[0])
        return [r for _, r in results[:top_k]]

    def _parse_date_filter(self, query: str) -> Optional[str]:
        today = datetime.now()
        if re.search(r"今天|today", query, re.IGNORECASE):
            return today.strftime("%Y-%m-%d")
        if re.search(r"昨天|yesterday", query, re.IGNORECASE):
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        if re.search(r"明天|tomorrow", query, re.IGNORECASE):
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        # 匹配 YYYY-MM-DD
        m = re.search(r"\d{4}-\d{2}-\d{2}", query)
        if m:
            return m.group()
        return None

    def _extract_keywords(self, query: str) -> list[str]:
        """去掉常见虚词，剩余词作为关键词"""
        stopwords = {
            "帮我", "查一下", "查找", "搜索", "告诉我", "的", "了", "吗", "呢",
            "什么", "有", "没有", "是", "search", "find", "what", "tell", "me",
            "帮", "查", "我", "一下", "请", "能", "可以", "要", "想",
        }
        tokens = re.split(r'[\s,，。？！、\?!\n]+', query)
        return [t for t in tokens if t and t not in stopwords and len(t) > 0]

    # ── 读取 ──────────────────────────────────

    def get_recent(self, n: int = 20) -> list[dict]:
        """返回最近 n 条记录（所有 role）"""
        return self.records[-n:]

    def get_ai_messages(self, n: int = MEMORY_CONTEXT_TURNS) -> list[dict]:
        """
        返回最近 n 轮对话，格式化为 OpenAI/DeepSeek messages 列表
        只包含 user / assistant 角色
        """
        recent = [r for r in self.records if r["role"] in ("user", "assistant")]
        recent = recent[-(n * 2):]
        return [{"role": r["role"], "content": r["content"]} for r in recent]

    # ── 统计 ──────────────────────────────────

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def user_count(self) -> int:
        return sum(1 for r in self.records if r["role"] == "user")
