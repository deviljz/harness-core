"""LLMProvider 抽象基类。

接口刻意极简：1 个方法。足以覆盖 review/execute 层的需求。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def complete(self, prompt: str, context: dict | None = None) -> str:
        """给 prompt，返回 LLM 回复。

        context 可选，用于 provider 特定能力（比如 claude_agent 里指定 subagent_type）。
        """


class LLMError(Exception):
    """LLM 调用失败"""
