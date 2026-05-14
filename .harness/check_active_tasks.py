#!/usr/bin/env python
"""harness active-tasks Stop hook

由 `harness init` 自动生成。读 .harness/active_tasks.json：
- pending 非空 → exit 2，输出 reason 让 Claude 继续
- 文件不存在或 pending 为空 → exit 0，正常停止
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path


def main() -> int:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    tasks_file = Path(project_dir) / ".harness" / "active_tasks.json"

    if not tasks_file.exists():
        return 0  # 没有文件 → 没有待办 → 允许停

    try:
        data = json.loads(tasks_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0  # 读取失败 → 静默放行

    pending = data.get("pending", [])
    if not pending:
        return 0  # 全部完成 → 允许停

    # 有未完成任务 → exit 2 触发 Claude 继续
    tasks_str = ", ".join(pending)
    print(
        f"[harness] 还有未完成的任务: {tasks_str}\n"
        f"请继续执行下一个任务，不要停下来。",
        flush=True,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
