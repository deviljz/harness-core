"""harness baseline CLI: harness baseline scan ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scanner import scan_baseline, scan_target
from .diff import gap_diff
from .writer import write_spec_gap_section


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness baseline",
        description="Coverage gap audit against reference implementation.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan", help="Scan baseline vs target and write gap into spec")
    scan.add_argument("--source", required=True, help="Reference impl URL or local HTML path")
    scan.add_argument("--target", required=True, help="Current impl HTML path")
    scan.add_argument("--spec", default=None, help="spec.md to write gap section into")
    scan.add_argument(
        "--sidebar-selector",
        default=None,
        help="CSS selector for sidebar nav (auto-detect if omitted)",
    )
    scan.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.6,
        help="Fuzzy match similarity threshold for partial match (0.0-1.0)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd != "scan":
        return 2

    baseline = scan_baseline(args.source, args.sidebar_selector)
    target = scan_target(args.target, args.sidebar_selector)
    gap = gap_diff(baseline, target, fuzzy_threshold=args.fuzzy_threshold)

    print("== Baseline Coverage Audit ==")
    print(f"Source : {args.source}")
    print(f"Target : {args.target}")
    print()
    print(f"Aligned (✓ {len(gap.aligned)}):")
    for it in gap.aligned[:20]:
        print(f"  ✓ {it.baseline_label}")
    if len(gap.aligned) > 20:
        print(f"  ... +{len(gap.aligned) - 20} more")
    print()
    print(f"Partial (🟡 {len(gap.partial)}):")
    for it in gap.partial:
        print(f"  🟡 {it.baseline_label} ~ {it.target_label}  ({it.note})")
    print()
    print(f"Missing (❌ {len(gap.missing)}):")
    for it in gap.missing:
        print(f"  ❌ {it.baseline_label}  ({it.note})")

    if args.spec:
        write_spec_gap_section(args.spec, gap, args.source)
        print()
        print(f"→ Spec written: {args.spec} (section: 覆盖度差距)")

    # 退出码：missing > 0 不影响成功（这是 plan 阶段产物），返回 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
