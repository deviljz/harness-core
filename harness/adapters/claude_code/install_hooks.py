"""往项目的 .claude/settings.json 注册 harness hook。

PostToolUse(Edit|Write) → run_hook.py check --on-edit <file>
Stop → run_hook.py check --gate

设计：
- 默认写 .claude/settings.json（入 git 共享）
- hook 命令调 .harness/run_hook.py（跨平台 Python 脚本）
- run_hook.py 自动检测 harness 是否安装，没装就静默跳过（对没装 harness 的协作者无感）
- 幂等：重复跑不会重复加
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

HOOK_MARKER = "harness-core"
ACTIVE_TASKS_MARKER = "harness-active-tasks"
_COMMANDS_SRC = Path(__file__).parent / "commands"


# check_active_tasks.py: 装在项目 .harness/ 下，Stop hook 调它。
# 作用：读 .harness/active_tasks.json，有未完成任务时 exit 2 阻止 Claude 停下来。
# 格式：{"pending": ["step1", ...], "completed": ["step0"]}
CHECK_ACTIVE_TASKS_SCRIPT = '''#!/usr/bin/env python
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
        f"[harness] 还有未完成的任务: {tasks_str}\\n"
        f"请继续执行下一个任务，不要停下来。",
        flush=True,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
'''


# run_hook.py: 装在项目 .harness/ 下，hook 调它。
# 作用：检测 harness 是否在 PATH；在就跑，不在就静默 exit 0。
# 跨平台：用 python 写，Windows/macOS/Linux 都能跑。
RUN_HOOK_SCRIPT = '''#!/usr/bin/env python
"""harness hook wrapper：没装 harness 就静默跳过（优雅降级）

这个脚本由 `harness init` 自动生成并安装到 .claude/settings.json 调用。
手改请小心——下次 harness init --force 会覆盖。
"""
from __future__ import annotations
import shutil
import subprocess
import sys


def main() -> int:
    exe = shutil.which("harness")
    if not exe:
        # 协作者没装 harness → 静默跳过，不打扰他
        return 0
    try:
        result = subprocess.run([exe, *sys.argv[1:]], check=False)
        return result.returncode
    except Exception as e:
        print(f"[harness hook] exec failed: {e}", file=sys.stderr)
        return 0  # 不阻塞对话


if __name__ == "__main__":
    sys.exit(main())
'''


def install_hooks(
    project_root: Path,
    scope: Literal["shared", "local"] = "shared",
    with_gate: bool = False,
    with_active_tasks: bool = True,
) -> Path:
    """注册 hook。返回被写入的 settings 文件路径。

    with_gate=False（默认）：只装 PostToolUse（每次 Edit/Write 后增量验证）
    with_gate=True：额外装 Stop hook（每轮对话结束跑 --gate 全量校验）
    with_active_tasks=True（默认）：装 check_active_tasks.py + Stop hook，
        让 harness-full 多 subagent 跑完前阻止 Claude 中途停止
    """
    # 1) 写 run_hook.py + check_active_tasks.py
    harness_dir = project_root / ".harness"
    harness_dir.mkdir(exist_ok=True)
    wrapper = harness_dir / "run_hook.py"
    wrapper.write_text(RUN_HOOK_SCRIPT, encoding="utf-8")

    if with_active_tasks:
        check_script = harness_dir / "check_active_tasks.py"
        check_script.write_text(CHECK_ACTIVE_TASKS_SCRIPT, encoding="utf-8")

    # 2) 更新 settings
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(exist_ok=True)
    filename = "settings.local.json" if scope == "local" else "settings.json"
    settings_path = claude_dir / filename

    data = {}
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    hooks = data.setdefault("hooks", {})

    # 用 python 调 wrapper，$CLAUDE_PROJECT_DIR 保证任何 cwd 下都能找到 wrapper
    on_edit_cmd = f'python "$CLAUDE_PROJECT_DIR/.harness/run_hook.py" check --on-edit "$CLAUDE_TOOL_FILE_PATH" --warn-only  # {HOOK_MARKER}'
    gate_cmd = f'python "$CLAUDE_PROJECT_DIR/.harness/run_hook.py" check --gate  # {HOOK_MARKER}'

    post = hooks.setdefault("PostToolUse", [])
    if not _already_installed(post, HOOK_MARKER):
        post.append(
            {
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [{"type": "command", "command": on_edit_cmd}],
            }
        )

    if with_active_tasks and not with_gate:
        # active_tasks 已能阻止 stop，老的 gate Stop hook 冗余 → 清掉
        stop = hooks.get("Stop", [])
        stop[:] = [e for e in stop if not _already_installed([e], HOOK_MARKER)]
        if stop:
            hooks["Stop"] = stop
        else:
            hooks.pop("Stop", None)

    if with_gate:
        stop = hooks.setdefault("Stop", [])
        if not _already_installed(stop, HOOK_MARKER):
            stop.append({"hooks": [{"type": "command", "command": gate_cmd}]})

    if with_active_tasks:
        active_tasks_cmd = f'python "$CLAUDE_PROJECT_DIR/.harness/check_active_tasks.py"  # {ACTIVE_TASKS_MARKER}'
        stop = hooks.setdefault("Stop", [])
        if not _already_installed(stop, ACTIVE_TASKS_MARKER):
            stop.append({"hooks": [{"type": "command", "command": active_tasks_cmd}]})

    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 3) 安装 slash commands 到 .claude/commands/
    _install_commands(claude_dir)

    # 4) 安装 skills 到 .claude/skills/
    _install_skills(claude_dir)

    return settings_path


def _install_commands(claude_dir: Path) -> list[Path]:
    """复制 harness-* slash command 到项目 .claude/commands/。已存在则覆盖（保持最新）。"""
    dst_dir = claude_dir / "commands"
    dst_dir.mkdir(exist_ok=True)
    installed: list[Path] = []
    if not _COMMANDS_SRC.exists():
        return installed
    for src in _COMMANDS_SRC.glob("harness-*.md"):
        dst = dst_dir / src.name
        shutil.copyfile(src, dst)
        installed.append(dst)
    return installed


def _install_skills(claude_dir: Path) -> list[Path]:
    """复制 harness/skills/* 到项目 .claude/skills/，整目录拷贝
    （每个 skill 是一个子目录含 SKILL.md）。已存在则覆盖（保持最新）。"""
    # harness/skills 在 harness 包根目录下
    skills_src = Path(__file__).resolve().parent.parent.parent / "skills"
    if not skills_src.exists():
        return []
    dst_dir = claude_dir / "skills"
    dst_dir.mkdir(exist_ok=True)
    installed: list[Path] = []
    for skill_dir in skills_src.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("__"):
            continue
        dst_skill = dst_dir / skill_dir.name
        if dst_skill.exists():
            shutil.rmtree(dst_skill)
        shutil.copytree(skill_dir, dst_skill)
        installed.append(dst_skill)
    return installed


def uninstall_hooks(project_root: Path, scope: Literal["shared", "local"] = "shared") -> Path | None:
    """移除 harness 装的 hook（保留非 harness 的）"""
    claude_dir = project_root / ".claude"
    filename = "settings.local.json" if scope == "local" else "settings.json"
    settings_path = claude_dir / filename
    if not settings_path.exists():
        return None

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    hooks = data.get("hooks", {})
    for phase in ("PostToolUse", "Stop"):
        entries = hooks.get(phase, [])
        hooks[phase] = [
            e for e in entries
            if not _already_installed([e], HOOK_MARKER)
            and not _already_installed([e], ACTIVE_TASKS_MARKER)
        ]
        if not hooks[phase]:
            hooks.pop(phase, None)

    if not hooks:
        data.pop("hooks", None)

    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return settings_path


def _already_installed(entries: list, marker: str) -> bool:
    for e in entries:
        cmd_list = []
        if "command" in e:
            cmd_list = [e["command"]]
        elif "hooks" in e:
            cmd_list = [h.get("command", "") for h in e.get("hooks", [])]
        if any(marker in c for c in cmd_list):
            return True
    return False
