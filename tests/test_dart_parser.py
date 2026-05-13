"""dart parse_results 专项测试 — 覆盖 expanded reporter 格式。"""
from __future__ import annotations

from harness.languages.dart import DartModule
from harness.languages.base import TestRunResult


def _raw(stdout: str, exit_code: int = 0) -> TestRunResult:
    return TestRunResult(
        cmd="flutter test --reporter=expanded",
        cwd=".",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=1000,
    )


class TestDartParserExpandedReporter:
    """Case A: "+5: All tests passed!" — passed=5, failed=0"""

    def test_case_a_all_passed(self):
        mod = DartModule()
        stdout = (
            "00:01 +0: loading test/foo_test.dart\n"
            "00:02 +5: All tests passed!"
        )
        result = mod.parse_results(_raw(stdout, 0))
        assert result.passed == 5
        assert result.failed == 0
        assert result.all_green

    """Case B: "+3 -1" — passed=3, failed=1"""

    def test_case_b_some_failed(self):
        mod = DartModule()
        stdout = (
            "00:01 +0: loading test/foo_test.dart\n"
            "00:02 +3 -1: foo_test failed"
        )
        result = mod.parse_results(_raw(stdout, 1))
        assert result.passed == 3
        assert result.failed == 1
        assert not result.all_green

    def test_case_b_multi_failed(self):
        mod = DartModule()
        stdout = (
            "00:01 +0: loading\n"
            "00:02 +1 -1: first fail\n"
            "00:03 +3 -2: second fail\n"
        )
        result = mod.parse_results(_raw(stdout, 1))
        # 最后一行累计值
        assert result.passed == 3
        assert result.failed == 2

    """Case C: 早期行含 "+0" 不应干扰最终计数"""

    def test_case_c_loading_line_does_not_pollute(self):
        mod = DartModule()
        stdout = (
            "00:00 +0: (suite) loading test/widget_test.dart\n"
            "00:01 +0: widget renders\n"
            "00:02 +1: widget renders\n"
            "00:03 +7: All tests passed!\n"
        )
        result = mod.parse_results(_raw(stdout, 0))
        assert result.passed == 7
        assert result.failed == 0

    """Case D: 零测试但 exit 0 — 不应误报 error"""

    def test_case_d_zero_tests_exit_0(self):
        mod = DartModule()
        stdout = "00:00 +0: All tests passed!"
        result = mod.parse_results(_raw(stdout, 0))
        assert result.passed == 0
        assert result.failed == 0
        assert result.errors == 0

    """Case E: exit non-zero 且无计数 → errors=1"""

    def test_case_e_crash_no_counts(self):
        mod = DartModule()
        stdout = "Error: Flutter SDK not found"
        result = mod.parse_results(_raw(stdout, 127))
        assert result.errors == 1
        assert result.passed == 0
        assert result.failed == 0

    """Case F: skipped (~N) 格式"""

    def test_case_f_skipped(self):
        mod = DartModule()
        stdout = "00:02 +3 ~2: All tests passed (some skipped)!"
        result = mod.parse_results(_raw(stdout, 0))
        assert result.passed == 3
        assert result.skipped == 2
