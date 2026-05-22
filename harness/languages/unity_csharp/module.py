"""Unity C# 语言模块入口：组装 finder/runner"""
from __future__ import annotations

from pathlib import Path

from ..base import Issue, LanguageModule, TestResult, TestRunResult
from .finder import find_related_test_files
from .runner import parse_nunit3_xml, run_unity_tests


class UnityCSharpModule(LanguageModule):
    name = "unity_csharp"

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
        return run_unity_tests(test_files, target_config, project_root)

    def parse_results(self, raw: TestRunResult) -> TestResult:
        return parse_nunit3_xml(raw)

    def deep_check(self, test_file: str, project_root: Path) -> list[Issue]:
        # C# AST 静态检查需要 Roslyn (.NET)，Python 端没好用的现成 lib。
        # 当前依靠 anti_patterns 正则做粗筛（在 harness/validate 层），不在这里做。
        # 未来可考虑通过 `dotnet roslyn-analyzers` 子进程 + 解析 sarif 输出来做。
        return []
