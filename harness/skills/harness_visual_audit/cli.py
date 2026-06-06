"""harness visual-audit CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows 下强制 UTF-8，避免输出 ✓ ✗ 等 unicode 字符挂 gbk（与 harness/cli.py 同范式；
# 本模块可经 python -m 单独入口运行，不经过 harness/cli.py 的 reconfigure）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from .assertions import Severity
from .runner import run_audit, AuditConfig, DEFAULT_CONFIG
from .report import print_console_summary, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness visual-audit",
        description="Run DOM/visual assertions on rendered UI (HTML report / web app).",
    )
    parser.add_argument("--target", required=True, help="HTML 报告路径或 URL")
    parser.add_argument("--config", default=None, help="YAML 配置文件 (覆盖默认)")
    parser.add_argument("--report", default=None, help="markdown 报告输出路径")
    parser.add_argument("--fail-on", default="error", choices=["error", "warn"], help="退出码非零阈值")
    return parser


def _load_config(path: str | None) -> dict:
    if not path:
        return dict(DEFAULT_CONFIG)
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    text = p.read_text(encoding="utf-8")
    # 支持 JSON / YAML（YAML 需 PyYAML，没装则只支持 JSON）
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = AuditConfig(target=args.target, config=_load_config(args.config))
    result = run_audit(cfg)
    print_console_summary(result)
    if args.report:
        write_report(result, args.report)
        print()
        print(f"→ Report: {args.report}")
    # --fail-on=error（默认）：仅 error 级失败挡门；--fail-on=warn：任何失败都挡门
    if args.fail_on == "warn":
        blocking = result.failed
    else:
        blocking = [r for r in result.failed if r.severity == Severity.ERROR]
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
