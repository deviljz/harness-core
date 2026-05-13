"""active_tasks_helper：让 AI 把 subagent todo 状态写到 .harness/active_tasks.json

格式：{"pending": ["subj1", "subj2"], "completed": ["subj3"]}

用法（AI 在 harness-full skill 里调用）：
    from harness.adapters.claude_code.active_tasks_helper import (
        write_active_tasks,
        mark_completed,
        clear_active_tasks,
    )

    # 开始时登记所有待做项
    write_active_tasks(project_root, pending=["execute", "check", "review", "commit"])

    # 每步完成后更新
    mark_completed(project_root, "execute")

    # 全部完成后清空（允许 Stop）
    clear_active_tasks(project_root)

Stop hook（check_active_tasks.py）会读这个文件：
- 有 pending → exit 2（阻止停止，返回 reason 让 Claude 继续）
- 无文件或 pending 为空 → exit 0（允许停止）
"""
from __future__ import annotations

import json
from pathlib import Path

ACTIVE_TASKS_FILE = ".harness/active_tasks.json"


def _tasks_path(project_root: Path) -> Path:
    return project_root / ACTIVE_TASKS_FILE


def write_active_tasks(
    project_root: Path,
    pending: list[str],
    completed: list[str] | None = None,
) -> None:
    """写入（或覆盖）active_tasks.json。"""
    harness_dir = project_root / ".harness"
    harness_dir.mkdir(exist_ok=True)
    data = {"pending": list(pending), "completed": list(completed or [])}
    _tasks_path(project_root).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def mark_completed(project_root: Path, task: str) -> None:
    """把 task 从 pending 移到 completed。文件不存在时静默。"""
    path = _tasks_path(project_root)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    pending = [t for t in data.get("pending", []) if t != task]
    completed = data.get("completed", [])
    if task not in completed:
        completed = [*completed, task]

    path.write_text(
        json.dumps({"pending": pending, "completed": completed}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clear_active_tasks(project_root: Path) -> None:
    """清空 pending（全部完成），允许 Stop hook 放行。"""
    path = _tasks_path(project_root)
    if path.exists():
        path.write_text(
            json.dumps({"pending": [], "completed": []}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def read_active_tasks(project_root: Path) -> dict:
    """读取 active_tasks.json，文件不存在返回空结构。"""
    path = _tasks_path(project_root)
    if not path.exists():
        return {"pending": [], "completed": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pending": [], "completed": []}
