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
_COMMANDS_SRC = Path(__file__).parent / "commands"


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
) -> Path:
    """注册 hook。返回被写入的 settings 文件路径。"""
    # 1) 写 run_hook.py
    harness_dir = project_root / ".harness"
    harness_dir.mkdir(exist_ok=True)
    wrapper = harness_dir / "run_hook.py"
    wrapper.write_text(RUN_HOOK_SCRIPT, encoding="utf-8")

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

    # 用 python 调 wrapper，跨平台
    on_edit_cmd = f'python .harness/run_hook.py check --on-edit "$CLAUDE_TOOL_FILE_PATH" --warn-only  # {HOOK_MARKER}'
    gate_cmd = f'python .harness/run_hook.py check --gate  # {HOOK_MARKER}'

    post = hooks.setdefault("PostToolUse", [])
    if not _already_installed(post, HOOK_MARKER):
        post.append(
            {
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [{"type": "command", "command": on_edit_cmd}],
            }
        )

    stop = hooks.setdefault("Stop", [])
    if not _already_installed(stop, HOOK_MARKER):
        stop.append({"hooks": [{"type": "command", "command": gate_cmd}]})

    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 3) 安装 slash commands 到 .claude/commands/
    _install_commands(claude_dir)

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
        hooks[phase] = [e for e in entries if not _already_installed([e], HOOK_MARKER)]
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
