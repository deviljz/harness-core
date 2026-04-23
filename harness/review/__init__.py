"""审查层：对照 spec 判代码改动一致性"""
from __future__ import annotations

from .diff_packager import package_diff
from .runner import ReviewResult, run_review

__all__ = ["ReviewResult", "run_review", "package_diff"]
