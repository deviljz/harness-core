"""Gap diff 三态分类: aligned / partial / missing."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scanner import ScanResult, SidebarItem


@dataclass
class GapItem:
    baseline_label: str
    target_label: str = ""
    similarity: float = 0.0
    note: str = ""


@dataclass
class GapResult:
    aligned: list[GapItem] = field(default_factory=list)
    partial: list[GapItem] = field(default_factory=list)
    missing: list[GapItem] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "aligned": len(self.aligned),
            "partial": len(self.partial),
            "missing": len(self.missing),
        }


def gap_diff(
    baseline: "ScanResult",
    target: "ScanResult",
    fuzzy_threshold: float = 0.75,
) -> GapResult:
    """三态对比 baseline vs target sidebar."""
    result = GapResult()
    target_labels = [it.label for it in target.sidebar]
    target_norm_to_orig: dict[str, str] = {_normalize(lbl): lbl for lbl in target_labels}

    for b_item in baseline.sidebar:
        b_norm = _normalize(b_item.label)
        # 1. 精确匹配
        if b_norm in target_norm_to_orig:
            result.aligned.append(
                GapItem(
                    baseline_label=b_item.label,
                    target_label=target_norm_to_orig[b_norm],
                    similarity=1.0,
                )
            )
            continue
        # 2. fuzzy 匹配
        best_label = None
        best_sim = 0.0
        for t_norm, t_orig in target_norm_to_orig.items():
            sim = SequenceMatcher(None, b_norm, t_norm).ratio()
            if sim > best_sim:
                best_sim = sim
                best_label = t_orig
        if best_sim >= fuzzy_threshold:
            result.partial.append(
                GapItem(
                    baseline_label=b_item.label,
                    target_label=best_label or "",
                    similarity=best_sim,
                    note=f"fuzzy match ({best_sim:.2f})",
                )
            )
        else:
            result.missing.append(
                GapItem(
                    baseline_label=b_item.label,
                    similarity=best_sim,
                    note=f"best fuzzy: {best_label!r} ({best_sim:.2f})" if best_label else "",
                )
            )
    return result


def _normalize(s: str) -> str:
    """归一化标签做比较."""
    if not s:
        return ""
    s = s.lower()
    # 去常见噪音字符
    for ch in (" ", "-", "_", "/", "(", ")", "[", "]", ".", ",", "，", "（", "）"):
        s = s.replace(ch, "")
    # UWA 风格 "new" 后缀（new1 / new2）
    import re

    s = re.sub(r"new\d*$", "", s)
    return s
