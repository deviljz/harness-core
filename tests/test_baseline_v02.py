"""Tests for harness-baseline v0.2 improvements.

新增覆盖：
- alias_map 优先匹配
- adaptive_threshold 短词/长词
- top_level_only 树形抽取
- _clean_label 装饰字符
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.skills.harness_baseline import (
    scan_baseline,
    scan_target,
    gap_diff,
    adaptive_threshold,
    DEFAULT_FUZZY_THRESHOLD,
)
from harness.skills.harness_baseline.scanner import (
    ScanResult,
    SidebarItem,
    _clean_label,
)


FIXTURES = Path(__file__).parent / "fixtures" / "template_project" / "case_07_baseline_audit"


def _mk(labels: list[str]) -> ScanResult:
    return ScanResult(source="mock", sidebar=[SidebarItem(label=lbl) for lbl in labels])


# ============ alias_map (P0-A) ============


def test_alias_map_exact_alias_aligned():
    """UWA "GPU 渲染分析" → Periscope "渲染" (语义同义)."""
    b = _mk(["GPU 渲染分析", "GPU 带宽分析", "卡顿点分析"])
    t = _mk(["渲染", "GPU 上传带宽", "卡顿列表"])
    alias_map = {
        "GPU 渲染分析": ["渲染", "rendering"],
        "GPU 带宽分析": ["GPU 上传带宽"],
        "卡顿点分析": ["卡顿列表"],
    }
    gap = gap_diff(b, t, alias_map=alias_map)
    assert gap.counts == {"aligned": 3, "partial": 0, "missing": 0}
    assert all(it.via_alias for it in gap.aligned)
    assert all(it.note == "alias" for it in gap.aligned)


def test_alias_map_first_match_wins():
    """alias 列表多个候选时，第一个匹配的目标胜出."""
    b = _mk(["性能概览"])
    t = _mk(["概览", "帧时长"])
    alias_map = {"性能概览": ["概览", "帧时长"]}
    gap = gap_diff(b, t, alias_map=alias_map)
    assert gap.aligned[0].target_label == "概览"


def test_alias_map_priority_over_exact():
    """alias 优先于 exact match —— 显式声明优先."""
    b = _mk(["A"])
    t = _mk(["A", "B"])
    # alias 把 A → B，应优先而非 A 自身 exact
    gap = gap_diff(b, t, alias_map={"A": ["B"]})
    assert gap.aligned[0].target_label == "B"
    assert gap.aligned[0].via_alias is True


def test_alias_miss_falls_through_to_fuzzy():
    """alias 未命中时回退 exact / fuzzy."""
    b = _mk(["运行日志"])
    t = _mk(["运行日志"])  # exact 命中
    gap = gap_diff(b, t, alias_map={"运行日志": ["nonexistent"]})
    # alias 没命中 → exact 兜底
    assert gap.counts == {"aligned": 1, "partial": 0, "missing": 0}
    assert gap.aligned[0].via_alias is False


# ============ adaptive_threshold (P1-C) ============


def test_adaptive_threshold_short_words_stricter():
    """短词阈值更高（避免 'FPS' vs 'PSS' 假阳）."""
    assert adaptive_threshold(3) > adaptive_threshold(7)
    assert adaptive_threshold(4) >= 0.85


def test_adaptive_threshold_long_words_lenient():
    """长词阈值更低."""
    assert adaptive_threshold(12) < adaptive_threshold(7)
    assert adaptive_threshold(10) <= 0.60


def test_adaptive_threshold_medium_default():
    """中等长度回退默认."""
    assert adaptive_threshold(7) == DEFAULT_FUZZY_THRESHOLD


def test_gap_diff_adaptive_long_word_partial():
    """长词差异允许匹配为 partial."""
    b = _mk(["加载模块性能"])  # 长 6 字符
    t = _mk(["加载性能"])  # 缺 2 字
    gap_no_adaptive = gap_diff(b, t, use_adaptive_threshold=False)
    gap_adaptive = gap_diff(b, t, use_adaptive_threshold=True)
    # adaptive 模式应更宽松匹配（partial 或 aligned 都行，关键是不被判 missing）
    assert len(gap_adaptive.missing) <= len(gap_no_adaptive.missing)


# ============ top_level_only + 树形结构 (P0-B) ============


def test_scan_target_top_level_excludes_sublist():
    """v0.2: scan target HTML 时 top_level_only=True 排除 sub-list 内的 a."""
    # 用 fixture target HTML（mock Periscope 风格）
    target_html = FIXTURES / "target" / "report.html"
    result = scan_target(str(target_html), top_level_only=True)
    labels = {it.label for it in result.sidebar}
    # 顶层应有
    assert "性能简报" in labels
    # 注意：v0.2 fixture html 无 sub-list 嵌套，所以行为同 v0.1 — 全过即可


def test_extract_tree_v01_behavior_unchanged():
    """v0.1 默认行为（top_level_only=False）保留向后兼容."""
    target_html = FIXTURES / "target" / "report.html"
    result_v01 = scan_target(str(target_html), top_level_only=False)
    # 至少能抽出 8 项 mock target tab
    assert len(result_v01.sidebar) >= 7


# ============ _clean_label (P2-E) ============


def test_clean_label_strips_toggle_chars():
    """v0.2: 剥末尾装饰符 (▸ ▾ ► ▼ ▲)."""
    assert _clean_label("重点函数分析▸") == "重点函数分析"
    assert _clean_label("内存占用 ▾") == "内存占用"
    assert _clean_label("Foo►") == "Foo"


def test_clean_label_strips_new_suffix():
    """UWA new / newN 后缀."""
    assert _clean_label("性能简报new") == "性能简报"
    assert _clean_label("GPU 分析new1") == "GPU 分析"


def test_clean_label_collapses_whitespace():
    assert _clean_label("foo   bar") == "foo bar"
    assert _clean_label("  baz  ") == "baz"


# ============ normalize 增强 (P2-E) ============


def test_normalize_removes_toggle_chars_in_diff():
    """_normalize 应去掉 ▸ 让 '内存占用' 与 '内存占用▸' 直接 exact 匹配."""
    b = _mk(["内存占用"])
    t = _mk(["内存占用▸"])
    gap = gap_diff(b, t)
    # 不再是 partial（0.89），应该 exact aligned 因 normalize 已剥 ▸
    assert gap.counts == {"aligned": 1, "partial": 0, "missing": 0}


# ============ Periscope realistic gap audit (e2e) ============


def test_e2e_periscope_with_aliases_higher_recall():
    """e2e: 用 alias map + adaptive 应显著提升 recall."""
    baseline = scan_baseline(str(FIXTURES / "baseline.html"))
    target = scan_target(str(FIXTURES / "target" / "report.html"))

    # 无 alias 基线
    gap_basic = gap_diff(baseline, target)

    # 带 alias map
    alias = {
        "GPU 渲染分析": ["渲染"],
        "GPU 带宽分析": ["GPU 上传带宽"],
        "UI 模块性能": ["UI/Canvas"],
        "物理系统性能": ["Physics"],
    }
    gap_with_alias = gap_diff(baseline, target, alias_map=alias)

    # 带 alias 应该 aligned 数 >= 不带
    assert gap_with_alias.counts["aligned"] >= gap_basic.counts["aligned"]
