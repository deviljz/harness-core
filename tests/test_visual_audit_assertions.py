"""Unit tests for visual_audit assertions (pure logic, no playwright)."""

from __future__ import annotations

from harness.skills.harness_visual_audit.assertions import (
    AssertionResult,
    Severity,
    assert_tooltip_no_unrelated,
    assert_non_chart_hides_tooltip,
    assert_color_palette,
    assert_distinct_hues,
    assert_table_alignment,
    assert_units_on_numeric,
    _hex_to_hue,
    _is_grayscale,
)


# ============ A1-1 tooltip unrelated ============


def test_a1_1_passes_clean_tooltip():
    r = assert_tooltip_no_unrelated(
        chart_id="chartMemGfx",
        tooltip_text="第 100 帧 GfxUsed = 305.8 MB",
        forbidden_keywords=["frameMs", "GPU=", "DC=", "GC="],
    )
    assert r.passed
    assert r.assertion_id == "A1-1"


def test_a1_1_catches_frameMs_leak():
    r = assert_tooltip_no_unrelated(
        chart_id="chartMemGfx",
        tooltip_text="第 100 帧 frameMs = 33.05 GfxUsed = 305.8 MB",
        forbidden_keywords=["frameMs"],
    )
    assert not r.passed
    assert "frameMs" in r.actual
    assert "preset" in r.remediation.lower() or "fmt" in r.remediation.lower()


def test_a1_1_allows_chart_specific_exception():
    """chartFrameMs 显示 frameMs= 是合理的，应通过."""
    r = assert_tooltip_no_unrelated(
        chart_id="chartFrameMs",
        tooltip_text="第 100 帧 frameMs = 33.05 ms",
        forbidden_keywords=["frameMs"],
        allowed_for_chart=["frameMs"],
    )
    assert r.passed


def test_a1_1_word_boundary_no_false_positive():
    """forbidden 'GPU=' 不应误命中 'GPU Frame Time'."""
    r = assert_tooltip_no_unrelated(
        chart_id="chartGpuTime",
        tooltip_text="第 100 帧 GPU Frame Time = 23.12 ms",
        forbidden_keywords=["GPU="],
    )
    # 严格"GPU=" pattern + "GPU Frame Time = 23.12" 中 GPU 后是空格不是 =，不应命中
    assert r.passed


# ============ A1-2 non-chart hides tooltip ============


def test_a1_2_passes_when_tooltip_hidden():
    r = assert_non_chart_hides_tooltip("phaseTimeline", "none")
    assert r.passed


def test_a1_2_catches_residual_tooltip():
    r = assert_non_chart_hides_tooltip("phaseTimeline", "block")
    assert not r.passed
    assert "block" in r.actual
    assert "mousemove" in r.remediation


# ============ A2-1 color palette ============


def test_a2_1_passes_when_all_in_palette():
    used = {"#79c0ff": ["#chartA path"], "#7ee787": ["#chartB path"]}
    palette = ["#79c0ff", "#7ee787", "#ffa657"]
    results = assert_color_palette(used, palette)
    assert all(r.passed for r in results)


def test_a2_1_catches_out_of_palette_color():
    used = {"#abcdef": ["#chartX path"]}
    palette = ["#79c0ff"]
    results = assert_color_palette(used, palette)
    fails = [r for r in results if not r.passed]
    assert len(fails) >= 1
    assert "#abcdef" in fails[0].actual


def test_a2_1_ignores_grayscale_by_default():
    used = {"#222222": ["#bg"], "#888888": ["#text"], "#fff": ["#card"]}
    palette = ["#79c0ff"]
    results = assert_color_palette(used, palette, ignore_grayscale=True)
    assert all(r.passed for r in results)


def test_a2_1_semantic_reserved_violation():
    used = {"#dc2626": ["span.random-decoration"]}
    palette = ["#79c0ff"]
    semantic = {"#dc2626": [".nav-badge", ".kpi-issue-dot.bad"]}
    results = assert_color_palette(used, palette, semantic_reserved=semantic)
    fails = [r for r in results if not r.passed]
    assert len(fails) == 1
    assert "语义保留色" in fails[0].actual


# ============ A2-2 distinct hues ============


def test_a2_2_passes_distinct_colors():
    # 蓝 / 绿 / 橙 hue 差大
    r = assert_distinct_hues("chartA", ["#79c0ff", "#7ee787", "#ffa657"])
    assert r.passed


def test_a2_2_catches_near_hues():
    # 两个蓝色 hue 接近
    r = assert_distinct_hues("chartMemTotal", ["#79c0ff", "#5aaad7", "#7ee787"], min_hue_diff_deg=30)
    assert not r.passed
    assert "Δ" in r.actual


def test_a2_2_passes_single_line():
    r = assert_distinct_hues("chartFrameMs", ["#79c0ff"])
    assert r.passed


def test_hex_to_hue_blue():
    h = _hex_to_hue("#79c0ff")
    # 蓝色 hue 约 195-220
    assert h is not None
    assert 190 <= h <= 230


# ============ A3-1 table alignment ============


def test_a3_1_passes_uniform_left():
    aligns = {"td1": "left", "td2": "left", "td3": "start"}  # start 等价 left
    results = assert_table_alignment(aligns, expected_align="left")
    assert all(r.passed for r in results)


def test_a3_1_catches_mixed_align():
    aligns = {"td1": "left", "td2": "right", "td3": "center"}
    results = assert_table_alignment(aligns, expected_align="left")
    fails = [r for r in results if not r.passed]
    assert len(fails) == 1
    assert "right" in fails[0].actual or "center" in fails[0].actual


# ============ A4-1 units ============


def test_a4_1_passes_with_unit_in_td():
    cells = [{"th_text": "内存", "td_text": "305 MB"}, {"th_text": "时间", "td_text": "33.2 ms"}]
    results = assert_units_on_numeric(cells, ["MB", "ms"])
    assert all(r.passed for r in results)


def test_a4_1_passes_with_unit_in_th():
    cells = [{"th_text": "内存 (MB)", "td_text": "305"}]
    results = assert_units_on_numeric(cells, ["MB"])
    assert all(r.passed for r in results)


def test_a4_1_catches_missing_unit():
    """UWA 实际 bug: '贴图 735' 是 Count 但没标单位，被误读为 MB."""
    cells = [
        {"th_text": "贴图", "td_text": "735"},
        {"th_text": "网格", "td_text": "200"},
    ]
    results = assert_units_on_numeric(cells, ["MB", "ms", "个"])
    fails = [r for r in results if not r.passed]
    assert len(fails) == 1


def test_a4_1_skips_non_numeric():
    cells = [{"th_text": "类型", "td_text": "Texture"}]
    results = assert_units_on_numeric(cells, ["MB"])
    assert all(r.passed for r in results)
