"""harness verify CLI subcommand group."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from .report import FixtureResult, VerifyReport, print_report
from .runner import run_fixture

console = Console()
err_console = Console(stderr=True)

# Fixtures root relative to this package (harness/verify/ -> ../../tests/fixtures)
_HERE = Path(__file__).parent
_FIXTURES_ROOT = _HERE.parent.parent / "tests" / "fixtures"
_REGRESSION_DIR = _FIXTURES_ROOT / "regression"
_TEMPLATE_DIR = _FIXTURES_ROOT / "template_project"


def _get_provider():
    """Try to get a configured LLM provider; return None on failure with warning."""
    try:
        from ..config import load_config
        from ..llm import get_provider

        cfg = load_config()
        return get_provider(cfg.llm.provider, cfg.llm.model_dump())
    except Exception as e:
        err_console.print(
            f"[yellow]Warning: could not load LLM provider: {e}[/yellow]\n"
            "[yellow]Use --dry-run for prompt-only mode, or fix your .harness/config.yaml[/yellow]"
        )
        return None


def _load_regression_fixtures(fixture_filter: str | None) -> list[Path]:
    if not _REGRESSION_DIR.exists():
        return []
    dirs = sorted(d for d in _REGRESSION_DIR.iterdir() if d.is_dir())
    if fixture_filter:
        dirs = [d for d in dirs if fixture_filter in d.name]
    return dirs


def _load_template_cases(case_filter: str | None) -> list[Path]:
    if not _TEMPLATE_DIR.exists():
        return []
    dirs = sorted(d for d in _TEMPLATE_DIR.iterdir() if d.is_dir() and d.name.startswith("case_"))
    if case_filter:
        dirs = [d for d in dirs if case_filter in d.name]
    return dirs


def _run_dirs(
    dirs: list[Path],
    suite: str,
    provider,
    dry_run: bool,
) -> list[FixtureResult]:
    results = []
    for d in dirs:
        result = run_fixture(d, provider=provider, dry_run=dry_run)
        results.append(
            FixtureResult(
                name=result.fixture_name,
                suite=suite,  # type: ignore[arg-type]
                passed=result.passed,
                detail=result.match_detail or (f"prompt_length={result.prompt_length}" if dry_run else ""),
                error=result.error,
            )
        )
    return results


@click.group(help="自我验证系统：Regression + Template-test")
def verify():
    pass


@verify.command("run", help="跑全套（regression + template-test）")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON 报告")
@click.option("--dry-run", is_flag=True, help="只组装 prompt，不调 LLM")
def verify_run(as_json: bool, dry_run: bool):
    provider = None if dry_run else _get_provider()

    reg_dirs = _load_regression_fixtures(None)
    tmpl_dirs = _load_template_cases(None)

    if not reg_dirs and not tmpl_dirs:
        err_console.print(f"[red]No fixtures found in {_FIXTURES_ROOT}[/red]")
        sys.exit(1)

    report = VerifyReport()
    report.results += _run_dirs(reg_dirs, "regression", provider, dry_run)
    report.results += _run_dirs(tmpl_dirs, "template", provider, dry_run)

    print_report(report, as_json=as_json)

    if not dry_run and report.failed:
        sys.exit(2)


@verify.command("regression", help="只跑 regression fixtures")
@click.option("--fixture", default=None, help="过滤 fixture 名（子字符串匹配）")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON 报告")
@click.option("--dry-run", is_flag=True, help="只组装 prompt，不调 LLM")
def verify_regression(fixture: str | None, as_json: bool, dry_run: bool):
    provider = None if dry_run else _get_provider()

    dirs = _load_regression_fixtures(fixture)
    if not dirs:
        err_console.print(f"[red]No regression fixtures found (filter={fixture!r})[/red]")
        sys.exit(1)

    report = VerifyReport(results=_run_dirs(dirs, "regression", provider, dry_run))
    print_report(report, as_json=as_json)

    if not dry_run and report.failed:
        sys.exit(2)


@verify.command("template-test", help="只跑 template-test cases")
@click.option("--case", default=None, help="过滤 case 名（子字符串匹配）")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON 报告")
@click.option("--dry-run", is_flag=True, help="只组装 prompt，不调 LLM")
def verify_template_test(case: str | None, as_json: bool, dry_run: bool):
    provider = None if dry_run else _get_provider()

    dirs = _load_template_cases(case)
    if not dirs:
        err_console.print(f"[red]No template-test cases found (filter={case!r})[/red]")
        sys.exit(1)

    report = VerifyReport(results=_run_dirs(dirs, "template", provider, dry_run))
    print_report(report, as_json=as_json)

    if not dry_run and report.failed:
        sys.exit(2)
