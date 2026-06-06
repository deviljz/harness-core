"""Audit 结果输出 markdown / 控制台."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runner import AuditResult


def build_markdown_report(result: "AuditResult") -> str:
    passed = result.passed
    failed = result.failed
    lines: list[str] = []
    lines.append("# Visual Audit Report")
    lines.append("")
    lines.append(f"Target: `{result.target}`")
    lines.append(f"Total: {len(result.results)} | ✓ PASS: {len(passed)} | ✗ FAIL: {len(failed)}")
    lines.append("")
    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### [{r.assertion_id}] `{r.selector}` ({r.severity.value})")
            if r.actual:
                lines.append(f"- **Actual**: {r.actual}")
            if r.expected:
                lines.append(f"- **Expected**: {r.expected}")
            if r.remediation:
                lines.append(f"- **Fix**: {r.remediation}")
            if r.note:
                lines.append(f"- _note_: {r.note}")
            lines.append("")
    if passed:
        lines.append("## Passed (summary)")
        by_id: dict[str, int] = {}
        for r in passed:
            by_id[r.assertion_id] = by_id.get(r.assertion_id, 0) + 1
        for aid, count in sorted(by_id.items()):
            lines.append(f"- {aid}: {count} pass")
        lines.append("")
    return "\n".join(lines)


def print_console_summary(result: "AuditResult") -> None:
    passed = result.passed
    failed = result.failed
    print(f"== Visual Audit Report ==")
    print(f"Target : {result.target}")
    print(f"Total  : {len(result.results)}")
    print(f"✓ PASS : {len(passed)}")
    print(f"✗ FAIL : {len(failed)}")
    print()
    for r in failed:
        print(f"  ✗ [{r.assertion_id}] ({r.severity.value}) {r.selector}")
        if r.actual:
            print(f"      actual: {r.actual}")
        if r.expected:
            print(f"      expect: {r.expected}")
        if r.remediation:
            print(f"      fix:    {r.remediation}")


def write_report(result: "AuditResult", out_path: str) -> None:
    md = build_markdown_report(result)
    Path(out_path).write_text(md, encoding="utf-8")
