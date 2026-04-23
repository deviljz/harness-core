"""harness CLI 入口。

所有子命令在此注册。各阶段的具体逻辑分布在对应模块里，
本文件只做命令分发 + 统一异常处理。
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .config import ConfigError, load_config

console = Console()
err_console = Console(stderr=True)


@click.group(help="harness: AI 工程化 Harness 框架")
@click.version_option(__version__)
def main():
    pass


# ════════════════════════════════════════════════════════════════════
# 接入
# ════════════════════════════════════════════════════════════════════


@main.command(help="在当前项目生成 .harness/ 骨架（含 config.yaml 模板）")
@click.option("--force", is_flag=True, help="已存在时覆盖")
def init(force: bool):
    # 阶段 9 实现，当前仅占位
    click.echo("TODO: harness init (阶段 0 暂未实现，阶段 9 完成)")


@main.command(help="诊断接入是否正确")
def doctor():
    # 简版：先做 config 加载 + 基础检查
    from .router import _IS_WINDOWS

    try:
        cfg = load_config()
    except ConfigError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] config loaded: project={cfg.project}")
    console.print(f"[green]✓[/green] targets: {len(cfg.targets)}")
    for t in cfg.targets:
        console.print(f"    - {t.name} ({t.language}, root={t.root})")
    console.print(f"[green]✓[/green] platform: {'windows' if _IS_WINDOWS else 'unix'}")
    console.print(f"[green]✓[/green] llm provider: {cfg.llm.provider}")


# ════════════════════════════════════════════════════════════════════
# 方案层
# ════════════════════════════════════════════════════════════════════


@main.group(help="方案层：spec 文档")
def plan():
    pass


@plan.command("new", help="生成新 spec 骨架")
@click.argument("task_name")
def plan_new(task_name: str):
    click.echo(f"TODO: plan new {task_name} (阶段 6)")


@plan.command("validate", help="校验 spec 合规")
@click.argument("spec_path", type=click.Path(exists=True))
def plan_validate(spec_path: str):
    click.echo(f"TODO: plan validate {spec_path} (阶段 6)")


# ════════════════════════════════════════════════════════════════════
# 执行层
# ════════════════════════════════════════════════════════════════════


@main.command(help="按 spec 执行任务")
@click.argument("spec_path", type=click.Path(exists=True))
def execute(spec_path: str):
    click.echo(f"TODO: execute {spec_path} (阶段 8)")


# ════════════════════════════════════════════════════════════════════
# 审查层
# ════════════════════════════════════════════════════════════════════


@main.command(help="对最近 diff 做 review")
def review():
    click.echo("TODO: review (阶段 7)")


# ════════════════════════════════════════════════════════════════════
# 验证层
# ════════════════════════════════════════════════════════════════════


@main.command(help="跑检查（或手动触发 --on-edit）")
@click.option("--on-edit", "on_edit", type=str, default=None, help="指定刚改的文件")
@click.option("--gate", "gate", is_flag=True, help="交付闸：读最近 check 报告")
@click.option("--dry-run", is_flag=True, help="只报告会跑什么，不真跑")
@click.option("--warn-only", is_flag=True, help="失败只 warn 不阻塞")
@click.option("--skip-gate", is_flag=True, help="强制绕过闸门")
@click.option("--reason", type=str, default=None, help="--skip-gate 时必填理由")
def check(on_edit, gate, dry_run, warn_only, skip_gate, reason):
    if skip_gate and not reason:
        err_console.print("[red]--skip-gate requires --reason \"...\"[/red]")
        sys.exit(2)
    try:
        cfg = load_config()
    except ConfigError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)

    # 阶段 5 实现，这里先打印路由结果
    if on_edit:
        from .config import find_config, project_root
        from .router import route_file

        cfg_path = find_config()
        root = project_root(cfg_path)
        result = route_file(on_edit, cfg, root)
        if result.ignored:
            console.print(f"[dim]ignored: {result.ignore_reason}[/dim]")
            return
        if not result.matched_targets:
            console.print(f"[dim]no target matched for {on_edit}[/dim]")
            return
        console.print(f"[green]matched targets:[/green] {', '.join(result.matched_targets)}")
        console.print("[yellow]TODO: run target checks (阶段 5)[/yellow]")
    else:
        console.print("[yellow]TODO: full check (阶段 5)[/yellow]")


# ════════════════════════════════════════════════════════════════════
# 流程控制
# ════════════════════════════════════════════════════════════════════


@main.command(help="当前是否有暂停的流程（断路器触发后）")
def status():
    click.echo("TODO: status (阶段 5)")


@main.command(help="恢复某次断路器暂停的流程")
@click.argument("ts")
def resume(ts: str):
    click.echo(f"TODO: resume {ts} (阶段 5)")


@main.command(help="列最近 N 次报告")
@click.option("-n", "count", type=int, default=10, help="显示最近几份")
def reports(count: int):
    click.echo(f"TODO: list reports (top {count})")


if __name__ == "__main__":
    main()
