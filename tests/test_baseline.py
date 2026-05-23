"""Tests for harness-baseline skill."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.skills.harness_baseline import (
    scan_baseline,
    scan_target,
    gap_diff,
    write_spec_gap_section,
    build_gap_markdown,
)
from harness.skills.harness_baseline.diff import GapResult, GapItem
from harness.skills.harness_baseline.scanner import ScanResult, SidebarItem


FIXTURES = Path(__file__).parent / "fixtures" / "template_project" / "case_07_baseline_audit"


# ============ Scanner tests ============


def test_scan_local_html_extracts_sidebar():
    result = scan_baseline(str(FIXTURES / "baseline.html"))
    assert isinstance(result, ScanResult)
    labels = [it.label for it in result.sidebar]
    # baseline.html mock UWA-like 有 5 子页
    assert "性能简报" in labels
    assert "GPU 渲染分析" in labels
    assert "GPU 带宽分析" in labels
    assert "Lua 内存" in labels
    assert "自定义面板" in labels


def test_scan_target_uses_data_tab_fallback():
    result = scan_target(str(FIXTURES / "target" / "report.html"))
    labels = [it.label for it in result.sidebar]
    # target/report.html Periscope 风格 a[data-tab=...]，只 3 个 tab
    assert "性能简报" in labels
    assert "GPU 渲染分析" in labels
    # target 没有 Lua 内存 / 自定义面板
    assert "Lua 内存" not in labels


def test_scan_nonexistent_raises():
    with pytest.raises(FileNotFoundError):
        scan_baseline("/nonexistent/path.html")


# ============ Diff tests ============


def _mk_result(labels: list[str]) -> ScanResult:
    return ScanResult(
        source="mock",
        sidebar=[SidebarItem(label=lbl) for lbl in labels],
    )


def test_gap_diff_exact_match():
    b = _mk_result(["A", "B", "C"])
    t = _mk_result(["A", "B", "C"])
    gap = gap_diff(b, t)
    assert gap.counts == {"aligned": 3, "partial": 0, "missing": 0}


def test_gap_diff_missing():
    b = _mk_result(["A", "B", "C"])
    t = _mk_result(["A", "B"])
    gap = gap_diff(b, t)
    assert gap.counts == {"aligned": 2, "partial": 0, "missing": 1}
    assert gap.missing[0].baseline_label == "C"


def test_gap_diff_fuzzy_partial():
    # v0.1 reviewer 调整：用默认 0.75 阈值，避免不同类别共享前缀误判 partial
    b = _mk_result(["GPU 渲染分析", "GPU 带宽分析"])
    t = _mk_result(["GPU 渲染分析x"])  # 仅小差异 (后缀 x)，应 partial
    gap = gap_diff(b, t)  # 默认 0.75
    assert gap.counts["partial"] >= 1
    # GPU 带宽分析 与 GPU 渲染分析x 字符差异大，应判 missing
    assert any(m.baseline_label == "GPU 带宽分析" for m in gap.missing)


def test_gap_diff_normalize_handles_spaces_and_punct():
    b = _mk_result(["性能 简报", "GPU 渲染分析"])
    t = _mk_result(["性能简报", "GPU渲染分析"])
    gap = gap_diff(b, t)
    assert gap.counts == {"aligned": 2, "partial": 0, "missing": 0}


# ============ Writer tests ============


def test_build_gap_markdown_contains_section_header():
    gap = GapResult(
        aligned=[GapItem(baseline_label="A", target_label="A", similarity=1.0)],
        partial=[],
        missing=[GapItem(baseline_label="B")],
    )
    md = build_gap_markdown(gap, "https://example.com/report")
    assert "## 覆盖度差距" in md
    assert "https://example.com/report" in md
    assert "<!-- harness-baseline-begin -->" in md
    assert "<!-- harness-baseline-end -->" in md
    assert "✓ 1 / 🟡 0 / ❌ 1" in md
    assert "| ✓ | A | A |" in md
    assert "| ❌ | B | — |" in md


def test_write_spec_gap_section_inserts_before_boundaries(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(
        "# Spec\n\n## Objective\n\nFoo\n\n## Boundaries\n\nBar\n",
        encoding="utf-8",
    )
    gap = GapResult(
        aligned=[GapItem(baseline_label="A", target_label="A")],
        missing=[GapItem(baseline_label="B")],
    )
    write_spec_gap_section(spec, gap, "src")
    content = spec.read_text(encoding="utf-8")
    # 覆盖度差距 section 出现在 Boundaries 之前
    idx_gap = content.find("## 覆盖度差距")
    idx_b = content.find("## Boundaries")
    assert 0 <= idx_gap < idx_b


def test_write_spec_gap_section_idempotent(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\n## Boundaries\n\nBar\n", encoding="utf-8")
    gap1 = GapResult(missing=[GapItem(baseline_label="B1")])
    write_spec_gap_section(spec, gap1, "src1")
    content1 = spec.read_text(encoding="utf-8")
    assert "B1" in content1

    # 再写一次（不同 gap）应该替换不重复追加
    gap2 = GapResult(missing=[GapItem(baseline_label="B2")])
    write_spec_gap_section(spec, gap2, "src2")
    content2 = spec.read_text(encoding="utf-8")
    assert "B2" in content2
    assert "B1" not in content2
    # marker 只有一对
    assert content2.count("<!-- harness-baseline-begin -->") == 1
    assert content2.count("<!-- harness-baseline-end -->") == 1


# ============ End-to-end fixture test ============


def test_e2e_fixture_periscope_vs_uwa():
    """完整流程：baseline (mock UWA) vs target (mock Periscope) 产出预期 gap 表."""
    baseline = scan_baseline(str(FIXTURES / "baseline.html"))
    target = scan_target(str(FIXTURES / "target" / "report.html"))
    gap = gap_diff(baseline, target)

    aligned_labels = {it.baseline_label for it in gap.aligned}
    missing_labels = {it.baseline_label for it in gap.missing}

    # 期望对齐项
    assert "性能简报" in aligned_labels
    assert "GPU 渲染分析" in aligned_labels
    # 期望缺失项
    assert "Lua 内存" in missing_labels
    assert "自定义面板" in missing_labels
    assert "GPU 带宽分析" in missing_labels
