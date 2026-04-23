"""Dart 模块测试（不跑真 flutter，只测解析逻辑和 finder）"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.languages import get_language_module
from harness.languages.base import TestRunResult
from harness.languages.dart import DartModule


def test_dart_registered():
    mod = get_language_module("dart")
    assert isinstance(mod, DartModule)


class TestFinder:
    def test_test_file_itself(self, tmp_path):
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "home_test.dart").touch()
        mod = DartModule()
        found = mod.find_related_tests("test/home_test.dart", {}, tmp_path)
        assert found == ["test/home_test.dart"]

    def test_find_by_module_name(self, tmp_path):
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "home.dart").touch()
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "home_test.dart").touch()
        mod = DartModule()
        found = mod.find_related_tests("lib/home.dart", {"test_paths": ["test"]}, tmp_path)
        assert "test/home_test.dart" in found

    def test_non_dart_file(self, tmp_path):
        mod = DartModule()
        assert mod.find_related_tests("README.md", {}, tmp_path) == []

    def test_no_matching_test(self, tmp_path):
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "lonely.dart").touch()
        (tmp_path / "test").mkdir()
        mod = DartModule()
        assert mod.find_related_tests("lib/lonely.dart", {}, tmp_path) == []


class TestParseResults:
    def _raw(self, stdout: str, exit_code: int = 0) -> TestRunResult:
        return TestRunResult(
            cmd="flutter test",
            cwd=".",
            exit_code=exit_code,
            stdout=stdout,
            stderr="",
            duration_ms=1000,
        )

    def test_all_passed(self):
        mod = DartModule()
        out = "00:01 +5: All tests passed!"
        result = mod.parse_results(self._raw(out, 0))
        assert result.passed == 5
        assert result.failed == 0
        assert result.all_green

    def test_some_failed(self):
        mod = DartModule()
        out = "00:02 +3 -2: Some tests failed."
        result = mod.parse_results(self._raw(out, 1))
        assert result.passed == 3
        assert result.failed == 2
        assert not result.all_green

    def test_exit_non_zero_no_counts(self):
        mod = DartModule()
        out = "Error: could not run flutter"
        result = mod.parse_results(self._raw(out, 127))
        assert result.errors == 1

    def test_failure_extraction(self):
        mod = DartModule()
        out = "00:01 +2 -1: some_test [E] expected a but got b\nSome tests failed."
        result = mod.parse_results(self._raw(out, 1))
        assert result.failed == 1
        assert len(result.failures) >= 1
