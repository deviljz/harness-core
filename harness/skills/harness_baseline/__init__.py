"""harness-baseline skill: 对标场景覆盖度审计.

v0.2: alias_map / sidebar 树形结构 / 自适应阈值 / 装饰符 normalize
"""

from .scanner import scan_baseline, scan_target, SidebarItem, ScanResult
from .diff import (
    gap_diff,
    GapItem,
    GapResult,
    DEFAULT_FUZZY_THRESHOLD,
    adaptive_threshold,
)
from .writer import write_spec_gap_section, build_gap_markdown

__all__ = [
    "scan_baseline",
    "scan_target",
    "SidebarItem",
    "ScanResult",
    "gap_diff",
    "GapItem",
    "GapResult",
    "DEFAULT_FUZZY_THRESHOLD",
    "adaptive_threshold",
    "write_spec_gap_section",
    "build_gap_markdown",
]

__version__ = "0.2.0"
