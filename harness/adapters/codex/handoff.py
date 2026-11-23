"""极简 4 栏换班状态文件管理（不污染共享项目 git 历史）。"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .sync import resolve_codex_home
from .templates import render_handoff_template


def project_key(root: Path) -> str:
    """生成稳定短标识 `<slug>-<8位hash>`，与 long-task-handoff 习惯一致。"""
    resolved = root.resolve()
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", resolved.name).strip("-").lower() or "project"
    digest = hashlib.sha256(resolved.as_posix().lower().encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def handoff_path(
    root: Path,
    *,
    use_global: bool = False,
    codex_home: Path | None = None,
) -> Path:
    resolved = root.resolve()
    if use_global:
        home = resolve_codex_home(codex_home)
        return home / "handoffs" / project_key(resolved) / "current.md"
    return resolved / ".harness" / "handoff.md"


def ensure_handoff(
    root: Path,
    *,
    use_global: bool = False,
    reset: bool = False,
    codex_home: Path | None = None,
) -> tuple[Path, bool]:
    """确保 4 栏换班状态文件存在，返回 `(路径, 是否本次新建/重置)`。"""
    path = handoff_path(root, use_global=use_global, codex_home=codex_home)
    if path.is_file() and not reset:
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_handoff_template(root.resolve().name), encoding="utf-8")
    return path, True
