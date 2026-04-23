"""执行计划：根据 spec.complexity 决定"simple 主 Claude" vs "complex 起 subagent"

v1 不做自动判定，严格读 spec 里的 complexity 字段。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..plan.validator import extract_complexity


@dataclass
class SubTask:
    """一个 subagent 该做的事"""
    name: str
    spec_section: str  # spec 里对应的章节内容
    context_hints: list[str] = field(default_factory=list)  # 涉及的文件/模块


@dataclass
class ExecutionPlan:
    complexity: str  # "simple" | "complex"
    strategy: str    # "main_claude" | "subagents"
    subtasks: list[SubTask] = field(default_factory=list)
    notes: str = ""


def plan_execution(spec_path: Path) -> ExecutionPlan:
    """读 spec，生成执行计划。

    simple → 主 Claude 一条线做完
    complex → 从 spec 的 Structure / 执行计划 节抽多个 subtask
    """
    if not spec_path.exists():
        raise FileNotFoundError(f"spec not found: {spec_path}")

    complexity = extract_complexity(spec_path) or "simple"
    content = spec_path.read_text(encoding="utf-8")

    if complexity == "simple":
        return ExecutionPlan(
            complexity="simple",
            strategy="main_claude",
            notes="complexity=simple → 主 Claude 直接执行整份 spec",
        )

    # complex：试图从 spec 抽子任务
    subtasks = _extract_subtasks(content)
    return ExecutionPlan(
        complexity="complex",
        strategy="subagents",
        subtasks=subtasks,
        notes=f"complexity=complex → 拆 {len(subtasks)} 个 subagent",
    )


def _extract_subtasks(content: str) -> list[SubTask]:
    """从 spec 抽子任务。

    v1 启发式：
    - 找"执行计划"表格里的行（| 阶段 | 交付物 | 估时 |）
    - 或 Structure 段里的每一级模块
    - 兜底：返回单个通用 subtask
    """
    subtasks: list[SubTask] = []

    # 尝试解析"执行计划"表格——按行处理最稳
    exec_section = _extract_section(content, ["执行计划", "Execution Plan"])
    if exec_section:
        header_keywords = {"阶段", "交付物", "估时", "stage", "phase", "delivery"}
        for raw_line in exec_section.splitlines():
            line = raw_line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            # 分隔行 |---|---|---|
            if all(set(c.replace("-", "").replace(":", "")) <= {" ", ""} for c in cells):
                continue
            # 表头
            if cells and cells[0].lower() in header_keywords:
                continue
            if len(cells) < 2:
                continue
            phase = cells[0]
            delivery = cells[1]
            if not phase or not delivery:
                continue
            subtasks.append(
                SubTask(
                    name=phase,
                    spec_section=f"{phase}: {delivery}",
                )
            )

    if subtasks:
        return subtasks

    # 没抽到表格，退回"整份 spec 当一个 subagent"
    return [
        SubTask(
            name="full_implementation",
            spec_section=content,
            context_hints=[],
        )
    ]


def _extract_section(content: str, section_titles: list[str]) -> str:
    """找第一个标题匹配的 ## 段，返回到下个 ## 之前的内容"""
    for title in section_titles:
        pattern = rf"^##\s+(?:\d+\.\s+)?{re.escape(title)}.*?$(.*?)(?=^##\s|\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if m:
            return m.group(1)
    return ""
