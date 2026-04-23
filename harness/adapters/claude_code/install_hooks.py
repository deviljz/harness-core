"""往项目的 .claude/settings.json 注册 harness hook。

PostToolUse(Edit|Write) → harness check --on-edit <file>
Stop → harness check --gate

设计：
- 默认写 .claude/settings.json（入 git 共享）
- 若命令不可用或用户偏好，可用 --local 写 settings.local.json
- 幂等：重复跑不会重复加
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

HOOK_MARKER = "harness-core"  # 识别我们装的 hook


def install_hooks(
    project_root: Path,
    scope: Literal["shared", "local"] = "shared",
) -> Path:
    """注册 hook。返回被写入的 settings 文件路径。"""
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

    # PostToolUse (Edit|Write)
    post = hooks.setdefault("PostToolUse", [])
    if not _already_installed(post, HOOK_MARKER):
        post.append(
            {
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"harness check --on-edit \"$CLAUDE_TOOL_FILE_PATH\" --warn-only  # {HOOK_MARKER}",
                    }
                ],
            }
        )

    # Stop
    stop = hooks.setdefault("Stop", [])
    if not _already_installed(stop, HOOK_MARKER):
        stop.append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"harness check --gate  # {HOOK_MARKER}",
                    }
                ],
            }
        )

    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return settings_path


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
    """查 entries 里有没有 marker"""
    for e in entries:
        cmd_list = []
        if "command" in e:
            cmd_list = [e["command"]]
        elif "hooks" in e:
            cmd_list = [h.get("command", "") for h in e.get("hooks", [])]
        if any(marker in c for c in cmd_list):
            return True
    return False
