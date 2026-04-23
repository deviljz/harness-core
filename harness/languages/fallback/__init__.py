"""Fallback 语言模块：不知道语言特性，只跑命令。

用于：Unity/C#、Rust/Go、任何新语言还没写完整模块时的兜底。
"""
from __future__ import annotations

from pathlib import Path

from ..base import LanguageModule, TestResult, TestRunResult, run_command


class FallbackModule(LanguageModule):
    """只跑 config 里指定的命令，退出码 0 = 通过。"""

    name = "fallback"

    def find_related_tests(
        self,
        changed_file: str,
        target_config: dict,
        project_root: Path,
    ) -> list[str]:
        """fallback 不知道如何找相关测试，返回空列表 → 触发全量"""
        return []

    def run_tests(
        self,
        test_files: list[str],
        target_config: dict,
        project_root: Path,
    ) -> TestRunResult:
        """从 checks 里找第一个带 cmd 的 check 跑"""
        checks = target_config.get("checks", {})
        for _check_name, check_cfg in checks.items():
            if isinstance(check_cfg, dict) and "cmd" in check_cfg:
                cmd = check_cfg["cmd"]
                cwd = check_cfg.get("cwd", str(project_root))
                timeout = check_cfg.get("timeout", 600)
                return run_command(cmd, cwd, timeout=timeout)
        return TestRunResult(
            cmd="(no cmd configured)",
            cwd=str(project_root),
            exit_code=0,
            stdout="",
            stderr="fallback module: no check with 'cmd' in config",
            duration_ms=0,
        )

    def parse_results(self, raw: TestRunResult) -> TestResult:
        """只能判退出码。0 → 假装 1 通过；非 0 → 1 失败。"""
        if raw.exit_code == 0:
            return TestResult(passed=1, raw_output=raw.stdout)
        return TestResult(
            failed=1,
            failures=[
                {
                    "file": "(fallback)",
                    "test": raw.cmd,
                    "message": f"exit code {raw.exit_code}",
                    "traceback": (raw.stderr or raw.stdout)[:2000],
                }
            ],
            raw_output=raw.stdout + "\n" + raw.stderr,
        )
