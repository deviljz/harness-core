"""harness CLI 入口"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .config import ConfigError, find_config, load_config, project_root as _project_root

# Windows 下强制 UTF-8，避免 rich 输出 ✓ ✗ 等 unicode 字符挂 gbk
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console()
err_console = Console(stderr=True)


@click.group(help="harness: AI 工程化 Harness 框架")
@click.version_option(__version__)
def main():
    pass


# ════════════════════════════════════════════════════════════════════
# init
# ════════════════════════════════════════════════════════════════════


@main.command(help="在当前项目生成 .harness/ 骨架 + 装 hook")
@click.option("--force", is_flag=True, help="已存在时覆盖 config.yaml")
@click.option("--local", is_flag=True, help="hook 写入 .claude/settings.local.json（不入 git）")
@click.option("--no-hooks", is_flag=True, help="跳过 Claude Code hook 安装")
def init(force: bool, local: bool, no_hooks: bool):
    from .adapters.claude_code import install_hooks

    cwd = Path.cwd()
    harness_dir = cwd / ".harness"
    harness_dir.mkdir(exist_ok=True)

    cfg_path = harness_dir / "config.yaml"
    if cfg_path.exists() and not force:
        console.print(f"[yellow]! {cfg_path} already exists (use --force to overwrite)[/yellow]")
    else:
        cfg_path.write_text(_CONFIG_TEMPLATE.format(project=cwd.name), encoding="utf-8")
        console.print(f"[green]✓[/green] {cfg_path}")

    # reports/ 目录
    (cwd / "reports").mkdir(exist_ok=True)
    # docs/tasks/ 目录
    (cwd / "docs" / "tasks").mkdir(parents=True, exist_ok=True)

    if not no_hooks:
        scope = "local" if local else "shared"
        path = install_hooks(cwd, scope=scope)
        console.print(f"[green]✓[/green] hooks installed: {path}")

    console.print("\nNext steps:")
    console.print("  1. Edit .harness/config.yaml (fill `targets`)")
    console.print("  2. Run `harness doctor`")
    console.print("  3. Run `harness check` to verify")


_CONFIG_TEMPLATE = """# harness-core config
project: {project}

llm:
  provider: claude_agent  # claude_agent | manual

ignore_paths_global:
  - .git/**
  - "**/__pycache__/**"
  - "**/node_modules/**"
  - "**/*.log"
  - "**/.pytest_cache/**"
  - reports/**

circuit_breaker:
  max_retries: 3
  same_error_limit: 2

incremental_cache:
  enabled: true
  debounce_seconds: 30

plan:
  spec_dir: docs/tasks
  require_complexity_field: true

execute:
  complexity_source: spec_field

review:
  enabled: true
  focus: [api_contract, error_handling]

# 在这里按需添加 target
targets: []
  # - name: backend
  #   root: app/
  #   language: python
  #   test_paths: [tests/]
  #   ignore_paths:
  #     - app/migrations/**
  #   checks:
  #     assertion_ast:
  #       forbid_tautology: true

gate:
  require_evidence: true
  evidence_source: harness_report
  max_age_seconds: 300
"""


# ════════════════════════════════════════════════════════════════════
# doctor
# ════════════════════════════════════════════════════════════════════


@main.command(help="诊断：config / hook / platform")
def doctor():
    from .router import _IS_WINDOWS

    try:
        cfg = load_config()
    except ConfigError as e:
        err_console.print(f"[red]✗ config load failed: {e}[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] config: project={cfg.project}")
    console.print(f"[green]✓[/green] llm: {cfg.llm.provider}")
    console.print(f"[green]✓[/green] platform: {'windows' if _IS_WINDOWS else 'unix'}")
    console.print(f"[green]✓[/green] targets: {len(cfg.targets)}")
    for t in cfg.targets:
        console.print(f"    - {t.name} ({t.language}, root={t.root})")
    if not cfg.targets:
        console.print("[yellow]! no targets configured yet[/yellow]")

    # skipped log 提醒
    cfg_path = find_config()
    root = _project_root(cfg_path)
    skipped = root / "skipped.log"
    if skipped.exists():
        lines = skipped.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > 3:
            console.print(f"[yellow]! skipped.log has {len(lines)} entries; review with `harness reports`[/yellow]")


# ════════════════════════════════════════════════════════════════════
# plan
# ════════════════════════════════════════════════════════════════════


@main.group(help="方案层：spec 文档")
def plan():
    pass


@plan.command("new", help="生成新 spec 骨架")
@click.argument("task_name")
def plan_new(task_name: str):
    from .plan.template import render_template, spec_filename

    cfg = load_config()
    cfg_path = find_config()
    root = _project_root(cfg_path)
    spec_dir = root / cfg.plan.spec_dir
    spec_dir.mkdir(parents=True, exist_ok=True)
    out = spec_dir / spec_filename(task_name)
    if out.exists():
        err_console.print(f"[red]✗ {out} already exists[/red]")
        sys.exit(1)
    out.write_text(render_template(task_name), encoding="utf-8")
    console.print(f"[green]✓[/green] {out}")
    console.print("Fill the 6 sections + set **complexity** to simple|complex.")


@plan.command("validate", help="校验 spec 合规")
@click.argument("spec_path", type=click.Path(exists=True))
def plan_validate(spec_path: str):
    from .plan import validate_spec

    issues = validate_spec(Path(spec_path))
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    for w in warnings:
        console.print(f"[yellow]⚠  {w.message}[/yellow]")
    for e in errors:
        console.print(f"[red]✗ {e.message}[/red]")
    if errors:
        sys.exit(1)
    console.print(f"[green]✓[/green] spec valid ({len(warnings)} warnings)")


# ════════════════════════════════════════════════════════════════════
# execute
# ════════════════════════════════════════════════════════════════════


@main.command(help="按 spec 执行任务（输出执行计划）")
@click.argument("spec_path", type=click.Path(exists=True))
def execute(spec_path: str):
    from .execute import plan_execution

    try:
        plan_ = plan_execution(Path(spec_path))
    except FileNotFoundError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    console.print(f"[bold]Execution Plan[/bold]")
    console.print(f"  complexity: {plan_.complexity}")
    console.print(f"  strategy:   {plan_.strategy}")
    if plan_.subtasks:
        console.print(f"  subtasks ({len(plan_.subtasks)}):")
        for st in plan_.subtasks:
            console.print(f"    • {st.name}")
    console.print(f"  {plan_.notes}")


# ════════════════════════════════════════════════════════════════════
# review
# ════════════════════════════════════════════════════════════════════


@main.command("review-data", help="打包 diff+spec 为 JSON（供 skill 给 subagent 用）")
@click.option("--spec", "spec_path", type=click.Path(exists=True), default=None)
@click.option("--base", type=str, default="HEAD", help="git diff base")
def review_data(spec_path: str | None, base: str):
    """skill 模式：打印 {spec_content, diff_content, template} JSON 到 stdout"""
    from .review.diff_packager import package_diff

    cfg_path = find_config()
    root = _project_root(cfg_path)
    packed = package_diff(
        root,
        Path(spec_path) if spec_path else None,
        diff_base=base,
    )
    # 加 prompt template
    template_path = Path(__file__).parent / "review" / "prompt_template.md"
    packed["template"] = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    print(json.dumps(packed, ensure_ascii=False, indent=2))


@main.command(help="对最近 diff 做 review（直接调 LLM provider；推荐走 skill 更灵活）")
@click.option("--spec", "spec_path", type=click.Path(exists=True), default=None)
@click.option("--base", type=str, default="HEAD", help="git diff base")
def review(spec_path: str | None, base: str):
    """走 LLM provider（manual / 将来的 openai 等）。skill 模式下推荐 review-data。"""
    from .llm import get_provider
    from .review import run_review

    cfg = load_config()
    cfg_path = find_config()
    root = _project_root(cfg_path)

    provider = get_provider(cfg.llm.provider, cfg.llm.model_dump())
    result = run_review(
        provider,
        root,
        Path(spec_path) if spec_path else None,
        focus=",".join(cfg.review.focus) if cfg.review.focus else "api_contract",
        diff_base=base,
    )

    if result.error:
        err_console.print(f"[red]✗ {result.error}[/red]")
        if result.raw_response:
            err_console.print(f"[dim]raw: {result.raw_response[:500]}[/dim]")
        sys.exit(1)

    if result.consistent:
        console.print(f"[green]✓ review passed (consistent with spec)[/green]")
    else:
        console.print(f"[red]✗ {len(result.issues)} issue(s) vs spec:[/red]")
        for i in result.issues:
            console.print(f"  - {i}")
        sys.exit(2)


# ════════════════════════════════════════════════════════════════════
# check
# ════════════════════════════════════════════════════════════════════


@main.command(help="跑检查")
@click.option("--on-edit", "on_edit", type=str, default=None, help="指定刚改的文件")
@click.option("--gate", "gate_mode", is_flag=True, help="交付闸：读最近 check 报告")
@click.option("--dry-run", is_flag=True, help="只报告会跑什么，不真跑")
@click.option("--warn-only", is_flag=True, help="失败只 warn 不阻塞")
@click.option("--skip-gate", is_flag=True, help="绕过闸门")
@click.option("--reason", type=str, default=None, help="--skip-gate 时必填")
def check(on_edit, gate_mode, dry_run, warn_only, skip_gate, reason):
    from .reporter import render_markdown, render_xml_compact, save_check_json, save_markdown
    from .validate import evaluate_gate, run_checks
    from .validate.cache import IncrementalCache

    if skip_gate and not reason:
        err_console.print('[red]--skip-gate requires --reason "..."[/red]')
        sys.exit(2)

    try:
        cfg = load_config()
    except ConfigError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)

    cfg_path = find_config()
    root = _project_root(cfg_path)
    reports_dir = root / "reports"

    # ── Gate 模式 ─────────────────────────────────────────────
    if gate_mode:
        result = evaluate_gate(
            reports_dir,
            cfg.gate.max_age_seconds,
            skip=skip_gate,
            skip_reason=reason,
        )
        if result.allowed:
            console.print(f"[green]✓ gate passed: {result.reason}[/green]")
            return
        err_console.print(f"[red]✗ gate denied: {result.reason}[/red]")
        sys.exit(1)

    # ── on-edit: 增量缓存 ─────────────────────────────────────
    if on_edit and cfg.incremental_cache.enabled:
        cache = IncrementalCache(
            root / ".harness" / "check_cache.json",
            cfg.incremental_cache.debounce_seconds,
        )
        abs_path = Path(on_edit)
        if not abs_path.is_absolute():
            abs_path = root / on_edit
        skip, reason_ = cache.should_skip(abs_path)
        if skip:
            console.print(f"[dim]skipped: {reason_}[/dim]")
            return

    # ── Dry run ──────────────────────────────────────────────
    if dry_run:
        from .router import route_file

        if on_edit:
            r = route_file(on_edit, cfg, root)
            if r.ignored:
                console.print(f"[dim]ignored: {r.ignore_reason}[/dim]")
            elif not r.matched_targets:
                console.print(f"[dim]no target matched[/dim]")
            else:
                console.print(f"[yellow]dry-run: would run targets: {', '.join(r.matched_targets)}[/yellow]")
        else:
            console.print(f"[yellow]dry-run: would run all {len(cfg.targets)} targets[/yellow]")
        return

    # ── 真跑 ────────────────────────────────────────────────
    trigger = f"on_edit:{on_edit}" if on_edit else "manual"
    report = run_checks(cfg, root, changed_file=on_edit, trigger=trigger)

    # 保存
    if report.results:
        save_check_json(report, reports_dir)
        save_markdown(report, reports_dir)

    # 记录缓存
    if on_edit and cfg.incremental_cache.enabled:
        cache = IncrementalCache(
            root / ".harness" / "check_cache.json",
            cfg.incremental_cache.debounce_seconds,
        )
        abs_path = Path(on_edit)
        if not abs_path.is_absolute():
            abs_path = root / on_edit
        cache.record(abs_path)

    # 输出给 AI（stdout，紧凑 XML）
    xml = render_xml_compact(report)
    print(xml)

    # 退出码
    if report.has_failures and not warn_only:
        sys.exit(1)


# ════════════════════════════════════════════════════════════════════
# status / resume / reports
# ════════════════════════════════════════════════════════════════════


@main.command(help="当前是否有暂停的流程")
def status():
    cfg_path = find_config()
    root = _project_root(cfg_path)
    state_file = root / ".harness" / "circuit_state.json"
    if not state_file.exists():
        console.print("[green]✓ no paused flow[/green]")
        return
    data = json.loads(state_file.read_text(encoding="utf-8"))
    if data.get("paused"):
        console.print(f"[red]✗ flow paused[/red]")
        console.print(f"  retries:   {data.get('retries')}")
        console.print(f"  last sig:  {data.get('error_signatures', ['?'])[-1][:100]}")
        console.print(f"  resume:    harness resume <ts>")
    else:
        console.print("[green]✓ no paused flow[/green]")


@main.command(help="恢复被断路器暂停的流程")
@click.argument("ts", required=False)
def resume(ts: str | None):
    from .validate import CircuitBreaker

    cfg_path = find_config()
    root = _project_root(cfg_path)
    cb = CircuitBreaker(root / ".harness" / "circuit_state.json")
    cb.resume()
    console.print("[green]✓ flow resumed[/green]")


@main.command(help="列最近 N 次报告")
@click.option("-n", "count", type=int, default=10)
def reports(count: int):
    cfg_path = find_config()
    root = _project_root(cfg_path)
    reports_dir = root / "reports"
    if not reports_dir.exists():
        console.print("[dim]no reports/ yet[/dim]")
        return
    files = sorted(reports_dir.glob("check_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:count]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        icon = "✓" if data.get("all_green") else "✗"
        console.print(f"{icon} {f.name}  trigger={data.get('trigger', '?')}")


if __name__ == "__main__":
    main()
