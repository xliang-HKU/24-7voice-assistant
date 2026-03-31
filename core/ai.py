"""
core/ai.py
DeepSeek AI 处理器
"""
from datetime import datetime
from typing import Callable, Optional

from openai import OpenAI

import config
from core.memory import MemoryManager


CHAT_SYSTEM = """\
你是一个智能语音助手，帮助用户回答问题、管理信息。
回复简洁自然，像朋友聊天，不要废话。
使用中文回复，除非用户使用其他语言。
当前时间：{current_time}
"""

SEARCH_SYSTEM = """\
你是一个智能语音助手，负责帮用户整理和回顾历史记录。
下面是从历史对话中检索到的相关记录，请基于这些内容整理后简洁回复用户。
引用内容时注明时间，例如"你在 XX月XX日 提到过..."。
如果没有找到相关记录，直接告知用户未找到。
当前时间：{current_time}

【检索到的历史记录】
{records}
"""


class AIProcessor:

    def __init__(self, memory: MemoryManager, api_key: str = ""):
        self.memory = memory
        # 优先用传入的 key，否则直接读 config
        key = api_key or config.DEEPSEEK_API_KEY
        self.client = OpenAI(
            api_key=key,
            base_url=config.DEEPSEEK_BASE_URL,
        )

    def update_api_key(self, api_key: str):
        key = api_key or config.DEEPSEEK_API_KEY
        self.client = OpenAI(
            api_key=key,
            base_url=config.DEEPSEEK_BASE_URL,
        )

    # ── 普通对话 ──────────────────────────────

    def chat(self, user_message: str, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        system   = CHAT_SYSTEM.format(current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"))
        history  = self.memory.get_ai_messages()
        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_message}]
        return self._stream(messages, on_chunk)

    # ── 搜索历史并回复 ────────────────────────

    def search_and_reply(self, query: str, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        results = self.memory.search(query)
        if results:
            records_text = ""
            for r in results:
                role_label = "用户" if r["role"] == "user" else "助手"
                records_text += f"[{r['date']} {r['time']}] {role_label}：{r['content']}\n"
        else:
            records_text = "（未找到相关记录）"

        system   = SEARCH_SYSTEM.format(
            current_time=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
            records=records_text,
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": query},
        ]
        return self._stream(messages, on_chunk)

    # ── 内部流式请求 ──────────────────────────

    def _stream(self, messages: list, on_chunk: Optional[Callable[[str], None]]) -> str:
        full = ""
        try:
            stream = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                stream=True,
                max_tokens=1024,
                temperature=0.7,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full += delta.content
                    if on_chunk:
                        on_chunk(delta.content)
        except Exception as e:
            err = str(e)
            if "401" in err or "authentication" in err.lower():
                full = "❌ API Key 无效或已过期，请检查 config.py 中的 DEEPSEEK_API_KEY"
            elif "429" in err or "rate limit" in err.lower():
                full = "⚠️ 请求过于频繁，请稍后再试"
            else:
                full = f"❌ 请求失败：{err}"
        return full