"""fallback 模块测试"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.languages import get_language_module, list_languages
from harness.languages.base import TestRunResult
from harness.languages.fallback import FallbackModule


def test_fallback_registered():
    assert "fallback" in list_languages()
    mod = get_language_module("fallback")
    assert isinstance(mod, FallbackModule)


def test_unknown_language_returns_fallback():
    mod = get_language_module("nonexistent_xyz")
    assert isinstance(mod, FallbackModule)


def test_fallback_find_returns_empty(tmp_path):
    mod = FallbackModule()
    assert mod.find_related_tests("x.cs", {}, tmp_path) == []


def test_fallback_run_cmd_success(tmp_path):
    mod = FallbackModule()
    target_cfg = {
        "checks": {
            "smoke": {"cmd": "python -c \"print('hi')\""},
        }
    }
    raw = mod.run_tests([], target_cfg, tmp_path)
    assert raw.exit_code == 0
    result = mod.parse_results(raw)
    assert result.all_green


def test_fallback_run_cmd_failure(tmp_path):
    mod = FallbackModule()
    target_cfg = {
        "checks": {
            "smoke": {"cmd": "python -c \"import sys; sys.exit(7)\""},
        }
    }
    raw = mod.run_tests([], target_cfg, tmp_path)
    assert raw.exit_code == 7
    result = mod.parse_results(raw)
    assert result.failed == 1


def test_fallback_no_cmd_configured(tmp_path):
    mod = FallbackModule()
    raw = mod.run_tests([], {}, tmp_path)
    assert raw.exit_code == 0
    assert "no check with 'cmd'" in raw.stderr


def test_fallback_custom_cwd(tmp_path):
    mod = FallbackModule()
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    target_cfg = {
        "checks": {
            "smoke": {"cmd": "python -c \"import os; print(os.getcwd())\"", "cwd": str(subdir)},
        }
    }
    raw = mod.run_tests([], target_cfg, tmp_path)
    assert "subdir" in raw.stdout.lower()
