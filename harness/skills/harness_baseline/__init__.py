"""harness-baseline skill: 对标场景覆盖度审计."""

from .scanner import scan_baseline, scan_target
from .diff import gap_diff
from .writer import write_spec_gap_section, build_gap_markdown

__all__ = [
    "scan_baseline",
    "scan_target",
    "gap_diff",
    "write_spec_gap_section",
    "build_gap_markdown",
]

__version__ = "0.1.0"
