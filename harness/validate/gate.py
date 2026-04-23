"""交付闸：读最近一份 check 报告 JSON，判断是否放行"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GateResult:
    allowed: bool
    reason: str
    report_path: Path | None = None


def evaluate_gate(
    reports_dir: Path,
    max_age_seconds: int = 300,
    *,
    skip: bool = False,
    skip_reason: str | None = None,
) -> GateResult:
    """读 reports_dir 里最新的 check_*.json，判断是否允许交付。

    规则：
    - 报告必须存在
    - 报告年龄 <= max_age_seconds（防 Claude 引用古早报告）
    - 报告 all_green 必须为 true
    - skip=True 需配合 skip_reason（调用方已校验）
    """
    if skip:
        # 记录跳过日志
        skipped_log = reports_dir.parent / "skipped.log"
        skipped_log.parent.mkdir(parents=True, exist_ok=True)
        with skipped_log.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\tskip-gate\t{skip_reason}\n")
        return GateResult(allowed=True, reason=f"skip-gate: {skip_reason}")

    if not reports_dir.exists():
        return GateResult(allowed=False, reason="no reports/ dir. Run `harness check` first.")

    check_files = sorted(reports_dir.glob("check_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not check_files:
        return GateResult(allowed=False, reason="no check_*.json reports found. Run `harness check` first.")

    latest = check_files[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return GateResult(allowed=False, reason=f"cannot read latest report {latest.name}: {e}")

    age = time.time() - data.get("timestamp", 0)
    if age > max_age_seconds:
        return GateResult(
            allowed=False,
            reason=f"report {latest.name} is {int(age)}s old (>{max_age_seconds}s). Re-run `harness check`.",
            report_path=latest,
        )

    if not data.get("all_green"):
        failures_count = sum(1 for r in data.get("results", []) if r.get("status") == "fail")
        return GateResult(
            allowed=False,
            reason=f"report {latest.name} has {failures_count} failing check(s). Fix them first.",
            report_path=latest,
        )

    return GateResult(allowed=True, reason=f"report {latest.name} all_green", report_path=latest)
