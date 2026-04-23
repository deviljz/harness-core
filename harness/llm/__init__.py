"""LLM provider 抽象 + 注册表。

核心层调 `get_provider(name).complete(prompt)`，不知道背后是 Claude/Manual/未来其他。
"""
from __future__ import annotations

from .base import LLMProvider

# 具体 provider 的 import 放在函数里，避免循环依赖
_REGISTRY: dict[str, type[LLMProvider]] = {}


def _populate_registry():
    global _REGISTRY
    from .providers.claude_agent import ClaudeAgentProvider
    from .providers.manual import ManualProvider

    _REGISTRY = {
        "claude_agent": ClaudeAgentProvider,
        "manual": ManualProvider,
    }


def get_provider(name: str, config: dict | None = None) -> LLMProvider:
    if not _REGISTRY:
        _populate_registry()
    if name not in _REGISTRY:
        raise ValueError(f"Unknown LLM provider: {name}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name](config or {})


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    if not _REGISTRY:
        _populate_registry()
    _REGISTRY[name] = cls


def list_providers() -> list[str]:
    if not _REGISTRY:
        _populate_registry()
    return sorted(_REGISTRY.keys())


__all__ = ["LLMProvider", "get_provider", "register_provider", "list_providers"]
