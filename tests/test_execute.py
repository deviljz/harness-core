"""执行层测试：读 complexity + 抽子任务"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from harness.execute import plan_execution


def _write_spec(tmp_path: Path, body: str, name: str = "spec.md") -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return p


class TestPlanExecution:
    def test_simple_uses_main_claude(self, tmp_path):
        p = _write_spec(
            tmp_path,
            """
            # Feature X
            **complexity**: simple
            ## 1. Objective
            ...
            """,
        )
        plan = plan_execution(p)
        assert plan.complexity == "simple"
        assert plan.strategy == "main_claude"
        assert plan.subtasks == []

    def test_complex_extracts_from_table(self, tmp_path):
        p = _write_spec(
            tmp_path,
            """
            # Feature Y
            **complexity**: complex
            ## 执行计划
            | 阶段 | 交付物 | 估时 |
            |---|---|---|
            | 0. 核心基建 | CLI 骨架 + config | 0.5d |
            | 1. 语言模块 | Python + Dart | 2d |
            | 2. 验证层 | hooks + gate | 1d |
            """,
        )
        plan = plan_execution(p)
        assert plan.complexity == "complex"
        assert plan.strategy == "subagents"
        # 3 个阶段
        names = [st.name for st in plan.subtasks]
        assert any("核心基建" in n for n in names)
        assert any("语言模块" in n for n in names)
        assert any("验证层" in n for n in names)

    def test_complex_no_table_falls_back(self, tmp_path):
        p = _write_spec(
            tmp_path,
            """
            # Feature Z
            **complexity**: complex
            ## 1. Objective
            just do it
            """,
        )
        plan = plan_execution(p)
        assert plan.complexity == "complex"
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].name == "full_implementation"

    def test_missing_complexity_defaults_simple(self, tmp_path):
        p = _write_spec(
            tmp_path,
            """
            # No complexity field
            ## 1. Objective
            x
            """,
        )
        plan = plan_execution(p)
        assert plan.complexity == "simple"

    def test_nonexistent_spec(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            plan_execution(tmp_path / "nope.md")
