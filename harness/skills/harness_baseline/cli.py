"""harness baseline CLI: harness baseline scan ...

v0.2: --alias-map / --top-level-only / --adaptive
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows 下强制 UTF-8，避免输出 ✓ ❌ → 等 unicode 字符挂 gbk（与 harness/cli.py 同范式；
# 本模块可经 python -m 单独入口运行，不经过 harness/cli.py 的 reconfigure）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from .scanner import scan_baseline, scan_target
from .diff import gap_diff, DEFAULT_FUZZY_THRESHOLD
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
        default=DEFAULT_FUZZY_THRESHOLD,
        help=f"Fuzzy partial match threshold 0.0-1.0 (default {DEFAULT_FUZZY_THRESHOLD})",
    )
    scan.add_argument(
        "--alias-map",
        default=None,
        help="JSON file: {baseline_label: [target_alias, ...]} 语义别名映射，优先匹配",
    )
    scan.add_argument(
        "--top-level-only",
        action="store_true",
        help="v0.2: 只抽 sidebar 顶层项，sub-list 内 a 进 children",
    )
    scan.add_argument(
        "--adaptive",
        action="store_true",
        help="v0.2: 自适应阈值（短词敏感 / 长词宽容）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd != "scan":
        return 2

    alias_map = None
    if args.alias_map:
        alias_path = Path(args.alias_map)
        if not alias_path.exists():
            print(f"alias map file not found: {alias_path}", file=sys.stderr)
            return 2
        raw = json.loads(alias_path.read_text(encoding="utf-8"))
        # 过滤 _comment 字段
        alias_map = {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}

    baseline = scan_baseline(args.source, args.sidebar_selector, args.top_level_only)
    target = scan_target(args.target, args.sidebar_selector, args.top_level_only)
    gap = gap_diff(
        baseline,
        target,
        fuzzy_threshold=args.fuzzy_threshold,
        alias_map=alias_map,
        use_adaptive_threshold=args.adaptive,
    )

    print("== Baseline Coverage Audit ==")
    print(f"Source : {args.source}")
    print(f"Target : {args.target}")
    if alias_map:
        print(f"Alias  : {len(alias_map)} entries from {args.alias_map}")
    if args.adaptive:
        print("Adaptive threshold: ON")
    if args.top_level_only:
        print("Top-level only: ON")
    print()
    print(f"Aligned (✓ {len(gap.aligned)}):")
    for it in gap.aligned[:20]:
        tag = " [alias]" if it.via_alias else ""
        print(f"  ✓ {it.baseline_label}{tag}")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
