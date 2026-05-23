"""harness-visual-audit skill: DOM/视觉断言巡检 UI 工程报告。

实现 docs/visual_audit_assertions.md 的 6 大类断言 MVP:
- A1-1: hover tooltip 不串入无关字段
- A1-2: 非曲线图 mousemove 隐 global tooltip
- A2-1: 颜色调色板限制
- A2-2: 同 chart 多线 hue 差 > 30°
- A3-1: 表格对齐统一
- A4-1: 数值列必须标单位
"""

from .runner import run_audit, AuditConfig, AuditResult
from .assertions import (
    AssertionResult,
    Severity,
    assert_tooltip_no_unrelated,
    assert_non_chart_hides_tooltip,
    assert_color_palette,
    assert_distinct_hues,
    assert_table_alignment,
    assert_units_on_numeric,
)
from .report import build_markdown_report

__all__ = [
    "run_audit",
    "AuditConfig",
    "AuditResult",
    "AssertionResult",
    "Severity",
    "assert_tooltip_no_unrelated",
    "assert_non_chart_hides_tooltip",
    "assert_color_palette",
    "assert_distinct_hues",
    "assert_table_alignment",
    "assert_units_on_numeric",
    "build_markdown_report",
]

__version__ = "0.1.0"
