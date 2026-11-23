"""Codex 轻量项目模板：薄 AGENTS.md、轻量 config.yaml、4 栏换班状态文件。"""
from __future__ import annotations

from typing import Any

HARNESS_GITIGNORE = """# harness-core 运行时产物（不提交到 git）
check_cache.json
circuit_state.json
review_data*.json
review_prompt.md
handoff.md
reports/
"""


def render_thin_agents_md(scan: dict[str, Any]) -> str:
    """生成 ≤35 行的入口地图式薄 AGENTS.md（不重复抄写全局规则）。"""
    project = scan.get("project", "project")
    unity_roots: list[str] = scan.get("unity_roots") or []
    docs: list[str] = [d for d in (scan.get("docs") or []) if d != "AGENTS.md"]
    scripts: dict[str, list[str]] = scan.get("scripts") or {}
    verify_scripts = scripts.get("verify") or []
    build_scripts = scripts.get("build") or []
    export_scripts = scripts.get("export") or []

    lines: list[str] = [
        f"# {project} 项目入口地图",
        "",
        "> 本文件只放本项目专属入口与红线（保持 ≤40 行）；全局通用纪律见 `~/.codex/AGENTS.md`。",
        "",
        "## 常用验证与构建命令",
    ]

    if verify_scripts:
        for s in verify_scripts[:3]:
            cmd = f"powershell -ExecutionPolicy Bypass -File ./{s}" if s.endswith(".ps1") else f"./{s}"
            lines.append(f"- 验证：`{cmd}`")
    if build_scripts:
        for s in build_scripts[:3]:
            cmd = f"powershell -ExecutionPolicy Bypass -File ./{s}" if s.endswith(".ps1") else f"./{s}"
            lines.append(f"- 构建：`{cmd}`")
    if export_scripts:
        for s in export_scripts[:2]:
            lines.append(f"- 导出：`./{s}`")
    if not (verify_scripts or build_scripts or export_scripts):
        lines.append("- 验证：`<补充本项目实测/验证命令>`")
        lines.append("- 构建：`<补充本项目构建命令>`")

    lines.extend(["", "## 主文档与关键目录"])
    if unity_roots:
        lines.append(f"- Unity 工程：`{', '.join(unity_roots)}`")
    if docs:
        for d in docs[:4]:
            lines.append(f"- `{d}`")
    else:
        lines.append("- `README.md`（如有）")

    lines.extend(
        [
            "",
            "## 本项目硬红线（只留 3～5 条最痛的）",
            "- `<红线 1：例如固定构建/输出路径，不新建平行副本>`",
            "- `<红线 2：例如特定资源/配置必须走指定脚本导出>`",
            "- `<红线 3：例如查因默认只读，改动前先核对原流程>`",
            "",
            "## 轻量检查与换班",
            "- 静态红线扫描：`python -m harness check --warn-only`",
            "- 换话题/结项落盘：`python -m harness handoff`（1 页 4 栏状态文件，不入 git）",
            "",
        ]
    )
    return "\n".join(lines)


def render_codex_config_yaml(scan: dict[str, Any]) -> str:
    """生成轻量 Codex 项目 .harness/config.yaml（无重型 hook、无慢速全量目标）。"""
    project = scan.get("project", "project")
    is_unity = "unity" in (scan.get("types") or [])

    extra_ignores = ""
    if is_unity:
        extra_ignores = (
            '  - "**/Library/**"\n'
            '  - "**/Temp/**"\n'
            '  - "**/Obj/**"\n'
            '  - "**/Work_Local/**"\n'
            '  - "**/.ui_pipeline/**"\n'
            '  - "**/*.meta"\n'
            '  - "**/*.prefab"\n'
            '  - "**/*.unity"\n'
        )

    return f"""# harness-core Codex 轻量配置（公共包不放单项目业务细节，项目红线留在这里）
project: {project}
agent: codex

llm:
  provider: manual

ignore_paths_global:
  - .git/**
  - "**/__pycache__/**"
  - "**/node_modules/**"
  - "**/*.log"
  - reports/**
  - .harness/**
{extra_ignores}
# Unity / 大型工程默认不挂重型编译 target，避免误触发全量卡死；
# 轻量检查优先通过 anti_patterns 或项目自有 verify 脚本执行。
targets: []

# 项目专属静态红线（毫秒级正则扫描，支持 include / exclude 精准限定目录）。
# 支持语言：csharp / lua / cpp / python / javascript / typescript / powershell / dart / all
anti_patterns: {{}}
  # csharp:
  #   - name: empty_catch
  #     pattern: '^\\s*catch\\s*(\\([^)]*\\))?\\s*\\{{\\s*\\}}\\s*$'
  #     msg: "禁止空 catch 块吞异常"
  #     severity: warn
  #     include: ["game/client/Assets/**/*.cs"]
  #     exclude: ["**/Editor/**", "**/Tests/**"]
"""


def render_handoff_template(project: str) -> str:
    """1 页 4 栏换班状态文件模板（换大话题 / 结项 / 明显变傻时刷新后开干净新对话）。"""
    return f"""# {project} 换班状态卡

> 保持 ≤1 页。只在换大话题、阶段结项或上下文明显变重鬼打墙时刷新并开新对话；同题密集讨论不强切。

## 1. 已验证事实
- （写精确的 `文件:行号`、命令与实测结果，不把猜测当事实）

## 2. 试过确认不行的路
- （写清条件 + 失败现象，避免下轮重复踩坑）

## 3. 未决项
- （写“在条件 X 下观察到 Y；尚未测试 Z；需确认 W”）

## 4. 下一步最小动作
- （具体到下一轮第一件可立刻执行的事）
"""
