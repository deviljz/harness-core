"""Codex 项目初始化实现：生成薄 AGENTS.md、轻量 config.yaml、4 栏换班卡，绝不塞 .claude/ hook。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .handoff import ensure_handoff
from .scanner import inspect_project
from .templates import (
    HARNESS_GITIGNORE,
    render_codex_config_yaml,
    render_thin_agents_md,
)


def init_codex_project(
    root: Path,
    *,
    force_agents: bool = False,
    reset_config: bool = False,
    create_handoff: bool = True,
) -> dict[str, Any]:
    """初始化单个项目为 Codex 轻量模式。

    不变量：
    - 默认不覆盖已有 `.harness/config.yaml`（除非 reset_config=True）
    - 默认不覆盖已有 `AGENTS.md`（除非 force_agents=True）
    - 绝不安装 Claude Code `.claude/` hook
    """
    root = root.resolve()
    scan = inspect_project(root)

    created: list[str] = []
    preserved: list[str] = []
    warnings: list[str] = []

    harness_dir = root / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    # 1. .harness/.gitignore
    gi_path = harness_dir / ".gitignore"
    if not gi_path.exists():
        gi_path.write_text(HARNESS_GITIGNORE, encoding="utf-8")
        created.append(".harness/.gitignore")
    else:
        preserved.append(".harness/.gitignore")

    # 2. .harness/config.yaml
    cfg_path = harness_dir / "config.yaml"
    if cfg_path.exists() and not reset_config:
        preserved.append(".harness/config.yaml")
    else:
        cfg_path.write_text(render_codex_config_yaml(scan), encoding="utf-8")
        created.append(".harness/config.yaml")

    # 3. 薄 AGENTS.md（存在且未 force 时绝不覆盖）
    agents_path = root / "AGENTS.md"
    if agents_path.exists() and not force_agents:
        preserved.append("AGENTS.md")
        line_count = len(agents_path.read_text(encoding="utf-8", errors="replace").splitlines())
        if line_count > 60:
            warnings.append(
                f"已有 AGENTS.md 共 {line_count} 行（建议保持 ≤40 行入口地图，超长内容拆到专项文档或 Skill）"
            )
    else:
        agents_path.write_text(render_thin_agents_md(scan), encoding="utf-8")
        created.append("AGENTS.md")

    # 4. 本地 4 栏换班卡（位于 .harness/handoff.md，被 .harness/.gitignore 忽略）
    if create_handoff:
        _, was_created = ensure_handoff(root, use_global=False, reset=False)
        if was_created:
            created.append(".harness/handoff.md")
        else:
            preserved.append(".harness/handoff.md")

    # 更新 scan 中的最新状态
    scan["existing_agents_md"] = {
        "exists": agents_path.is_file(),
        "path": "AGENTS.md",
        "line_count": len(agents_path.read_text(encoding="utf-8", errors="replace").splitlines()),
    }
    scan["existing_config"] = {
        "exists": cfg_path.is_file(),
        "path": ".harness/config.yaml",
    }

    return {
        "scan": scan,
        "created": created,
        "preserved": preserved,
        "warnings": warnings,
        "next_steps": [
            "补齐或精简 AGENTS.md（≤40 行，仅保留本项目构建/验证命令、主文档指针、3～5 条红线）",
            "按需在 .harness/config.yaml 的 anti_patterns 下加 1～2 条项目专属客观红线",
            "运行 `python -m harness doctor` 与 `python -m harness check --warn-only` 自检",
        ],
    }
