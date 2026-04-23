"""pytest 执行 + 输出解析。

处理边界情况：
- parametrize 展开的多条 case
- fixture 失败
- collection error（文件里 syntax error）
- xdist 并行（-n auto）
- 测试被 skip
"""
from __future__ import annotations

import re
from pathlib import Path

from ..base import TestResult, TestRunResult, run_command


# ════════════════════════════════════════════════════════════════════
# 运行
# ════════════════════════════════════════════════════════════════════


def run_pytest(
    test_files: list[str],
    target_config: dict,
    project_root: Path,
    *,
    extra_args: list[str] | None = None,
    timeout: int = 600,
) -> TestRunResult:
    """跑 pytest。test_files 为空 → 全量"""
    cmd: list[str] = ["python", "-m", "pytest", "-v", "--tb=short", "--no-header"]
    if extra_args:
        cmd.extend(extra_args)
    if test_files:
        cmd.extend(test_files)
    # 用 shell=False 避免 quoting 问题
    import subprocess
    import time

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestRunResult(
            cmd=" ".join(cmd),
            cwd=str(project_root),
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestRunResult(
            cmd=" ".join(cmd),
            cwd=str(project_root),
            exit_code=124,
            stdout=e.stdout.decode(errors="replace") if e.stdout else "",
            stderr=f"[harness] pytest timeout after {timeout}s",
            duration_ms=duration_ms,
        )


# ════════════════════════════════════════════════════════════════════
# 解析
# ════════════════════════════════════════════════════════════════════


# pytest 总结行：  "===  3 passed, 2 failed, 1 skipped, 1 error in 0.12s ==="
_SUMMARY_RE = re.compile(
    r"=+\s*"
    r"(?:(?P<failed>\d+)\s+failed[,\s]*)?"
    r"(?:(?P<passed>\d+)\s+passed[,\s]*)?"
    r"(?:(?P<skipped>\d+)\s+skipped[,\s]*)?"
    r"(?:(?P<errors>\d+)\s+error[s]?[,\s]*)?"
    r".*?\s*=+",
)

# 每条失败测试的第一行：  "FAILED tests/test_foo.py::test_bar - AssertionError: xxx"
_FAILURE_RE = re.compile(
    r"^(FAILED|ERROR)\s+"
    r"(?P<file>[^:]+)::(?P<test>[^\s-]+)"
    r"(?:\s+-\s+(?P<msg>.+))?$",
    re.MULTILINE,
)


def parse_pytest_output(raw: TestRunResult) -> TestResult:
    out = raw.stdout + "\n" + raw.stderr

    # 先尝试从最后几行找 summary
    summary = None
    for line in reversed(out.splitlines()):
        m = _SUMMARY_RE.search(line)
        if m and any(m.group(k) for k in ("passed", "failed", "skipped", "errors")):
            summary = m
            break

    passed = int(summary.group("passed") or 0) if summary else 0
    failed = int(summary.group("failed") or 0) if summary else 0
    skipped = int(summary.group("skipped") or 0) if summary else 0
    errors = int(summary.group("errors") or 0) if summary else 0

    # Fallback：summary 行缺失（如项目 addopts 里有 -p no:capture 等配置）
    # 直接从 per-test 行里数 PASSED/FAILED/SKIPPED/ERROR 计数
    if summary is None or (passed == 0 and failed == 0 and skipped == 0 and errors == 0):
        fb = _count_per_test_markers(out)
        if any(fb.values()):
            passed, failed, skipped, errors = fb["passed"], fb["failed"], fb["skipped"], fb["errors"]

    # collection error 特殊处理：pytest 输出 "ERRORS" 章节 + 非 0 退出
    if raw.exit_code != 0 and passed == 0 and failed == 0 and errors == 0:
        if "no tests ran" not in out.lower():
            errors = 1

    # 收集失败详情
    failures: list[dict[str, str]] = []
    for m in _FAILURE_RE.finditer(out):
        failures.append(
            {
                "file": m.group("file").strip(),
                "test": m.group("test").strip(),
                "message": (m.group("msg") or "").strip(),
                "traceback": _extract_traceback(out, m.group("test")),
            }
        )

    return TestResult(
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        failures=failures,
        raw_output=out[-4000:],  # 截断，防塞满 AI context
    )


_PER_TEST_RE = re.compile(
    r"^(?:\S+::)?\S+\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\b",
    re.MULTILINE,
)


def _count_per_test_markers(out: str) -> dict[str, int]:
    """当 summary 行缺失时的兜底：逐条测试行数 PASSED/FAILED/SKIPPED/ERROR"""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for m in _PER_TEST_RE.finditer(out):
        kind = m.group(1)
        if kind in ("PASSED", "XPASS"):
            counts["passed"] += 1
        elif kind in ("FAILED", "XFAIL"):
            counts["failed"] += 1
        elif kind == "SKIPPED":
            counts["skipped"] += 1
        elif kind == "ERROR":
            counts["errors"] += 1
    return counts


def _extract_traceback(out: str, test_name: str) -> str:
    """从 pytest 输出里抠出 test_name 对应的 traceback"""
    # 找 "_______ test_name _______" 分隔符
    marker = f"_ {test_name} _"
    idx = out.find(marker)
    if idx < 0:
        return ""
    # 到下一个分隔符或 summary 结束
    rest = out[idx:]
    next_sep = rest.find("\n_______", 10)
    next_sum = rest.find("\n=======", 10)
    end = min(x for x in (next_sep, next_sum) if x > 0) if (next_sep > 0 or next_sum > 0) else len(rest)
    return rest[:end].strip()[:1500]
