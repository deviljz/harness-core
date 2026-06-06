"""--fail-on 退出码阈值接线 + 报告 severity 展示.

cli.py 定义了 --fail-on {error,warn} 但 main() 未使用（连通性 bug：参数定义了没接线），
导致 severity=warn 的 FAIL 也让退出码非零，warn 语义形同虚设。
"""

import pytest

from harness.skills.harness_visual_audit import cli as va_cli
from harness.skills.harness_visual_audit.assertions import AssertionResult, Severity
from harness.skills.harness_visual_audit.runner import AuditResult


def _fake_result(*results: AssertionResult) -> AuditResult:
    return AuditResult(target="fake.html", results=list(results))


def _warn_fail() -> AssertionResult:
    return AssertionResult("W1", False, Severity.WARN, actual="软违规", expected="无")


def _error_fail() -> AssertionResult:
    return AssertionResult("E1", False, Severity.ERROR, actual="硬违规", expected="无")


@pytest.fixture
def patch_audit(monkeypatch):
    """替换 run_audit（playwright/浏览器边界），注入构造好的结果."""
    def _patch(result: AuditResult):
        monkeypatch.setattr(va_cli, "run_audit", lambda cfg: result)
    return _patch


# ---------- 退出码阈值 ----------

def test_warn_only_failure_default_exits_zero(patch_audit):
    # 默认 --fail-on=error：仅 warn 级失败 → 退出码 0（warn 不挡门）
    patch_audit(_fake_result(_warn_fail()))
    assert va_cli.main(["--target", "fake.html"]) == 0


def test_warn_only_failure_fail_on_warn_exits_nonzero(patch_audit):
    patch_audit(_fake_result(_warn_fail()))
    assert va_cli.main(["--target", "fake.html", "--fail-on", "warn"]) == 1


def test_error_failure_default_exits_nonzero(patch_audit):
    patch_audit(_fake_result(_error_fail(), _warn_fail()))
    assert va_cli.main(["--target", "fake.html"]) == 1


def test_all_pass_exits_zero(patch_audit):
    patch_audit(_fake_result(AssertionResult("OK", True)))
    assert va_cli.main(["--target", "fake.html"]) == 0


# ---------- 报告里 warn/error 可区分 ----------

def test_markdown_report_shows_severity():
    from harness.skills.harness_visual_audit.report import build_markdown_report

    md = build_markdown_report(_fake_result(_warn_fail(), _error_fail()))
    assert "warn" in md   # warn 级失败必须在报告里可辨识
    assert "error" in md
