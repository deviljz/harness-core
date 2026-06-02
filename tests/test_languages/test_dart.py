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


class TestFlutterResolution:
    """守卫 flutter 可执行路径可配置（flutter_bin），默认 'flutter'。

    与 python 的 _resolve_python / unity 的 _resolve_unity_exe 范式一致：
    flutter 不在 PATH 或需指定特定 SDK 时，target_config['flutter_bin'] 覆盖。
    """

    def test_resolve_defaults_to_flutter(self):
        from harness.languages.dart import _resolve_flutter

        assert _resolve_flutter({}) == "flutter"

    def test_resolve_respects_flutter_bin(self):
        from harness.languages.dart import _resolve_flutter

        assert _resolve_flutter({"flutter_bin": "/opt/flutter/bin/flutter"}) == "/opt/flutter/bin/flutter"

    def test_run_tests_cmd_uses_flutter_bin(self, monkeypatch, tmp_path):
        captured: dict = {}

        def _fake_run_command(cmd, cwd, timeout=600):
            captured["cmd"] = cmd
            return TestRunResult(
                cmd=str(cmd), cwd=str(cwd), exit_code=0,
                stdout="All tests passed!", stderr="", duration_ms=1,
            )

        monkeypatch.setattr("harness.languages.dart.run_command", _fake_run_command)
        DartModule().run_tests([], {"flutter_bin": "/custom/flutter"}, tmp_path)

        cmd = captured["cmd"]
        # win32 下 run_tests 把 cmd join 成 shell 字符串，其它平台是 list；统一成 token 序列
        tokens = cmd.split() if isinstance(cmd, str) else cmd
        assert tokens[0] == "/custom/flutter"
        assert tokens[1] == "test"
