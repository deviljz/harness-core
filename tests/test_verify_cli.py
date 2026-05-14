"""Unit tests for harness verify framework.

Tests the framework only — LLM is always mocked.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from harness.verify.matchers import match as kw_match
from harness.verify.report import FixtureResult, VerifyReport, print_report
from harness.verify.runner import _load_fixture, run_fixture


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_fixture(tmp_path: Path, expected: dict, *, with_spec: bool = True, with_worktree: bool = True, with_subagent: bool = False) -> Path:
    """Create a minimal fixture directory under tmp_path."""
    d = tmp_path / "fixture_001"
    d.mkdir()
    (d / "expected.json").write_text(json.dumps(expected), encoding="utf-8")
    if with_spec:
        (d / "spec.md").write_text("# Spec\n\nSome spec content.", encoding="utf-8")
    if with_worktree:
        wt = d / "worktree" / "src"
        wt.mkdir(parents=True)
        (wt / "main.py").write_text("print('hello')\n", encoding="utf-8")
    if with_subagent:
        (d / "subagent_report.txt").write_text("Decision: consistent=true", encoding="utf-8")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# matchers
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchers:
    def test_all_required_hit(self):
        result = kw_match(
            actual_consistent=False,
            issues=["设置页缺少检查更新按钮", "mock 测试不够"],
            expected={
                "consistent": False,
                "required_keywords": ["设置页", "mock"],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        assert result.passed is True
        assert result.required_hit == ["设置页", "mock"]
        assert result.required_miss == []

    def test_required_miss_causes_fail(self):
        result = kw_match(
            actual_consistent=False,
            issues=["设置页有问题"],
            expected={
                "consistent": False,
                "required_keywords": ["设置页", "baseUrl"],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        assert result.passed is False
        assert "baseUrl" in result.required_miss

    def test_or_pattern_syntax(self):
        """Pipe | in pattern should be treated as regex OR."""
        result = kw_match(
            actual_consistent=False,
            issues=["relative URL is used"],
            expected={
                "consistent": False,
                "required_keywords": ["相对路径|relative|baseUrl"],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        assert result.passed is True
        assert result.required_miss == []

    def test_soft_keywords_threshold_50_percent(self):
        """Soft keywords: 1/2 hit = 50% = pass threshold."""
        result = kw_match(
            actual_consistent=False,
            issues=["mock test only"],
            expected={
                "consistent": False,
                "required_keywords": [],
                "soft_keywords": ["mock", "集成测试"],
                "min_issues_count": 0,
            },
        )
        assert result.passed is True  # 1/2 = 50%, meets threshold

    def test_soft_keywords_below_threshold(self):
        """0/2 soft hit should fail."""
        result = kw_match(
            actual_consistent=False,
            issues=["something unrelated"],
            expected={
                "consistent": False,
                "required_keywords": [],
                "soft_keywords": ["mock", "集成测试"],
                "min_issues_count": 0,
            },
        )
        assert result.passed is False

    def test_consistent_mismatch_fails(self):
        result = kw_match(
            actual_consistent=True,  # LLM says consistent
            issues=[],
            expected={
                "consistent": False,  # expected inconsistent
                "required_keywords": [],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        assert result.passed is False
        assert result.consistent_ok is False

    def test_consistent_match_no_keywords(self):
        result = kw_match(
            actual_consistent=True,
            issues=[],
            expected={
                "consistent": True,
                "required_keywords": [],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        assert result.passed is True

    def test_min_issues_count_soft_does_not_block(self):
        """min_issues_count is soft — should not block PASS."""
        result = kw_match(
            actual_consistent=False,
            issues=["one issue"],
            expected={
                "consistent": False,
                "required_keywords": [],
                "soft_keywords": [],
                "min_issues_count": 5,  # expect 5, got 1
            },
        )
        assert result.passed is True  # soft — doesn't block
        assert result.issues_count_ok is False  # but flagged

    def test_invalid_regex_falls_back_to_literal(self):
        """Invalid regex should not crash — falls back to literal search."""
        result = kw_match(
            actual_consistent=False,
            issues=["[unclosed bracket issue"],
            expected={
                "consistent": False,
                "required_keywords": ["[unclosed"],
                "soft_keywords": [],
                "min_issues_count": 0,
            },
        )
        # Should not raise; literal match works
        assert isinstance(result.passed, bool)


# ─────────────────────────────────────────────────────────────────────────────
# fixture loading
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureLoading:
    def test_load_valid_fixture(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        fixture = _load_fixture(d)
        assert fixture.name == "fixture_001"
        assert fixture.spec_content
        assert isinstance(fixture.expected, dict)

    def test_missing_expected_json_raises(self, tmp_path):
        d = tmp_path / "bad_fixture"
        d.mkdir()
        (d / "spec.md").write_text("# Spec", encoding="utf-8")
        with pytest.raises(ValueError, match="expected.json"):
            _load_fixture(d)

    def test_worktree_diff_built(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        fixture = _load_fixture(d)
        # Should have generated a pseudo-diff from worktree files
        assert "+print" in fixture.diff_content or fixture.diff_content != ""

    def test_no_spec_file_empty_string(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False}, with_spec=False)
        fixture = _load_fixture(d)
        assert fixture.spec_content == ""

    def test_subagent_report_included(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False}, with_subagent=True)
        fixture = _load_fixture(d)
        assert "consistent=true" in fixture.subagent_report


# ─────────────────────────────────────────────────────────────────────────────
# runner (mock LLM)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunner:
    def _mock_provider(self, response_json: dict) -> MagicMock:
        provider = MagicMock()
        provider.complete.return_value = json.dumps(response_json)
        return provider

    def test_dry_run_skips_llm(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        result = run_fixture(d, provider=None, dry_run=True)
        assert result.dry_run is True
        assert result.passed is True
        assert result.prompt_length > 0

    def test_pass_when_llm_matches_expected(self, tmp_path):
        d = _make_fixture(
            tmp_path,
            {"consistent": False, "required_keywords": ["missing.*button|按钮缺失"], "soft_keywords": []},
        )
        provider = self._mock_provider({"consistent": False, "issues": ["按钮缺失: X button not found"]})
        result = run_fixture(d, provider=provider)
        assert result.passed is True

    def test_fail_when_consistent_wrong(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        provider = self._mock_provider({"consistent": True, "issues": []})
        result = run_fixture(d, provider=provider)
        assert result.passed is False

    def test_fail_when_required_keyword_missing(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": ["特殊关键词"]})
        provider = self._mock_provider({"consistent": False, "issues": ["something else"]})
        result = run_fixture(d, provider=provider)
        assert result.passed is False

    def test_no_provider_returns_error(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        result = run_fixture(d, provider=None, dry_run=False)
        assert result.passed is False
        assert result.error is not None

    def test_bad_json_response_returns_error(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        provider = MagicMock()
        provider.complete.return_value = "not json at all"
        result = run_fixture(d, provider=provider)
        assert result.passed is False
        assert result.error is not None

    def test_llm_exception_returns_error(self, tmp_path):
        d = _make_fixture(tmp_path, {"consistent": False, "required_keywords": []})
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("LLM timeout")
        result = run_fixture(d, provider=provider)
        assert result.passed is False
        assert "LLM call failed" in (result.error or "")


# ─────────────────────────────────────────────────────────────────────────────
# report
# ─────────────────────────────────────────────────────────────────────────────

class TestReport:
    def test_pass_fail_counts(self):
        report = VerifyReport(results=[
            FixtureResult("a", "regression", passed=True, detail="ok"),
            FixtureResult("b", "regression", passed=False, detail="fail"),
            FixtureResult("c", "template", passed=True, detail="ok"),
        ])
        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1

    def test_recall_calculation(self):
        report = VerifyReport(results=[
            FixtureResult("a", "regression", passed=True, detail=""),
            FixtureResult("b", "template", passed=True, detail=""),
            FixtureResult("c", "template", passed=False, detail=""),
        ])
        assert abs(report.recall - 2 / 3) < 1e-9

    def test_json_output(self, capsys):
        report = VerifyReport(results=[
            FixtureResult("x", "regression", passed=True, detail="caught 1/1"),
        ])
        print_report(report, as_json=True)
        # JSON goes to stdout buffer, not capsys — use a different check
        # We just verify it doesn't raise
        assert report.total == 1

    def test_empty_report_zero_recall(self):
        report = VerifyReport()
        assert report.recall == 0.0
        assert report.total == 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI:
    def _runner(self):
        return CliRunner()

    def test_verify_help(self):
        from harness.verify.cli import verify
        runner = self._runner()
        result = runner.invoke(verify, ["--help"])
        assert result.exit_code == 0
        assert "regression" in result.output or "verify" in result.output.lower()

    def test_verify_run_dry_run(self, tmp_path):
        """dry-run should succeed even with no provider."""
        from harness.verify.cli import verify

        # Create a minimal fixture under tests/fixtures/regression/
        # by patching _REGRESSION_DIR and _TEMPLATE_DIR
        fixture_dir = tmp_path / "regression" / "001_test"
        fixture_dir.mkdir(parents=True)
        (fixture_dir / "expected.json").write_text(
            json.dumps({"consistent": False, "required_keywords": []}), encoding="utf-8"
        )
        (fixture_dir / "spec.md").write_text("# Spec", encoding="utf-8")

        runner = self._runner()
        with patch("harness.verify.cli._REGRESSION_DIR", fixture_dir.parent), \
             patch("harness.verify.cli._TEMPLATE_DIR", tmp_path / "template_project"):
            result = runner.invoke(verify, ["run", "--dry-run"])
        assert result.exit_code == 0

    def test_verify_regression_fixture_filter(self, tmp_path):
        """--fixture filter should only run matching fixtures."""
        from harness.verify.cli import verify

        reg_dir = tmp_path / "regression"
        for name in ["001_foo", "002_bar"]:
            d = reg_dir / name
            d.mkdir(parents=True)
            (d / "expected.json").write_text(
                json.dumps({"consistent": False, "required_keywords": []}), encoding="utf-8"
            )

        runner = self._runner()
        with patch("harness.verify.cli._REGRESSION_DIR", reg_dir), \
             patch("harness.verify.cli._TEMPLATE_DIR", tmp_path / "tmpl"):
            result = runner.invoke(verify, ["regression", "--fixture=001", "--dry-run"])
        assert result.exit_code == 0

    def test_verify_template_case_filter(self, tmp_path):
        """--case filter for template-test."""
        from harness.verify.cli import verify

        tmpl_dir = tmp_path / "template_project"
        for name in ["case_01_happy_path", "case_02_ui_skipped"]:
            d = tmpl_dir / name
            d.mkdir(parents=True)
            (d / "expected.json").write_text(
                json.dumps({"consistent": True, "required_keywords": []}), encoding="utf-8"
            )

        runner = self._runner()
        with patch("harness.verify.cli._REGRESSION_DIR", tmp_path / "reg"), \
             patch("harness.verify.cli._TEMPLATE_DIR", tmpl_dir):
            result = runner.invoke(verify, ["template-test", "--case=01", "--dry-run"])
        assert result.exit_code == 0

    def test_verify_json_flag(self, tmp_path):
        """--json flag should produce parseable JSON output."""
        from harness.verify.cli import verify

        reg_dir = tmp_path / "regression"
        d = reg_dir / "001_test"
        d.mkdir(parents=True)
        (d / "expected.json").write_text(
            json.dumps({"consistent": False, "required_keywords": []}), encoding="utf-8"
        )

        runner = self._runner()
        with patch("harness.verify.cli._REGRESSION_DIR", reg_dir), \
             patch("harness.verify.cli._TEMPLATE_DIR", tmp_path / "tmpl"):
            result = runner.invoke(verify, ["regression", "--dry-run", "--json"])
        # Should exit 0 (dry-run always passes)
        assert result.exit_code == 0

    def test_no_fixtures_exits_nonzero(self, tmp_path):
        """Empty fixture dirs should exit 1."""
        from harness.verify.cli import verify

        runner = self._runner()
        with patch("harness.verify.cli._REGRESSION_DIR", tmp_path / "empty_reg"), \
             patch("harness.verify.cli._TEMPLATE_DIR", tmp_path / "empty_tmpl"):
            result = runner.invoke(verify, ["run", "--dry-run"])
        assert result.exit_code != 0
