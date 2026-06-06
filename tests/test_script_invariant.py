"""脚本不变量（script_invariants）单测 + evaluate_snapshot 接线测试（纯逻辑，不依赖 playwright）.

机制：在已加载报告页内对一段 JS 表达式求值（复用报告自己的全局函数/数据，零口径漂移），
约定返回 {pass, actual, expected} 或 bool，抛错自动判 FAIL。
区别于 data_invariants（selector 只能取 DOM 当前可见值）：可遍历整个内存数据集做 sanity。
"""

from harness.skills.harness_visual_audit.assertions import (
    assert_script_invariant,
    Severity,
)
from harness.skills.harness_visual_audit.runner import AuditConfig, evaluate_snapshot


# ---------- assert_script_invariant 各分支 ----------

def test_dict_pass():
    r = assert_script_invariant(
        {"id": "X", "expr": "1"}, {"pass": True, "actual": "0 帧违反", "expected": "0"}
    )
    assert r.passed and r.assertion_id == "X"


def test_dict_fail_carries_actual_expected():
    r = assert_script_invariant(
        {"id": "X", "expr": "1"}, {"pass": False, "actual": "3 帧违反", "expected": "0 帧违反"}
    )
    assert not r.passed
    assert r.actual == "3 帧违反" and r.expected == "0 帧违反"


def test_bool_true_pass():
    assert assert_script_invariant({"id": "X", "expr": "1"}, True).passed


def test_bool_false_fail():
    assert not assert_script_invariant({"id": "X", "expr": "1"}, False).passed


def test_expr_threw_is_fail():
    r = assert_script_invariant({"id": "X", "expr": "1"}, {"error": "spkCatNs is not defined"})
    assert not r.passed and "spkCatNs is not defined" in r.actual


def test_missing_result_is_fail():
    r = assert_script_invariant({"id": "X", "expr": "1"}, None)
    assert not r.passed and "未产出" in r.actual


def test_missing_expr_is_fail():
    r = assert_script_invariant({"id": "X"}, True)
    assert not r.passed and "expr" in r.actual


def test_missing_id_is_fail():
    # JS 采集侧会跳过无 id 的条目（结果无处存放）——Python 侧必须给出准确报错，
    # 而不是误导性的「表达式未产出结果」。
    r = assert_script_invariant({"expr": "1"}, None)
    assert not r.passed and "id" in r.actual


def test_unrecognized_result_is_fail():
    r = assert_script_invariant({"id": "X", "expr": "1"}, {"foo": 1})
    assert not r.passed


def test_severity_warn_honored():
    r = assert_script_invariant({"id": "X", "expr": "1", "severity": "warn"}, False)
    assert r.severity == Severity.WARN


def test_default_severity_error():
    r = assert_script_invariant({"id": "X", "expr": "1"}, False)
    assert r.severity == Severity.ERROR


# ---------- evaluate_snapshot 接线（config.script_invariants → snapshot.script_invariant_results）----------

def test_evaluate_snapshot_wires_script_invariants():
    cfg = AuditConfig(
        target="dummy.html",
        config={
            "assertions": {},  # 关掉 6 项 DOM 断言，只测 script_invariants 接线
            "data_invariants": [],
            "script_invariants": [
                {"id": "OK", "expr": "1", "description": "应通过"},
                {"id": "BAD", "expr": "1", "description": "应失败"},
            ],
        },
    )
    snapshot = {
        "script_invariant_results": {
            "OK": {"pass": True, "actual": "0 违反", "expected": "0"},
            "BAD": {"pass": False, "actual": "5 违反", "expected": "0"},
        }
    }
    res = evaluate_snapshot(cfg, snapshot)
    ids_pass = {r.assertion_id: r.passed for r in res.results}
    assert ids_pass == {"OK": True, "BAD": False}
