"""通用「数据不变量」断言（harness visual-audit 机制层）.

这是 harness-core 提供的**通用机制**：从报告里按 selector 取数值、聚合、和参照值（常量或另一 selector）比较。
具体业务不变量（如 Periscope 的 marker≤时长、FPS≤cap）由**项目 config** 提供，不进 harness-core。
"""

from harness.skills.harness_visual_audit.assertions import (
    assert_data_invariant,
    Severity,
)


def S(texts, count=None):
    """构造一个 selector 采样：{texts, count}。"""
    return {"texts": list(texts), "count": count if count is not None else len(texts)}


# ── op <= 参照×factor（另一 selector 取值）：marker 各线程 total ≤ 时长×1.1 ──

def test_le_ref_factor_pass():
    samples = {".thread .total": S(["100", "200", "300"]), "#duration": S(["600"])}
    spec = {
        "id": "marker_total_le_duration",
        "value": {"selector": ".thread .total", "aggregate": "sum"},
        "op": "<=",
        "ref": {"selector": "#duration"},
        "factor": 1.1,
    }
    r = assert_data_invariant(spec, samples)
    assert r.passed  # sum=600 <= 600*1.1=660


def test_le_ref_factor_fail():
    samples = {".thread .total": S(["100", "200", "500"]), "#duration": S(["600"])}
    spec = {
        "id": "marker_total_le_duration",
        "value": {"selector": ".thread .total", "aggregate": "sum"},
        "op": "<=",
        "ref": {"selector": "#duration"},
        "factor": 1.1,
    }
    r = assert_data_invariant(spec, samples)
    assert not r.passed  # sum=800 > 660
    assert "800" in r.actual


# ── op <= 常量：所有"占峰值%" ≤ 100 ──

def test_le_const_percent_fail():
    samples = {".pct": S(["95%", "100%", "120%"])}
    spec = {"id": "pct_le_100", "value": {"selector": ".pct", "aggregate": "max"}, "op": "<=", "ref": {"const": 100}}
    assert not assert_data_invariant(spec, samples).passed  # max=120 > 100


# ── op <= 参照×factor + max 聚合：FPS max ≤ targetFrameRate×1.5 ──

def test_max_le_ref_factor_fail():
    samples = {".fps": S(["55", "57", "30"]), "#target": S(["30"])}
    spec = {"id": "fps", "value": {"selector": ".fps", "aggregate": "max"}, "op": "<=", "ref": {"selector": "#target"}, "factor": 1.5}
    assert not assert_data_invariant(spec, samples).passed  # max=57 > 30*1.5=45


# ── op >= 参照×factor：尖峰帧 breakdown 之和 ≥ frameMs×0.6 ──

def test_ge_ref_factor_fail():
    samples = {".bd": S(["10", "10", "5"]), "#frameMs": S(["100"])}
    spec = {"id": "breakdown", "value": {"selector": ".bd", "aggregate": "sum"}, "op": ">=", "ref": {"selector": "#frameMs"}, "factor": 0.6}
    assert not assert_data_invariant(spec, samples).passed  # sum=25 < 100*0.6=60


# ── op non_empty：凡声称逐帧/spike 的数据，尖峰帧必须非空 ──

def test_non_empty_pass_and_fail():
    spec = {"id": "spike_nonempty", "value": {"selector": ".spike-row"}, "op": "non_empty"}
    assert assert_data_invariant(spec, {".spike-row": S(["a", "b"], count=2)}).passed
    assert not assert_data_invariant(spec, {".spike-row": S([], count=0)}).passed


# ── 数值解析：千分位 / 单位 / 百分号 ──

def test_number_parsing_commas():
    spec = {"id": "frame_lt_cap", "value": {"selector": "#frame"}, "op": "<", "ref": {"selector": "#cap"}, "factor": 2}
    assert assert_data_invariant(spec, {"#frame": S(["1,270,000"]), "#cap": S(["650000"])}).passed  # 1.27M < 1.3M
    assert not assert_data_invariant(spec, {"#frame": S(["1,270,000"]), "#cap": S(["600000"])}).passed  # 1.27M > 1.2M


def test_number_parsing_with_unit_suffix():
    samples = {".fps": S(["57.3 fps"]), "#target": S(["30 FPS"])}
    spec = {"id": "fps", "value": {"selector": ".fps", "aggregate": "max"}, "op": "<=", "ref": {"selector": "#target"}, "factor": 1.5}
    assert not assert_data_invariant(spec, samples).passed  # 57.3 > 45


# ── extract: count（按匹配元素个数取值）──

def test_extract_count():
    samples = {".err": S(["e1", "e2", "e3"], count=3)}
    spec = {"id": "few_errors", "value": {"selector": ".err", "extract": "count"}, "op": "<=", "ref": {"const": 5}}
    assert assert_data_invariant(spec, samples).passed  # count=3 <= 5


# ── 失败/边界：取不到值、聚合歧义、解析失败、缺 ref、未知 op ──

def test_value_selector_not_collected():
    r = assert_data_invariant({"id": "x", "value": {"selector": ".nope"}, "op": "<=", "ref": {"const": 1}}, {})
    assert not r.passed


def test_aggregate_none_ambiguous_multiple_matches():
    samples = {".v": S(["1", "2"])}  # 2 个匹配但默认 aggregate=none
    spec = {"id": "x", "value": {"selector": ".v"}, "op": "<=", "ref": {"const": 10}}
    r = assert_data_invariant(spec, samples)
    assert not r.passed  # 歧义：必须指定 sum/max/min


def test_unparseable_number():
    samples = {".v": S(["N/A", "--"])}
    spec = {"id": "x", "value": {"selector": ".v", "aggregate": "max"}, "op": "<=", "ref": {"const": 10}}
    assert not assert_data_invariant(spec, samples).passed


def test_missing_ref_for_numeric_op():
    samples = {".v": S(["5"])}
    spec = {"id": "x", "value": {"selector": ".v"}, "op": "<="}  # 数值 op 缺 ref
    assert not assert_data_invariant(spec, samples).passed


def test_unknown_op():
    samples = {".v": S(["5"])}
    spec = {"id": "x", "value": {"selector": ".v"}, "op": "≈", "ref": {"const": 5}}
    assert not assert_data_invariant(spec, samples).passed


def test_severity_warn_propagates():
    samples = {".v": S(["50"])}
    spec = {"id": "x", "value": {"selector": ".v"}, "op": "<=", "ref": {"const": 10}, "severity": "warn"}
    r = assert_data_invariant(spec, samples)
    assert not r.passed
    assert r.severity == Severity.WARN


def test_pass_sets_expected_and_id():
    samples = {".v": S(["5"])}
    spec = {"id": "v_small", "value": {"selector": ".v"}, "op": "<=", "ref": {"const": 10}}
    r = assert_data_invariant(spec, samples)
    assert r.passed
    assert r.assertion_id == "v_small"


# ── 派发：config.data_invariants 经 evaluate_snapshot 真的被跑（无浏览器，注入假快照）──

def test_runner_dispatches_data_invariants():
    from harness.skills.harness_visual_audit.runner import evaluate_snapshot, AuditConfig

    cfg = AuditConfig(
        target="fake.html",
        config={
            "assertions": {},  # 关掉 6 项 DOM 断言，只验 data_invariants 派发
            "data_invariants": [
                {"id": "pct_le_100", "value": {"selector": ".pct", "aggregate": "max"}, "op": "<=", "ref": {"const": 100}},
                {"id": "spike_nonempty", "value": {"selector": ".spike"}, "op": "non_empty"},
            ],
        },
    )
    snapshot = {
        "data_invariant_samples": {
            ".pct": S(["95%", "120%"]),   # max 120 > 100 → fail
            ".spike": S(["x"], count=1),  # 非空 → pass
        }
    }
    res = evaluate_snapshot(cfg, snapshot)
    ids = {r.assertion_id: r.passed for r in res.results}
    assert ids == {"pct_le_100": False, "spike_nonempty": True}


def test_runner_no_data_invariants_by_default():
    """harness-core 默认不内置任何业务不变量（边界）。"""
    from harness.skills.harness_visual_audit.runner import evaluate_snapshot, AuditConfig, DEFAULT_CONFIG

    assert DEFAULT_CONFIG.get("data_invariants", []) == []
    cfg = AuditConfig(target="fake.html", config={"assertions": {}})
    res = evaluate_snapshot(cfg, {"data_invariant_samples": {}})
    assert res.results == []
