"""验证层调度：给一组 target，跑所有 check，生成报告"""
from __future__ import annotations

import time
from pathlib import Path

from ..config import HarnessConfig, TargetConfig
from ..languages import get_language_module
from ..reporter import CheckResult, ValidationReport, make_session_id


def run_checks(
    config: HarnessConfig,
    project_root: Path,
    *,
    changed_file: str | None = None,
    only_targets: list[str] | None = None,
    trigger: str = "manual",
) -> ValidationReport:
    """跑检查主入口。

    - changed_file=None → 全量跑所有 target
    - changed_file 指定 → 只跑被它命中的 target
    - only_targets 白名单 → 限定在这些 target
    """
    results: list[CheckResult] = []

    target_names_to_run = _resolve_targets(config, changed_file, project_root, only_targets)

    for target in config.targets:
        if target.name not in target_names_to_run:
            continue
        results.extend(_run_target(target, project_root, changed_file))

    return ValidationReport(
        session_id=make_session_id(),
        timestamp=time.time(),
        project=config.project,
        trigger=trigger,
        results=results,
    )


def _resolve_targets(
    config: HarnessConfig,
    changed_file: str | None,
    project_root: Path,
    only_targets: list[str] | None,
) -> set[str]:
    if only_targets:
        return set(only_targets)
    if changed_file:
        from ..router import route_file

        r = route_file(changed_file, config, project_root)
        if r.ignored or not r.matched_targets:
            return set()
        return set(r.matched_targets)
    return {t.name for t in config.targets}


def _run_target(target: TargetConfig, project_root: Path, changed_file: str | None) -> list[CheckResult]:
    """跑一个 target 的所有 check"""
    mod = get_language_module(target.language)
    target_dict = target.model_dump()
    results: list[CheckResult] = []

    # 1) 跑测试
    test_files: list[str] = []
    if changed_file:
        test_files = mod.find_related_tests(changed_file, target_dict, project_root)
    t0 = time.monotonic()
    raw = mod.run_tests(test_files, target_dict, project_root)
    parsed = mod.parse_results(raw)
    dt = int((time.monotonic() - t0) * 1000)

    status: str
    if parsed.errors > 0 or parsed.failed > 0:
        status = "fail"
    elif parsed.passed == 0:
        status = "warn"
    else:
        status = "pass"

    results.append(
        CheckResult(
            check_name=f"{target.language}_test",
            target=target.name,
            status=status,  # type: ignore
            message=f"{parsed.passed} passed, {parsed.failed} failed, {parsed.skipped} skipped, {parsed.errors} errors",
            details={
                "passed": parsed.passed,
                "failed": parsed.failed,
                "skipped": parsed.skipped,
                "errors": parsed.errors,
                "failures": parsed.failures[:5],  # 限制 5 条防爆炸
                "cmd": raw.cmd,
                "exit_code": raw.exit_code,
            },
            duration_ms=dt,
        )
    )

    # 2) 深度检查（assertion_ast 类）
    if test_files:
        all_issues = []
        for tf in test_files:
            try:
                all_issues.extend(mod.deep_check(tf, project_root))
            except Exception as e:
                results.append(
                    CheckResult(
                        check_name="deep_check_error",
                        target=target.name,
                        status="warn",
                        message=f"deep_check failed on {tf}: {e}",
                    )
                )
        if all_issues:
            results.append(
                CheckResult(
                    check_name="assertion_ast",
                    target=target.name,
                    status="fail",
                    message=f"{len(all_issues)} issue(s)",
                    details={"issues": [
                        {"severity": i.severity, "file": i.file, "line": i.line, "rule": i.rule, "message": i.message}
                        for i in all_issues[:20]
                    ]},
                )
            )
        else:
            results.append(
                CheckResult(
                    check_name="assertion_ast",
                    target=target.name,
                    status="pass",
                    message="no issues",
                )
            )

    return results
