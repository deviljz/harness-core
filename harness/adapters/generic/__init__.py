"""Generic adapter：无 Claude Code 时的接入（纯 CLI + git pre-commit 兜底）。

Claude Code 用 PostToolUse/Stop hook 自动跑 check；其他工具（Hermes/Cursor/CI）没有
auto-hook，靠手动跑 check 容易疲劳/漏检。git pre-commit 在提交前兜底跑 `harness check`，
拦住不绿的提交——工具无关、谁提交都生效。
"""
from __future__ import annotations

import stat
from pathlib import Path

_PRECOMMIT_MARKER = "harness-core pre-commit"

_PRECOMMIT_SCRIPT = """#!/bin/sh
# harness-core pre-commit: 提交前跑 harness check，红了拦住提交。
# harness 未安装则跳过（优雅降级，不打扰没装的协作者）。
# 跳过单次: git commit --no-verify
if command -v harness >/dev/null 2>&1; then
  harness check || {
    echo "[harness] check 未通过，提交被拦截。修复后重试，或 git commit --no-verify 跳过。" >&2
    exit 1
  }
fi
"""


def install_precommit_hook(project_root: Path) -> Path | None:
    """装 git pre-commit hook（跑 harness check 拦红提交）。

    返回写入的 hook 路径；以下情况返回 None（不动现有文件）：
    - 非 git 仓库（没有 .git/hooks/）
    - 已存在**非 harness** 的 pre-commit（不覆盖别人的 hook）
    """
    hooks_dir = Path(project_root) / ".git" / "hooks"
    if not hooks_dir.exists():
        return None

    hook = hooks_dir / "pre-commit"
    if hook.exists():
        existing = hook.read_text(encoding="utf-8", errors="replace")
        if _PRECOMMIT_MARKER not in existing:
            return None  # 别人的 hook，不覆盖

    hook.write_text(_PRECOMMIT_SCRIPT, encoding="utf-8")
    try:
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass  # Windows 不需要 exec 位
    return hook


__all__ = ["install_precommit_hook"]
