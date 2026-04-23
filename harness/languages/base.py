"""LanguageModule 抽象基类。

核心约束：新增语言 = 继承这个类实现 4 个方法。核心代码一行不用改。
"""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestRunResult:
    """run_tests 的原始结果：还没解析，只是跑了命令"""
    __test__ = False  # 阻止 pytest 把这个 dataclass 当成测试类收集

    cmd: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class TestResult:
    """解析后的测试结果"""
    __test__ = False

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)
    """每个 failure 至少包含 {file, test, message, traceback}"""
    raw_output: str = ""

    @property
    def all_green(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.passed > 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors


@dataclass
class Issue:
    """深度检查（如 AST）发现的问题"""
    severity: str  # "error" | "warning"
    file: str
    line: int | None
    rule: str  # 如 "forbid_tautology"
    message: str


class LanguageModule(ABC):
    """语言模块接口（4 方法 + 1 可选）"""

    name: str = ""  # 子类覆盖

    @abstractmethod
    def find_related_tests(
        self,
        changed_file: str,
        target_config: dict,
        project_root: Path,
    ) -> list[str]:
        """文件变动 → 相关测试文件路径列表"""

    @abstractmethod
    def run_tests(
        self,
        test_files: list[str],
        target_config: dict,
        project_root: Path,
    ) -> TestRunResult:
        """跑测试。返回原始 subprocess 结果。"""

    @abstractmethod
    def parse_results(self, raw: TestRunResult) -> TestResult:
        """解析 raw 成结构化 TestResult"""

    def deep_check(self, test_file: str, project_root: Path) -> list[Issue]:
        """可选。默认返回空。"""
        return []


def run_command(
    cmd: str | list[str],
    cwd: Path | str,
    timeout: int = 600,
) -> TestRunResult:
    """通用子进程执行 helper。各语言模块的 run_tests 一般会调这个。"""
    import time

    shell = isinstance(cmd, str)
    cmd_str = cmd if shell else " ".join(cmd)
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestRunResult(
            cmd=cmd_str,
            cwd=str(cwd),
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestRunResult(
            cmd=cmd_str,
            cwd=str(cwd),
            exit_code=124,
            stdout=e.stdout.decode(errors="replace") if e.stdout else "",
            stderr=f"[harness] command timeout after {timeout}s\n"
                   + (e.stderr.decode(errors="replace") if e.stderr else ""),
            duration_ms=duration_ms,
        )
