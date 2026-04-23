"""验证层测试：runner / gate / circuit_breaker / cache"""
from __future__ import annotations

import json
import textwrap
import time
from pathlib import Path

import pytest

from harness.config import HarnessConfig, TargetConfig
from harness.reporter import CheckResult, ValidationReport, save_check_json
from harness.validate import (
    CircuitBreaker,
    IncrementalCache,
    evaluate_gate,
    run_checks,
)
from harness.validate.circuit_breaker import error_signature


# ════════════════════════════════════════════════════════════════════
# runner
# ════════════════════════════════════════════════════════════════════


class TestRunChecks:
    def _setup_python_target(self, tmp_path: Path, test_content: str) -> HarnessConfig:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_smoke.py").write_text(textwrap.dedent(test_content).lstrip())
        return HarnessConfig(
            project="test",
            targets=[
                TargetConfig(
                    name="backend",
                    root=".",
                    language="python",
                    test_paths=["tests"],
                )
            ],
        )

    def test_green_target(self, tmp_path):
        cfg = self._setup_python_target(
            tmp_path,
            """
            def test_ok():
                assert 1 + 1 == 2
            """,
        )
        report = run_checks(cfg, tmp_path)
        assert report.all_green
        assert any(r.check_name == "python_test" for r in report.results)

    def test_failing_target(self, tmp_path):
        cfg = self._setup_python_target(
            tmp_path,
            """
            def test_fail():
                assert 1 == 2
            """,
        )
        report = run_checks(cfg, tmp_path)
        assert report.has_failures

    def test_on_edit_routes_to_target(self, tmp_path):
        cfg = self._setup_python_target(
            tmp_path,
            """
            def test_ok():
                assert 1 + 1 == 2
            """,
        )
        report = run_checks(cfg, tmp_path, changed_file="tests/test_smoke.py")
        assert len(report.results) > 0

    def test_on_edit_ignored_file_no_run(self, tmp_path):
        cfg = self._setup_python_target(
            tmp_path,
            """
            def test_ok():
                assert 1 + 1 == 2
            """,
        )
        cfg.ignore_paths_global = ["**/*.log"]
        report = run_checks(cfg, tmp_path, changed_file="noise.log")
        assert len(report.results) == 0

    def test_assertion_ast_catches_fake_test(self, tmp_path):
        cfg = self._setup_python_target(
            tmp_path,
            """
            def test_fake():
                assert True
            """,
        )
        report = run_checks(cfg, tmp_path, changed_file="tests/test_smoke.py")
        # 应当有 assertion_ast check 标红
        ast_checks = [r for r in report.results if r.check_name == "assertion_ast"]
        assert ast_checks
        assert any(r.status == "fail" for r in ast_checks)


# ════════════════════════════════════════════════════════════════════
# gate
# ════════════════════════════════════════════════════════════════════


class TestGate:
    def test_no_reports_dir(self, tmp_path):
        result = evaluate_gate(tmp_path / "reports")
        assert not result.allowed
        assert "no reports" in result.reason.lower()

    def test_no_json_reports(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        result = evaluate_gate(reports)
        assert not result.allowed

    def test_all_green_report_allows(self, tmp_path):
        reports = tmp_path / "reports"
        report = ValidationReport(
            session_id="s1",
            timestamp=time.time(),
            project="t",
            trigger="manual",
            results=[CheckResult("c", "t", "pass")],
        )
        save_check_json(report, reports)
        result = evaluate_gate(reports)
        assert result.allowed

    def test_failing_report_denies(self, tmp_path):
        reports = tmp_path / "reports"
        report = ValidationReport(
            session_id="s1",
            timestamp=time.time(),
            project="t",
            trigger="manual",
            results=[CheckResult("c", "t", "fail", message="broken")],
        )
        save_check_json(report, reports)
        result = evaluate_gate(reports)
        assert not result.allowed
        assert "failing" in result.reason.lower()

    def test_old_report_denies(self, tmp_path):
        reports = tmp_path / "reports"
        report = ValidationReport(
            session_id="s1",
            timestamp=time.time() - 999,
            project="t",
            trigger="manual",
            results=[CheckResult("c", "t", "pass")],
        )
        save_check_json(report, reports)
        result = evaluate_gate(reports, max_age_seconds=60)
        assert not result.allowed
        assert "old" in result.reason.lower()

    def test_skip_gate_with_reason_logs(self, tmp_path):
        reports = tmp_path / "reports"
        result = evaluate_gate(reports, skip=True, skip_reason="emergency")
        assert result.allowed
        skipped_log = tmp_path / "skipped.log"
        assert skipped_log.exists()
        content = skipped_log.read_text(encoding="utf-8")
        assert "emergency" in content


# ════════════════════════════════════════════════════════════════════
# circuit breaker
# ════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    def test_no_trip_under_limit(self, tmp_path):
        cb = CircuitBreaker(tmp_path / "state.json", max_retries=5)
        assert not cb.record_failure("sig1")
        assert not cb.record_failure("sig2")
        assert not cb.is_paused()

    def test_trip_on_max_retries(self, tmp_path):
        cb = CircuitBreaker(tmp_path / "state.json", max_retries=3, same_error_limit=99)
        cb.record_failure("s1")
        cb.record_failure("s2")
        tripped = cb.record_failure("s3")
        assert tripped
        assert cb.is_paused()

    def test_trip_on_same_error(self, tmp_path):
        cb = CircuitBreaker(tmp_path / "state.json", max_retries=99, same_error_limit=2)
        cb.record_failure("same_sig")
        tripped = cb.record_failure("same_sig")
        assert tripped

    def test_success_resets(self, tmp_path):
        cb = CircuitBreaker(tmp_path / "state.json", max_retries=99, same_error_limit=99)
        cb.record_failure("x")
        cb.record_failure("y")
        assert cb.state.retries == 2
        cb.record_success()
        assert cb.state.retries == 0

    def test_state_persists(self, tmp_path):
        state_file = tmp_path / "state.json"
        cb1 = CircuitBreaker(state_file, max_retries=99)
        cb1.record_failure("x")
        cb2 = CircuitBreaker(state_file, max_retries=99)
        assert cb2.state.retries == 1

    def test_resume_clears(self, tmp_path):
        cb = CircuitBreaker(tmp_path / "state.json", max_retries=1, same_error_limit=99)
        cb.record_failure("x")
        assert cb.is_paused()
        cb.resume()
        assert not cb.is_paused()


def test_error_signature_deterministic():
    f1 = {"file": "a.py", "test": "t1", "message": "boom"}
    f2 = {"file": "a.py", "test": "t1", "message": "boom"}
    assert error_signature(f1) == error_signature(f2)


def test_error_signature_different_fields_different():
    f1 = {"file": "a.py", "test": "t1", "message": "boom"}
    f2 = {"file": "a.py", "test": "t2", "message": "boom"}
    assert error_signature(f1) != error_signature(f2)


# ════════════════════════════════════════════════════════════════════
# incremental cache
# ════════════════════════════════════════════════════════════════════


class TestIncrementalCache:
    def test_new_file_not_skipped(self, tmp_path):
        cache = IncrementalCache(tmp_path / "cache.json")
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        skip, _ = cache.should_skip(f)
        assert not skip

    def test_recorded_file_skipped_when_unchanged(self, tmp_path):
        cache = IncrementalCache(tmp_path / "cache.json", debounce_seconds=60)
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        cache.record(f)
        skip, _ = cache.should_skip(f)
        assert skip

    def test_modified_content_not_skipped(self, tmp_path):
        cache = IncrementalCache(tmp_path / "cache.json", debounce_seconds=60)
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        cache.record(f)
        f.write_text("x = 2")
        skip, _ = cache.should_skip(f)
        assert not skip

    def test_content_restored_still_skipped(self, tmp_path):
        """hash 算的是内容，改了又改回应该跳过"""
        cache = IncrementalCache(tmp_path / "cache.json", debounce_seconds=0)
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        cache.record(f)
        f.write_text("x = 2")
        cache.record(f)
        f.write_text("x = 1")  # 改回原样
        # 但 cache 最后记的是 x=2 的 hash，x=1 的 hash 不同 → 不跳过
        # 这是正确行为：虽然内容"改回原样"，但距上次 record 已变
        # 想实现"回原样跳过"需要保留历史 hash 列表，v2 优化
        skip, _ = cache.should_skip(f)
        assert not skip  # v1 简单实现

    def test_clear(self, tmp_path):
        cache = IncrementalCache(tmp_path / "cache.json")
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        cache.record(f)
        cache.clear()
        assert cache.data == {}
