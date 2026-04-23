"""Python 语言模块入口：组装 finder/runner/assertion_ast"""
from __future__ import annotations

from pathlib import Path

from ..base import Issue, LanguageModule, TestResult, TestRunResult
from .assertion_ast import check_test_file
from .finder import find_related_test_files
from .runner import parse_pytest_output, run_pytest


class PythonModule(LanguageModule):
    name = "python"

    def find_related_tests(
        self,
        changed_file: str,
        target_config: dict,
        project_root: Path,
    ) -> list[str]:
        return find_related_test_files(changed_file, target_config, project_root)

    def run_tests(
        self,
        test_files: list[str],
        target_config: dict,
        project_root: Path,
    ) -> TestRunResult:
        return run_pytest(test_files, target_config, project_root)

    def parse_results(self, raw: TestRunResult) -> TestResult:
        return parse_pytest_output(raw)

    def deep_check(self, test_file: str, project_root: Path) -> list[Issue]:
        path = Path(test_file)
        if not path.is_absolute():
            path = project_root / path
        if not path.exists():
            return []
        return check_test_file(path)
