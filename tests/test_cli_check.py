"""harness check CLI 边界测试

回归保护：
- --on-edit "" 必须 skip，禁止 fallback 跑全量（hook race / NotebookEdit / 删除场景）
- --on-edit "  " (whitespace only) 同等对待
- 未传 --on-edit 仍 manual 全量（不影响）
"""
from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from harness.cli import main


_MIN_CONFIG = """project: test
ignore_paths_global: []
targets:
  - name: backend
    root: src/
    language: python
    test_paths: [tests/]
"""


def _setup(tmp_path: Path) -> None:
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "config.yaml").write_text(_MIN_CONFIG, encoding="utf-8")
    (tmp_path / "src").mkdir()


def _run_check(tmp_path: Path, *args: str) -> tuple[int, str]:
    runner = CliRunner()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(main, ["check", *args])
        return result.exit_code, result.output
    finally:
        os.chdir(cwd)


class TestCheckOnEditEmptyString:
    def test_empty_string_skips_silently(self, tmp_path):
        """--on-edit "" 必须 skip，不能进入 run_checks"""
        _setup(tmp_path)
        code, output = _run_check(tmp_path, "--on-edit", "")
        assert code == 0
        assert "skipped" in output.lower() or "empty" in output.lower()

    def test_whitespace_only_treated_as_empty(self, tmp_path):
        _setup(tmp_path)
        code, output = _run_check(tmp_path, "--on-edit", "   ")
        assert code == 0
        assert "skipped" in output.lower() or "empty" in output.lower()
