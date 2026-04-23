"""Claude Code 适配器：往 .claude/settings.json 注册 hook"""
from __future__ import annotations

from .install_hooks import install_hooks, uninstall_hooks

__all__ = ["install_hooks", "uninstall_hooks"]
