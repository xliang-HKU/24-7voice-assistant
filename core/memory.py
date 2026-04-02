"""
core/memory.py
长期记忆管理：
1. 保存完整对话历史
2. 额外抽取与维护用户人物事实记忆
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import (
    MEMORY_CONTEXT_TURNS,
    MEMORY_FILE,
    MEMORY_SEARCH_TOP_K,
    PROFILE_MEMORY_FILE,
    PROFILE_MEMORY_TOP_K,
)


class MemoryManager:
    """
    - records: 完整对话历史
    - facts: 用户人物事实记忆
    """

    _RELATION_WORDS = (
        "女儿",
        "儿子",
        "老伴",
        "老婆",
        "丈夫",
        "先生",
        "太太",
        "爱人",
        "孙子",
        "孙女",
        "外孙",
        "外孙女",
        "哥哥",
        "姐姐",
        "弟弟",
        "妹妹",
    )
    _HEALTH_WORDS = (
        "高血压",
        "糖尿病",
        "失眠",
        "心脏病",
        "冠心病",
        "胃病",
        "关节炎",
        "腰疼",
        "头晕",
        "哮喘",
        "白内障",
        "焦虑",
        "抑郁",
        "咳嗽",
    )
    _RELATION_PATTERN = re.compile(
        rf"(?:我(?:的)?)(?P<relation>{'|'.join(_RELATION_WORDS)})(?:名字?叫|叫)(?P<name>[\u4e00-\u9fa5A-Za-z0-9·]{1,12})"
    )
    _RELATION_PATTERN_ALT = re.compile(
        rf"(?P<relation>{'|'.join(_RELATION_WORDS)})(?:名字?叫|叫)(?P<name>[\u4e00-\u9fa5A-Za-z0-9·]{1,12})"
    )
    _HEALTH_PATTERN = re.compile(
        rf"我(?:最近|一直|有点|有|得了|患有|老是|总是)?(?P<condition>{'|'.join(_HEALTH_WORDS)})"
    )
    _SCHEDULE_PATTERN = re.compile(
        r"我(?P<plan>(?:今天|明天|后天|周[一二三四五六日天]|下周[一二三四五六日天])"
        r"[^，。！？]{0,14}(?:复诊|看医生|去医院|看病|检查|体检|拿药|做检查|开会|出门|回家))"
    )
    _BACKGROUND_PATTERN = re.compile(
        r"我(?:退休前|以前)是(?P<value>[^，。！？]{1,12})"
    )
    _LOCATION_PATTERN = re.compile(
        r"我住在(?P<place>[^，。！？]{1,12})"
    )

    def __init__(
        self,
        filepath: Path = MEMORY_FILE,
        profile_filepath: Path = PROFILE_MEMORY_FILE,
    ):
        self.filepath = filepath
        self.profile_filepath = profile_filepath
        self.records: list[dict] = []
        self.facts: list[dict] = []
        self._load_records()
        self._load_facts()

    # ── 持久化 ────────────────────────────────

    def _load_records(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def _save_records(self):
        self.filepath.parent.mkdir(exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def _load_facts(self):
        if self.profile_filepath.exists():
            try:
                with open(self.profile_filepath, "r", encoding="utf-8") as f:
                    self.facts = json.load(f)
            except Exception:
                self.facts = []

    def _save_facts(self):
        self.profile_filepath.parent.mkdir(exist_ok=True)
        with open(self.profile_filepath, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, ensure_ascii=False, indent=2)

    # ── 对话历史 ──────────────────────────────

    def add(self, role: str, content: str, source: str = "text") -> dict:
        now = datetime.now()
        record = {
            "id": len(self.records),
            "role": role,
            "content": content,
            "source": source,
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }
        self.records.append(record)
        self._save_records()
        return record

    def search(self, query: str, top_k: int = MEMORY_SEARCH_TOP_K) -> list[dict]:
        date_filter = self._parse_date_filter(query)
        keywords = self._extract_keywords(query)

        results: list[tuple[float, dict]] = []
        for rec in self.records:
            if date_filter and rec["date"] != date_filter:
                continue

            text = rec["content"].lower()
            score = 0.0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in text:
                    score += 2.0
                else:
                    hits = sum(1 for ch in kw_lower if ch in text)
                    score += hits * 0.3

            if score > 0:
                results.append((score, rec))

        results.sort(key=lambda item: -item[0])
        return [record for _, record in results[:top_k]]

    def _parse_date_filter(self, query: str) -> Optional[str]:
        today = datetime.now()
        if re.search(r"今天|today", query, re.IGNORECASE):
            return today.strftime("%Y-%m-%d")
        if re.search(r"昨天|yesterday", query, re.IGNORECASE):
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        if re.search(r"明天|tomorrow", query, re.IGNORECASE):
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        match = re.search(r"\d{4}-\d{2}-\d{2}", query)
        if match:
            return match.group()
        return None

    def _extract_keywords(self, query: str) -> list[str]:
        stopwords = {
            "帮我",
            "查一下",
            "查找",
            "搜索",
            "告诉我",
            "的",
            "了",
            "吗",
            "呢",
            "什么",
            "有",
            "没有",
            "是",
            "search",
            "find",
            "what",
            "tell",
            "me",
            "帮",
            "查",
            "我",
            "一下",
            "请",
            "能",
            "可以",
            "要",
            "想",
        }
        tokens = re.split(r"[\s,，。？！、\?!\n]+", query)
        return [token for token in tokens if token and token not in stopwords]

    def get_recent(self, n: int = 20) -> list[dict]:
        return self.records[-n:]

    def get_ai_messages(self, n: int = MEMORY_CONTEXT_TURNS) -> list[dict]:
        recent = [record for record in self.records if record["role"] in ("user", "assistant")]
        recent = recent[-(n * 2) :]
        return [{"role": record["role"], "content": record["content"]} for record in recent]

    # ── 人物事实记忆 ──────────────────────────

    def extract_and_store_user_facts(self, text: str) -> list[dict]:
        candidates = self._extract_fact_candidates(text)
        saved: list[dict] = []
        for item in candidates:
            saved.append(self.remember_fact(**item))
        return saved

    def remember_schedule_fact(self, summary: str, evidence: str = "", key: str = "") -> dict:
        return self.remember_fact(
            category="schedule",
            key=key or f"schedule:{summary}",
            summary=summary,
            evidence=evidence or summary,
            priority=80,
        )

    def remember_fact(
        self,
        category: str,
        key: str,
        summary: str,
        evidence: str,
        priority: int = 50,
    ) -> dict:
        now = datetime.now().isoformat()
        for fact in self.facts:
            if fact.get("key") == key:
                fact["summary"] = summary
                fact["evidence"] = evidence
                fact["priority"] = max(priority, int(fact.get("priority", 0)))
                fact["updated_at"] = now
                self._save_facts()
                return fact

        fact = {
            "key": key,
            "category": category,
            "summary": summary,
            "evidence": evidence,
            "priority": priority,
            "created_at": now,
            "updated_at": now,
        }
        self.facts.append(fact)
        self.facts.sort(
            key=lambda item: (int(item.get("priority", 0)), item.get("updated_at", "")),
            reverse=True,
        )
        self._save_facts()
        return fact

    def _extract_fact_candidates(self, text: str) -> list[dict]:
        normalized = self._normalize(text)
        candidates: list[dict] = []

        relation_match = self._RELATION_PATTERN.search(normalized) or self._RELATION_PATTERN_ALT.search(normalized)
        if relation_match:
            relation = relation_match.group("relation")
            name = relation_match.group("name")
            candidates.append(
                {
                    "category": "family",
                    "key": f"family:{relation}",
                    "summary": f"你的{relation}叫{name}",
                    "evidence": text,
                    "priority": 95,
                }
            )

        health_match = self._HEALTH_PATTERN.search(normalized)
        if health_match:
            condition = health_match.group("condition")
            candidates.append(
                {
                    "category": "health",
                    "key": f"health:{condition}",
                    "summary": f"你提过自己有{condition}",
                    "evidence": text,
                    "priority": 100,
                }
            )

        schedule_match = self._SCHEDULE_PATTERN.search(normalized)
        if schedule_match:
            plan = schedule_match.group("plan").strip()
            candidates.append(
                {
                    "category": "schedule",
                    "key": f"schedule:{plan}",
                    "summary": f"你提过{plan}",
                    "evidence": text,
                    "priority": 85,
                }
            )

        background_match = self._BACKGROUND_PATTERN.search(normalized)
        if background_match:
            value = background_match.group("value").strip()
            candidates.append(
                {
                    "category": "background",
                    "key": f"background:{value}",
                    "summary": f"你退休前是{value}",
                    "evidence": text,
                    "priority": 75,
                }
            )

        location_match = self._LOCATION_PATTERN.search(normalized)
        if location_match:
            place = location_match.group("place").strip()
            candidates.append(
                {
                    "category": "location",
                    "key": f"location:{place}",
                    "summary": f"你住在{place}",
                    "evidence": text,
                    "priority": 65,
                }
            )

        return candidates

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.strip().replace("，", " ").replace("。", " ")
        return re.sub(r"\s+", " ", text)

    def get_facts(self, limit: int = PROFILE_MEMORY_TOP_K) -> list[dict]:
        return sorted(
            self.facts,
            key=lambda item: (-int(item.get("priority", 0)), item.get("updated_at", "")),
        )[:limit]

    def build_fact_prompt(self, limit: int = PROFILE_MEMORY_TOP_K) -> str:
        facts = self.get_facts(limit=limit)
        if not facts:
            return "暂无长期人物记忆。"
        return "\n".join(f"- {fact['summary']}" for fact in facts)

    def build_recent_prompt(self, limit: int = 6) -> str:
        recent = self.get_recent(limit)
        if not recent:
            return "暂无最近对话。"
        rows: list[str] = []
        for record in recent:
            role = "用户" if record["role"] == "user" else "助手"
            rows.append(f"- [{record['date']} {record['time']}] {role}：{record['content']}")
        return "\n".join(rows)

    # ── 统计 ──────────────────────────────────

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def user_count(self) -> int:
        return sum(1 for record in self.records if record["role"] == "user")

    @property
    def fact_count(self) -> int:
        return len(self.facts)
