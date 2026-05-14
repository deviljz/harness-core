"""Keyword matcher for verify fixtures.

Each fixture's expected.json specifies:
  - consistent: bool (strict match)
  - required_keywords: list[str]  — all must hit (OR patterns with | supported)
  - soft_keywords: list[str]      — >=50% must hit
  - min_issues_count: int         — soft lower bound on issues list length
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


@dataclass
class MatchResult:
    passed: bool
    consistent_ok: bool
    required_hit: list[str] = field(default_factory=list)
    required_miss: list[str] = field(default_factory=list)
    soft_hit: list[str] = field(default_factory=list)
    soft_miss: list[str] = field(default_factory=list)
    issues_count_ok: bool = True
    detail: str = ""


def _text_hits(pattern: str, corpus: str) -> bool:
    """Check if pattern (possibly with | for OR) matches corpus (case-insensitive)."""
    try:
        return bool(re.search(pattern, corpus, re.IGNORECASE))
    except re.error:
        # Treat invalid regex as literal string search
        return pattern.lower() in corpus.lower()


def match(
    *,
    actual_consistent: bool,
    issues: list[str],
    expected: dict,
) -> MatchResult:
    """Compare LLM review result against fixture expected.json."""
    exp_consistent: bool = bool(expected.get("consistent", False))
    required_keywords: list[str] = expected.get("required_keywords", [])
    soft_keywords: list[str] = expected.get("soft_keywords", [])
    min_issues_count: int = int(expected.get("min_issues_count", 0))

    # Combine all issues text for keyword search
    corpus = " ".join(issues)

    # 1. Consistent strict match
    consistent_ok = actual_consistent == exp_consistent

    # 2. Required keywords — all must hit
    req_hit = []
    req_miss = []
    for kw in required_keywords:
        if _text_hits(kw, corpus):
            req_hit.append(kw)
        else:
            req_miss.append(kw)

    # 3. Soft keywords — >=50% must hit
    soft_hit = []
    soft_miss = []
    for kw in soft_keywords:
        if _text_hits(kw, corpus):
            soft_hit.append(kw)
        else:
            soft_miss.append(kw)

    soft_threshold = math.ceil(len(soft_keywords) * 0.5) if soft_keywords else 0
    soft_ok = len(soft_hit) >= soft_threshold

    # 4. Min issues count (soft — warn only, does not block PASS)
    issues_count_ok = len(issues) >= min_issues_count

    # Overall PASS: consistent + all required + soft threshold
    passed = consistent_ok and not req_miss and soft_ok

    # Build detail string
    parts = []
    parts.append(f"consistent={'OK' if consistent_ok else 'FAIL'} (expected={exp_consistent}, got={actual_consistent})")
    if required_keywords:
        parts.append(f"required={len(req_hit)}/{len(required_keywords)}")
    if soft_keywords:
        parts.append(f"soft={len(soft_hit)}/{len(soft_keywords)}")
    if min_issues_count:
        parts.append(f"issues_count={len(issues)}>={min_issues_count}({'OK' if issues_count_ok else 'WARN'})")
    if req_miss:
        parts.append(f"missing_required={req_miss}")

    return MatchResult(
        passed=passed,
        consistent_ok=consistent_ok,
        required_hit=req_hit,
        required_miss=req_miss,
        soft_hit=soft_hit,
        soft_miss=soft_miss,
        issues_count_ok=issues_count_ok,
        detail="; ".join(parts),
    )
