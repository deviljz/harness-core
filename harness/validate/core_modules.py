"""核心模块测试覆盖检查。

config.core_modules_coverage 列出关键源文件 → 必须有对应测试。
缺测试 → warn（不 fail，因为补测试是渐进过程）。

触发场景：
- changed_file 命中 core_modules 列表 → 单条检查
- 全量扫描 → 检查所有 entries
"""
from __future__ import annotations

from pathlib import Path

from ..config import CoreModuleEntry, HarnessConfig
from ..reporter import CheckResult


def _check_entry(entry: CoreModuleEntry, project_root: Path) -> dict | None:
    """返回 finding dict 或 None"""
    test_path = project_root / entry.must_have_test
    if test_path.exists():
        return None
    return {
        "path": entry.path,
        "must_have_test": entry.must_have_test,
        "reason": entry.reason or "",
    }


def run_core_modules_coverage(
    config: HarnessConfig,
    project_root: Path,
    changed_file: str | None,
) -> CheckResult:
    """检查 core_modules_coverage 列出的文件是否有对应测试。"""
    entries = config.core_modules_coverage
    if not entries:
        return CheckResult(
            check_name="core_modules_coverage",
            target="global",
            status="skip",
            message="no core_modules_coverage configured",
        )

    if changed_file:
        rel = _to_rel(changed_file, project_root)
        relevant = [e for e in entries if e.path == rel]
    else:
        relevant = list(entries)

    findings = []
    for e in relevant:
        f = _check_entry(e, project_root)
        if f:
            findings.append(f)

    if not relevant:
        status = "skip"
        msg = "changed_file not in core_modules list"
    elif findings:
        status = "warn"
        msg = f"{len(findings)} core module(s) missing test"
    else:
        status = "pass"
        msg = f"{len(relevant)} core module(s) covered"

    return CheckResult(
        check_name="core_modules_coverage",
        target="global",
        status=status,
        message=msg,
        details={"missing": findings} if findings else {},
    )


def _to_rel(file_path: str, project_root: Path) -> str:
    p = Path(file_path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(project_root.resolve()).as_posix()
        except Exception:
            return p.as_posix()
    return Path(file_path).as_posix()
