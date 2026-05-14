"""Report formatter for verify results."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Literal

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

# Windows UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


@dataclass
class FixtureResult:
    name: str
    suite: Literal["regression", "template"]
    passed: bool
    detail: str
    error: str | None = None


@dataclass
class VerifyReport:
    results: list[FixtureResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def recall(self) -> float:
        return self.passed / self.total if self.total else 0.0


def print_report(report: VerifyReport, *, as_json: bool = False) -> None:
    if as_json:
        data = {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "recall": round(report.recall, 3),
            "results": [
                {
                    "name": r.name,
                    "suite": r.suite,
                    "passed": r.passed,
                    "detail": r.detail,
                    "error": r.error,
                }
                for r in report.results
            ],
        }
        out = json.dumps(data, ensure_ascii=False, indent=2)
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return

    # Group by suite
    regression = [r for r in report.results if r.suite == "regression"]
    template = [r for r in report.results if r.suite == "template"]

    def make_table(title: str, rows: list[FixtureResult]) -> Table:
        table = Table(title=title, show_lines=False)
        table.add_column("Fixture", style="bold", min_width=35)
        table.add_column("Result", min_width=6)
        table.add_column("Detail")
        for r in rows:
            status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
            detail = r.error or r.detail
            table.add_row(r.name, status, detail)
        return table

    if regression:
        console.print(make_table("=== Regression Fixtures ===", regression))
    if template:
        console.print(make_table("=== Template-test Cases ===", template))

    recall_str = f"{report.recall * 100:.1f}%"
    summary = (
        f"[bold]Total:[/bold] {report.passed} PASS, {report.failed} FAIL  "
        f"| Recall: {report.passed}/{report.total} = {recall_str}"
    )
    console.print(summary)
