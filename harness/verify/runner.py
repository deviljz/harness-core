"""Core runner for a single verify fixture.

Loads spec.md + worktree/ + expected.json from a fixture directory,
constructs a review prompt, calls the LLM provider, and compares
the result against expected.json using keyword matchers.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..review.runner import ReviewResult, _extract_json


@dataclass
class FixtureData:
    name: str
    spec_content: str
    diff_content: str
    subagent_report: str
    expected: dict


def _load_fixture(fixture_dir: Path) -> FixtureData:
    """Load a fixture directory. Raises ValueError if required files are missing."""
    expected_path = fixture_dir / "expected.json"
    if not expected_path.exists():
        raise ValueError(f"Missing expected.json in {fixture_dir}")

    spec_path = fixture_dir / "spec.md"
    spec_content = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""

    worktree_dir = fixture_dir / "worktree"
    diff_content = _build_diff_from_worktree(worktree_dir) if worktree_dir.exists() else ""

    subagent_path = fixture_dir / "subagent_report.txt"
    subagent_report = subagent_path.read_text(encoding="utf-8") if subagent_path.exists() else ""

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    return FixtureData(
        name=fixture_dir.name,
        spec_content=spec_content,
        diff_content=diff_content,
        subagent_report=subagent_report,
        expected=expected,
    )


def _build_diff_from_worktree(worktree_dir: Path) -> str:
    """Build a pseudo-diff from all files in the worktree directory."""
    parts = []
    for path in sorted(worktree_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(worktree_dir)
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = "(binary file)"
            parts.append(f"--- /dev/null\n+++ b/{rel.as_posix()}")
            for line in content.splitlines():
                parts.append(f"+{line}")
    return "\n".join(parts)


def _build_prompt(fixture: FixtureData, template: str) -> str:
    """Fill the review prompt template with fixture data."""
    # Include subagent_report in diff_content so the LLM can evaluate it
    augmented_diff = fixture.diff_content
    if fixture.subagent_report:
        augmented_diff += (
            "\n\n--- Subagent Review Report ---\n"
            + fixture.subagent_report
        )
    return template.format(
        spec_content=fixture.spec_content or "(no spec provided)",
        diff_content=augmented_diff or "(no diff)",
        focus="api_contract, user_flow, testing",
    )


def _load_review_template() -> str:
    here = Path(__file__).parent.parent / "review" / "prompt_template.md"
    if here.exists():
        return here.read_text(encoding="utf-8")
    # Minimal fallback
    return (
        "## Spec\n{spec_content}\n\n"
        "## Diff\n{diff_content}\n\n"
        "Focus: {focus}\n\n"
        'Reply with JSON: {"consistent": bool, "issues": [str, ...]}'
    )


@dataclass
class RunResult:
    fixture_name: str
    passed: bool
    actual_consistent: bool
    issues: list[str] = field(default_factory=list)
    match_detail: str = ""
    prompt_length: int = 0
    error: str | None = None
    dry_run: bool = False


def run_fixture(
    fixture_dir: Path,
    provider=None,
    *,
    dry_run: bool = False,
) -> RunResult:
    """Run one fixture. If dry_run=True, skip LLM call."""
    from ..verify.matchers import match as kw_match

    try:
        fixture = _load_fixture(fixture_dir)
    except ValueError as e:
        return RunResult(
            fixture_name=fixture_dir.name,
            passed=False,
            actual_consistent=False,
            error=str(e),
        )

    template = _load_review_template()
    prompt = _build_prompt(fixture, template)
    prompt_length = len(prompt)

    if dry_run:
        return RunResult(
            fixture_name=fixture.name,
            passed=True,
            actual_consistent=False,
            prompt_length=prompt_length,
            dry_run=True,
            match_detail=f"dry-run: prompt_length={prompt_length}",
        )

    if provider is None:
        return RunResult(
            fixture_name=fixture.name,
            passed=False,
            actual_consistent=False,
            error="No LLM provider available. Use --dry-run or configure a provider.",
        )

    try:
        response = provider.complete(prompt)
    except Exception as e:
        return RunResult(
            fixture_name=fixture.name,
            passed=False,
            actual_consistent=False,
            error=f"LLM call failed: {e}",
        )

    data = _extract_json(response)
    if data is None:
        return RunResult(
            fixture_name=fixture.name,
            passed=False,
            actual_consistent=False,
            issues=[],
            error=f"Could not parse LLM response as JSON. raw={response[:300]}",
        )

    actual_consistent = bool(data.get("consistent", False))
    issues = list(data.get("issues", []))

    match_result = kw_match(
        actual_consistent=actual_consistent,
        issues=issues,
        expected=fixture.expected,
    )

    return RunResult(
        fixture_name=fixture.name,
        passed=match_result.passed,
        actual_consistent=actual_consistent,
        issues=issues,
        match_detail=match_result.detail,
        prompt_length=prompt_length,
    )
