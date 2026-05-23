"""Gap diff 三态分类: aligned / partial / missing.

v0.2 改进 (基于 Periscope dogfood retro 2026-05-23):
- alias_map: 语义别名匹配（UWA "GPU 渲染分析" → Periscope "渲染"）
- adaptive_threshold: 短词敏感 / 长词宽容
- _normalize 增强：剥 ▸ ▾ ► 等 UI 装饰符
- 默认 fuzzy_threshold 0.75（对齐 v0.1 reviewer 调整）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .scanner import ScanResult, SidebarItem


DEFAULT_FUZZY_THRESHOLD = 0.75


@dataclass
class GapItem:
    baseline_label: str
    target_label: str = ""
    similarity: float = 0.0
    note: str = ""
    via_alias: bool = False  # v0.2: 标记是否通过 alias map 匹配


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


def adaptive_threshold(label_len: int, base: float = DEFAULT_FUZZY_THRESHOLD) -> float:
    """v0.2: 根据 label 长度自适应阈值.

    短词（≤4 字符）阈值高 — 避免短词假阳（如 "FPS" vs "PSS"）
    长词（≥10 字符）阈值低 — 允许缺字（"加载模块性能" vs "加载"）
    """
    if label_len <= 4:
        return min(1.0, base + 0.10)
    if label_len >= 10:
        return max(0.0, base - 0.15)
    return base


def gap_diff(
    baseline: "ScanResult",
    target: "ScanResult",
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    alias_map: Optional[dict[str, list[str]]] = None,
    use_adaptive_threshold: bool = False,
) -> GapResult:
    """三态对比 baseline vs target sidebar.

    Args:
        baseline / target: ScanResult
        fuzzy_threshold: partial 阈值（默认 0.75）
        alias_map: v0.2 别名映射 {baseline_label: [target_alias, ...]}
            优先级最高；命中即 aligned，via_alias=True
        use_adaptive_threshold: v0.2 短词敏感 / 长词宽容（默认关闭保兼容）
    """
    result = GapResult()
    alias_map = alias_map or {}

    target_labels = [it.label for it in target.sidebar]
    target_norm_to_orig: dict[str, str] = {
        _normalize(lbl): lbl for lbl in target_labels
    }
    target_norm_labels = set(target_norm_to_orig.keys())

    for b_item in baseline.sidebar:
        b_norm = _normalize(b_item.label)

        # 1. alias map 优先（v0.2）
        if b_item.label in alias_map:
            aliases = alias_map[b_item.label]
            matched_target = None
            for alias in aliases:
                alias_norm = _normalize(alias)
                if alias_norm in target_norm_to_orig:
                    matched_target = target_norm_to_orig[alias_norm]
                    break
            if matched_target:
                result.aligned.append(
                    GapItem(
                        baseline_label=b_item.label,
                        target_label=matched_target,
                        similarity=1.0,
                        note="alias",
                        via_alias=True,
                    )
                )
                continue

        # 2. 精确匹配
        if b_norm in target_norm_labels:
            result.aligned.append(
                GapItem(
                    baseline_label=b_item.label,
                    target_label=target_norm_to_orig[b_norm],
                    similarity=1.0,
                )
            )
            continue

        # 3. fuzzy 匹配
        best_label = None
        best_sim = 0.0
        for t_norm, t_orig in target_norm_to_orig.items():
            sim = SequenceMatcher(None, b_norm, t_norm).ratio()
            if sim > best_sim:
                best_sim = sim
                best_label = t_orig

        # v0.2: 自适应阈值
        thr = (
            adaptive_threshold(len(b_item.label), fuzzy_threshold)
            if use_adaptive_threshold
            else fuzzy_threshold
        )

        if best_sim >= thr:
            result.partial.append(
                GapItem(
                    baseline_label=b_item.label,
                    target_label=best_label or "",
                    similarity=best_sim,
                    note=f"fuzzy match ({best_sim:.2f}, threshold={thr:.2f})",
                )
            )
        else:
            result.missing.append(
                GapItem(
                    baseline_label=b_item.label,
                    similarity=best_sim,
                    note=(
                        f"best fuzzy: {best_label!r} ({best_sim:.2f}, threshold={thr:.2f})"
                        if best_label
                        else ""
                    ),
                )
            )
    return result


def _normalize(s: str) -> str:
    """归一化标签做比较 (v0.2: 增强 Unicode UI 装饰符移除)."""
    if not s:
        return ""
    s = s.lower()
    # 标点 + UI 装饰符（v0.2 新增 ▸ ▾ ► ▼ ▲ · 等 toggle 字符）
    PUNCT = (
        " ", "-", "_", "/", "(", ")", "[", "]", ".", ",",
        "，", "（", "）", "▸", "▾", "►", "▼", "▲", "·",
    )
    for ch in PUNCT:
        s = s.replace(ch, "")
    # UWA 风格 newN 后缀
    import re
    s = re.sub(r"new\d*$", "", s)
    return s
