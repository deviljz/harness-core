"""Spec.md 写入 gap 小节."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diff import GapResult


SECTION_HEADER = "## 覆盖度差距"
SECTION_MARKER_BEGIN = "<!-- harness-baseline-begin -->"
SECTION_MARKER_END = "<!-- harness-baseline-end -->"

# 在 spec.md 中找 Boundaries 小节，把覆盖度差距插在它之前
BOUNDARIES_HEADERS = [
    "## Boundaries",
    "## 边界",
    "## 7. Boundaries",
    "## §7 Boundaries",
]


def build_gap_markdown(gap: "GapResult", baseline_source: str) -> str:
    """构建覆盖度差距 markdown."""
    today = date.today().isoformat()
    lines = [
        SECTION_MARKER_BEGIN,
        f"{SECTION_HEADER} (baseline: `{baseline_source}`, scanned: {today})",
        "",
        f"**Counts**: ✓ {len(gap.aligned)} / 🟡 {len(gap.partial)} / ❌ {len(gap.missing)}",
        "",
        "| 状态 | Baseline | Target | 备注 |",
        "|---|---|---|---|",
    ]
    for it in gap.aligned:
        lines.append(f"| ✓ | {it.baseline_label} | {it.target_label} | |")
    for it in gap.partial:
        lines.append(f"| 🟡 | {it.baseline_label} | {it.target_label} | {it.note} |")
    for it in gap.missing:
        lines.append(f"| ❌ | {it.baseline_label} | — | {it.note} |")
    lines.append("")
    lines.append(
        "**Action**: 此处列出的 missing/partial 项必须在 Boundaries 显式声明\"不做\"（带 reason），或在后续 milestone 实现。"
    )
    lines.append(SECTION_MARKER_END)
    return "\n".join(lines)


def write_spec_gap_section(
    spec_path: str | Path,
    gap: "GapResult",
    baseline_source: str,
) -> None:
    """把 gap 小节写入 spec.md（在 Boundaries 之前；已存在则替换）."""
    path = Path(spec_path)
    md = build_gap_markdown(gap, baseline_source)

    if not path.exists():
        path.write_text(md + "\n", encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8")

    # idempotent: 已有 baseline section → 替换
    if SECTION_MARKER_BEGIN in content and SECTION_MARKER_END in content:
        before, _, rest = content.partition(SECTION_MARKER_BEGIN)
        _, _, after = rest.partition(SECTION_MARKER_END)
        # after 包含可能的换行
        after = after.lstrip("\n")
        content = before.rstrip() + "\n\n" + md + "\n\n" + after
    else:
        # 找 Boundaries 小节插入
        insert_idx = -1
        for h in BOUNDARIES_HEADERS:
            idx = content.find(h)
            if idx >= 0:
                insert_idx = idx
                break
        if insert_idx >= 0:
            content = (
                content[:insert_idx].rstrip()
                + "\n\n"
                + md
                + "\n\n"
                + content[insert_idx:]
            )
        else:
            # 没找到 Boundaries → 追加末尾
            content = content.rstrip() + "\n\n" + md + "\n"

    path.write_text(content, encoding="utf-8")
