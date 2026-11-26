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


@main.command(help="初始化当前项目（默认 Codex 轻量模式：薄 AGENTS.md + .harness/config.yaml + 4 栏换班卡）")
@click.option(
    "--agent",
    type=click.Choice(["codex", "claude"], case_sensitive=False),
    default="codex",
    show_default=True,
    help="目标 Agent 适配层（codex 轻量模式 | claude 经典 hook 模式）",
)
@click.option("--inspect-json", is_flag=True, help="Codex 模式：输出结构化 JSON（供 Agent 自主完成初始化）")
@click.option("--force-agents", is_flag=True, help="Codex 模式：强制覆盖已有 AGENTS.md（默认保留）")
@click.option("--no-handoff", is_flag=True, help="Codex 模式：跳过生成 .harness/handoff.md 模板")
@click.option("--force", is_flag=True, help="强制覆盖框架文件（run_hook.py + commands）；不动 config.yaml")
@click.option("--reset-config", is_flag=True, help="显式重置 config.yaml 到默认模板（危险：丢 targets 等所有用户配置）")
@click.option("--local", is_flag=True, help="Claude 模式：hook 写入 .claude/settings.local.json（不入 git）")
@click.option("--no-hooks", is_flag=True, help="Claude 模式：跳过 Claude Code hook 安装")
@click.option("--with-gate", is_flag=True, help="Claude 模式：额外装 Stop hook（每轮对话结束跑 --gate）")
@click.option("--pre-commit", is_flag=True, help="额外装 git pre-commit hook（提交前跑 harness check 拦红）")
def init(
    agent: str,
    inspect_json: bool,
    force_agents: bool,
    no_handoff: bool,
    force: bool,
    reset_config: bool,
    local: bool,
    no_hooks: bool,
    with_gate: bool,
    pre_commit: bool,
):
    cwd = Path.cwd()

    if agent.lower() == "codex":
        from .adapters.codex import init_codex_project

        result = init_codex_project(
            cwd,
            force_agents=force_agents,
            reset_config=reset_config,
            create_handoff=not no_handoff,
        )
        if pre_commit:
            from .adapters.generic import install_precommit_hook

            hook = install_precommit_hook(cwd)
            if hook:
                result["created"].append(".git/hooks/pre-commit")
            else:
                result["warnings"].append("pre-commit 跳过：非 git 仓库，或已有非 harness 的 pre-commit")

        if inspect_json:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
            return

        for rel in result["created"]:
            console.print(f"[green]✓[/green] created: {rel}")
        for rel in result["preserved"]:
            console.print(f"[dim]• preserved: {rel}[/dim]")
        for warn in result["warnings"]:
            console.print(f"[yellow]! {warn}[/yellow]")
        console.print("\nNext steps:")
        for idx, step in enumerate(result["next_steps"], 1):
            console.print(f"  {idx}. {step}")
        return

    from .adapters.claude_code import install_hooks

    harness_dir = cwd / ".harness"
    harness_dir.mkdir(exist_ok=True)

    cfg_path = harness_dir / "config.yaml"
    if cfg_path.exists():
        if reset_config:
            cfg_path.write_text(_CONFIG_TEMPLATE.format(project=cwd.name), encoding="utf-8")
            console.print(f"[yellow]![/yellow] {cfg_path} reset to default template")
        else:
            console.print(f"[dim]config.yaml 保留（如需重置请加 --reset-config）[/dim]")
    else:
        cfg_path.write_text(_CONFIG_TEMPLATE.format(project=cwd.name), encoding="utf-8")
        console.print(f"[green]✓[/green] {cfg_path}")

    # reports/ 目录
    (cwd / "reports").mkdir(exist_ok=True)
    # docs/tasks/ 目录
    (cwd / "docs" / "tasks").mkdir(parents=True, exist_ok=True)

    if not no_hooks:
        scope = "local" if local else "shared"
        path = install_hooks(cwd, scope=scope, with_gate=with_gate)
        console.print(f"[green]✓[/green] hooks installed: {path}")

    if pre_commit:
        from .adapters.generic import install_precommit_hook

        hook = install_precommit_hook(cwd)
        if hook:
            console.print(f"[green]✓[/green] git pre-commit hook: {hook}")
        else:
            console.print("[yellow]! pre-commit 跳过：非 git 仓库，或已有非 harness 的 pre-commit（未覆盖）[/yellow]")

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

# 反模式正则检查（跨语言静态扫描）。取消注释开启。
# 顶层 key = 语言名（dart/python/typescript/javascript/go/rust/java/kotlin/swift/csharp），
# "all" 对所有扩展名生效。详见 docs/contributing-anti-patterns.md。
# anti_patterns:
#   dart:
#     - name: self_recursive_getter
#       pattern: '^\\s*\\w+(\\?|<[^>]+>)?\\s+get\\s+(\\w+)\\s*=>\\s*\\2\\s*;'
#       msg: "自递归 getter 必爆栈 (StackOverflowError)"
#       severity: error
#   python:
#     - name: bare_except
#       pattern: '^\\s*except\\s*:\\s*$'
#       msg: "禁止裸 except"
#       severity: error
#     - name: mutable_default_arg
#       pattern: 'def \\w+\\([^)]*=\\s*(\\[\\]|\\{{\\}})\\s*[,)]'
#       msg: "可变默认参数跨调用共享状态，用 None"
#       severity: error
#   csharp:                              # 含 Unity 工程，.cs 文件
#     - name: empty_catch
#       pattern: '^\\s*catch\\s*\\([^)]*\\)\\s*\\{{\\s*\\}}\\s*$'
#       msg: "禁止裸 catch 空块，会吞掉所有异常"
#       severity: error
#     # 注意：纯正则识别不了 #if 上下文，下面这条只能抓 "import 了 UnityEditor"，
#     # 抓不到 "运行时代码真的调了 UnityEditor.X"。
#     # 真要查 IL2CPP build 风险需要 C# parser（Roslyn），不是正则能搞定的。
#     # 当前规则只能当作 "代码卫生提醒"（unused using），所以 severity = warn。
#     - name: editor_using_in_runtime_file
#       pattern: '^using UnityEditor'
#       msg: "运行时脚本里有 'using UnityEditor'——如果是 unused import 建议清理；如果有真实用法必须配 #if UNITY_EDITOR"
#       severity: warn
#       include: ["Assets/Scripts/**/*.cs"]
#       exclude: ["Assets/Scripts/Editor/**", "**/Tests/**"]
#       case: "Unity unused using 卫生（IL2CPP 不强制，但 unused 是噪音）"
#   all:
#     - name: api_key_leak
#       pattern: '(AIza[0-9A-Za-z_-]{{35}}|sk-[a-zA-Z0-9]{{20,}}|ghp_[a-zA-Z0-9]{{36}})'
#       msg: "疑似 API Key 硬编码，必须移到 .env"
#       severity: error

# 核心模块测试覆盖检查。改到 path 时要求 must_have_test 存在，否则 warn。
# core_modules_coverage:
#   - path: mobile/lib/screens/main_tab_screen.dart
#     must_have_test: mobile/test/main_tab_screen_test.dart
#     reason: "打卡入口，曾因自递归 getter 爆栈"
"""


# ════════════════════════════════════════════════════════════════════
# doctor
# ════════════════════════════════════════════════════════════════════


@main.command(help="诊断：config / AGENTS.md / Codex 全局同步 / platform")
def doctor():
    from .adapters.codex import sync_status
    from .router import _IS_WINDOWS

    try:
        cfg = load_config()
    except ConfigError as e:
        err_console.print(f"[red]✗ config load failed: {e}[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] config: project={cfg.project} (agent={cfg.agent})")
    console.print(f"[green]✓[/green] llm: {cfg.llm.provider}")
    console.print(f"[green]✓[/green] platform: {'windows' if _IS_WINDOWS else 'unix'}")
    console.print(f"[green]✓[/green] targets: {len(cfg.targets)}")
    for t in cfg.targets:
        console.print(f"    - {t.name} ({t.language}, root={t.root})")
    if not cfg.targets and not cfg.anti_patterns:
        console.print("[yellow]! no targets or anti_patterns configured yet[/yellow]")
    elif cfg.anti_patterns:
        n_rules = sum(len(v) for v in cfg.anti_patterns.values())
        console.print(f"[green]✓[/green] anti_patterns: {n_rules} rule(s) across {len(cfg.anti_patterns)} lang group(s)")

    cfg_path = find_config()
    root = _project_root(cfg_path)

    # 项目薄 AGENTS.md 体检
    agents_md = root / "AGENTS.md"
    if agents_md.is_file():
        n_lines = len(agents_md.read_text(encoding="utf-8", errors="replace").splitlines())
        if n_lines <= 60:
            console.print(f"[green]✓[/green] AGENTS.md: {n_lines} lines")
        else:
            console.print(f"[yellow]! AGENTS.md has {n_lines} lines (建议保持 ≤40 行入口地图，防膨胀)[/yellow]")
    elif cfg.agent == "codex":
        console.print("[yellow]! AGENTS.md missing (运行 `python -m harness init --agent codex` 生成薄入口)[/yellow]")

    # 本机 ~/.codex/ 同步状态检查
    if cfg.agent == "codex":
        handoff_file = root / ".harness" / "handoff.md"
        if handoff_file.is_file():
            h_lines = len(handoff_file.read_text(encoding="utf-8", errors="replace").splitlines())
            if h_lines > 80:
                console.print(
                    f"[yellow]! .harness/handoff.md has {h_lines} lines (建议 ≤60 行，覆写精简不要无限追加；"
                    "多条任务请用 `python -m harness task`)[/yellow]"
                )
        st = sync_status()
        if st["in_sync"]:
            console.print(f"[green]✓[/green] codex global sync: in sync ({st['codex_home']})")
        else:
            drifted = []
            if st["agents"] != "in_sync":
                drifted.append(f"AGENTS.md({st['agents']})")
            for sk, sv in st["skills"].items():
                if sv != "in_sync":
                    drifted.append(f"skills/{sk}({sv})")
            console.print(
                f"[yellow]! codex global sync drifted ({', '.join(drifted[:4])}); "
                "run `python -m harness sync`[/yellow]"
            )

    # skipped log 提醒
    skipped = root / "skipped.log"
    if skipped.exists():
        lines = skipped.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > 3:
            console.print(f"[yellow]! skipped.log has {len(lines)} entries; review with `harness reports`[/yellow]")


# ════════════════════════════════════════════════════════════════════
# sync — 多机同步 ~/.codex/ 全局铁律与通用工程 Skill
# ════════════════════════════════════════════════════════════════════


@main.command("sync", help="同步 harness-core 中的全局 AGENTS.md 与通用工程 Skill 到本机 ~/.codex/（或 --pull 回拉）")
@click.option("--pull", is_flag=True, help="反向回拉：从本机 ~/.codex/ 拉回已追踪文件到 harness/codex_home/ 以便 git 提交")
@click.option("--status", "show_status", is_flag=True, help="只检查是否一致，不改任何文件")
@click.option("--dry-run", is_flag=True, help="预览变更，不落盘")
@click.option(
    "--only",
    type=click.Choice(["all", "agents", "skills"], case_sensitive=False),
    default="all",
    show_default=True,
    help="同步范围",
)
@click.option("--codex-home", type=click.Path(path_type=Path), default=None, help="显式指定 Codex 配置目录（默认 $CODEX_HOME 或 ~/.codex）")
@click.option("--with-opencode", is_flag=True, help="同时将全局 AGENTS.md 与核心调查/复核 Skill 同步给本机 OpenCode（~/.config/opencode 与 ~/.agents/skills）")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def sync_cmd(
    pull: bool,
    show_status: bool,
    dry_run: bool,
    only: str,
    codex_home: Path | None,
    with_opencode: bool,
    as_json: bool,
):
    from .adapters.codex import pull_from_codex_home, sync_status, sync_to_codex_home, sync_to_opencode

    if show_status:
        st = sync_status(codex_home=codex_home)
        if as_json:
            click.echo(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            icon = "[green]✓[/green]" if st["in_sync"] else "[yellow]![/yellow]"
            console.print(f"{icon} codex_home: {st['codex_home']}")
            console.print(f"  AGENTS.md: {st['agents']}")
            for sk, sv in st["skills"].items():
                console.print(f"  skills/{sk}: {sv}")
        if not st["in_sync"]:
            sys.exit(1)
        return

    if pull:
        res = pull_from_codex_home(codex_home=codex_home, only=only.lower(), dry_run=dry_run)
    else:
        res = sync_to_codex_home(codex_home=codex_home, only=only.lower(), dry_run=dry_run)
        if with_opencode:
            res["opencode"] = sync_to_opencode(dry_run=dry_run)

    if as_json:
        click.echo(json.dumps(res, ensure_ascii=False, indent=2))
        return

    prefix = r"\[dry-run] " if dry_run else ""
    console.print(f"{prefix}[bold]{res['direction']}[/bold] ({res['codex_home']})")
    for item in res["updated"]:
        console.print(f"  [green]✓ updated:[/green] {item}")
    for bak in res.get("backups", []):
        console.print(f"  [dim]backup saved: {bak}[/dim]")
    if res["unchanged"]:
        console.print(f"  [dim]unchanged ({len(res['unchanged'])}): {', '.join(res['unchanged'][:6])}"
                      f"{' ...' if len(res['unchanged']) > 6 else ''}[/dim]")
    for miss in res.get("skipped_missing", []):
        console.print(f"  [yellow]! missing in codex_home:[/yellow] {miss}")
    if "opencode" in res:
        oc = res["opencode"]
        console.print(f"{prefix}[bold]{oc['direction']}[/bold] ({oc['opencode_config_dir']}, {oc['shared_skills_dir']})")
        for item in oc["updated"]:
            console.print(f"  [green]✓ updated:[/green] {item}")
        if oc["unchanged"]:
            console.print(f"  [dim]unchanged ({len(oc['unchanged'])}): {', '.join(oc['unchanged'])}[/dim]")


# ════════════════════════════════════════════════════════════════════
# handoff — 1 页 4 栏换班状态卡
# ════════════════════════════════════════════════════════════════════


@main.command("handoff", help="定位或初始化当前项目的 1 页 4 栏换班状态卡（不污染项目 git）")
@click.option("--global", "use_global", is_flag=True, help="存放到 ~/.codex/handoffs/<project-key>/current.md")
@click.option("--reset", is_flag=True, help="重置为空白 4 栏模板")
@click.option("--show", is_flag=True, help="直接打印当前换班状态卡内容")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def handoff_cmd(use_global: bool, reset: bool, show: bool, as_json: bool):
    from .adapters.codex import ensure_handoff, project_key

    try:
        root = _project_root(find_config())
    except ConfigError:
        root = Path.cwd().resolve()

    path, created = ensure_handoff(root, use_global=use_global, reset=reset)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "path": path.as_posix(),
                    "created": created,
                    "project_key": project_key(root),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    tag = "created" if created else "ready"
    console.print(f"[green]✓[/green] handoff ({tag}): {path}")
    if show:
        click.echo(path.read_text(encoding="utf-8"))


# ════════════════════════════════════════════════════════════════════
# task — 薄总控本地任务板（硬校验 + 防并行撞车 + 子 Agent 任务包）
# ════════════════════════════════════════════════════════════════════


def _resolve_task_root() -> Path:
    try:
        return _project_root(find_config())
    except ConfigError:
        return Path.cwd().resolve()


@main.group("task", help="薄总控任务板：管理 bug/UI/功能单，硬校验改动范围与验收标准，防并行子 Agent 撞车")
def task_group():
    pass


@task_group.command("add", help="登记一条任务单")
@click.argument("task_id")
@click.argument("title")
@click.option("--kind", type=click.Choice(["bug", "ui", "feat", "other"], case_sensitive=False), default="bug", show_default=True)
def task_add(task_id: str, title: str, kind: str):
    from .adapters.codex import TaskValidationError, add_task

    try:
        item = add_task(_resolve_task_root(), task_id, title, kind=kind.lower())
    except TaskValidationError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(2)
    console.print(f"[green]✓[/green] task added: {item['id']} ({item['kind']}) - {item['title']}")


@task_group.command("update", help="更新任务结论/状态（need_fix 强制校验 files + verify + fact，fixing 强制防文件冲突）")
@click.argument("task_id")
@click.option("--title", type=str, default=None, help="标题（首次直接 update 建单时可选填）")
@click.option("--kind", type=click.Choice(["bug", "ui", "feat", "other"], case_sensitive=False), default=None)
@click.option("--status", type=click.Choice(["open", "fixing", "done", "skipped"], case_sensitive=False), default=None)
@click.option("--verdict", type=click.Choice(["pending", "no_fix", "need_fix", "fixed_pending_qa", "blocked_external", "done"], case_sensitive=False), default=None)
@click.option("--fact", type=str, default=None, help="已核实事实（精确到文件:行号，≤400字）")
@click.option("--files", type=str, default=None, help="改动文件边界，逗号分隔（verdict=need_fix 时必填）")
@click.option("--verify", type=str, default=None, help="验收命令或通过标准（verdict=need_fix 时必填）")
@click.option("--note", type=str, default=None, help="补充说明（verdict=blocked_external 时必填缺哪项外部条件）")
@click.option("--owner", type=str, default=None, help="当前执行者（main / subagent / kimi 等）")
@click.option("--force-collision", is_flag=True, help="显式忽略并行文件冲突告警（谨慎使用）")
def task_update(
    task_id: str,
    title: str | None,
    kind: str | None,
    status: str | None,
    verdict: str | None,
    fact: str | None,
    files: str | None,
    verify: str | None,
    note: str | None,
    owner: str | None,
    force_collision: bool,
):
    from .adapters.codex import TaskValidationError, update_task

    try:
        item = update_task(
            _resolve_task_root(),
            task_id,
            title=title,
            kind=kind.lower() if kind else None,
            status=status.lower() if status else None,
            verdict=verdict.lower() if verdict else None,
            fact=fact,
            files=files,
            verify=verify,
            note=note,
            owner=owner,
            force_collision=force_collision,
        )
    except TaskValidationError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(2)
    console.print(
        f"[green]✓[/green] {item['id']} | status={item['status']} | verdict={item['verdict']} | "
        f"files={','.join(item['files']) or '-'}"
    )


@task_group.command("list", help="列出紧凑任务总表")
@click.option("--status", "filter_status", type=click.Choice(["all", "open", "fixing", "done", "skipped"], case_sensitive=False), default="all", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def task_list(filter_status: str, as_json: bool):
    from .adapters.codex import load_tasks
    from .adapters.codex.tasks import VERDICT_LABELS, _item_sort_key

    data = load_tasks(_resolve_task_root())
    items = sorted(data.get("items", []), key=_item_sort_key)
    if filter_status.lower() != "all":
        items = [it for it in items if it.get("status") == filter_status.lower()]
    if as_json:
        click.echo(json.dumps({"project": data.get("project"), "items": items}, ensure_ascii=False, indent=2))
        return
    if not items:
        console.print("[dim]暂无任务单（用 `python -m harness task add <id> <title>` 登记）[/dim]")
        return
    for it in items:
        v = VERDICT_LABELS.get(it.get("verdict", "pending"), it.get("verdict", ""))
        files = ",".join(it.get("files") or []) or "-"
        summary = (it.get("fact") or it.get("title") or "")[:72]
        console.print(f"- [bold]{it['id']}[/bold] [{it['kind']}|{it['status']}|{v}] files={files} | {summary}")


@task_group.command("show", help="查看单条任务详情")
@click.argument("task_id")
def task_show(task_id: str):
    from .adapters.codex import load_tasks

    data = load_tasks(_resolve_task_root())
    key = task_id.strip().lower()
    for it in data.get("items", []):
        if str(it.get("id", "")).strip().lower() == key:
            click.echo(json.dumps(it, ensure_ascii=False, indent=2))
            return
    err_console.print(f"[red]✗ 找不到任务: {task_id}[/red]")
    sys.exit(2)


@task_group.command("brief", help="生成可直接派给干净子 Agent 的精简任务包")
@click.argument("task_id")
@click.option("--mode", type=click.Choice(["auto", "investigate", "fix"], case_sensitive=False), default="auto", show_default=True)
def task_brief(task_id: str, mode: str):
    from .adapters.codex import TaskValidationError, build_subagent_brief

    try:
        text = build_subagent_brief(_resolve_task_root(), task_id, mode=mode.lower())
    except TaskValidationError as e:
        err_console.print(f"[red]✗ {e}[/red]")
        sys.exit(2)
    click.echo(text)


@task_group.command("done-check", help="长任务收尾硬检：仍有未完成的必做单时返回 exit 2，防止半路见好就收")
@click.option("--prefix", type=str, default=None, help="只检查指定编号前缀的任务（如 MUMU- 或 OFFLINE-）")
@click.option("--kind", type=click.Choice(["bug", "ui", "feat", "other"], case_sensitive=False), default=None)
@click.option("--strict", is_flag=True, help="严格模式：除 done/skipped/blocked_external 外一律视为未完成")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def task_done_check(prefix: str | None, kind: str | None, strict: bool, as_json: bool):
    from .adapters.codex import check_unfinished_tasks
    from .adapters.codex.tasks import VERDICT_LABELS

    res = check_unfinished_tasks(
        _resolve_task_root(),
        prefix=prefix,
        kind=kind.lower() if kind else None,
        strict=strict,
    )
    if as_json:
        click.echo(json.dumps(res, ensure_ascii=False, indent=2))
    elif res["ready"]:
        console.print(
            f"[green]✓ done-check GREEN[/green]（已核对 {res['matched_count']} 条，无剩余未完成必做单）"
        )
    else:
        console.print(
            f"[red]✗ done-check RED[/red]：还有 {res['unfinished_count']}/{res['matched_count']} 条未完成，禁止提前收尾："
        )
        for it in res["unfinished"]:
            v = VERDICT_LABELS.get(it.get("verdict", "pending"), it.get("verdict", ""))
            console.print(f"  - [bold]{it['id']}[/bold] [{it['status']}|{v}] {it.get('title', '')}")
    if not res["ready"]:
        sys.exit(2)


@task_group.command("clear", help="清理已完成/跳过（或全部）任务单")
@click.option("--all", "clear_all", is_flag=True, help="清空全部任务单（默认只清 done/skipped）")
def task_clear(clear_all: bool):
    from .adapters.codex import clear_tasks

    n = clear_tasks(_resolve_task_root(), only_done=not clear_all)
    console.print(f"[green]✓[/green] removed {n} task(s)")


# ════════════════════════════════════════════════════════════════════
# diff-guard — 改动预算硬闸门（防过度防御 / 擅自大改 / 巨无霸提交）
# ════════════════════════════════════════════════════════════════════


@main.command("diff-guard", help="改动预算硬闸门：检查运行代码文件数、净增行数与高危核心枢纽文件（超限返回 exit 2）")
@click.option("--base", type=str, default="HEAD", show_default=True, help="git diff 基线")
@click.option("--staged", is_flag=True, help="只检查暂存区（git diff --cached）")
@click.option("--max-files", type=int, default=None, help="覆盖运行代码文件数上限（默认读 config 或 3）")
@click.option("--max-net-lines", type=int, default=None, help="覆盖运行代码净增行数上限（默认读 config 或 80）")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def diff_guard_cmd(base: str, staged: bool, max_files: int | None, max_net_lines: int | None, as_json: bool):
    from .adapters.codex import run_diff_guard

    try:
        cfg = load_config()
        root = _project_root(find_config())
        b = cfg.diff_budget
        mf = max_files if max_files is not None else b.max_runtime_files
        ml = max_net_lines if max_net_lines is not None else b.max_net_added_lines
        hubs = list(b.hub_files)
        ignores = list(b.ignore_paths) + list(cfg.ignore_paths_global)
    except ConfigError:
        root = Path.cwd().resolve()
        mf = max_files if max_files is not None else 3
        ml = max_net_lines if max_net_lines is not None else 80
        hubs = []
        ignores = []

    try:
        res = run_diff_guard(
            root,
            base=base,
            staged=staged,
            max_runtime_files=mf,
            max_net_added_lines=ml,
            hub_files=hubs,
            extra_ignore=ignores,
        )
    except RuntimeError as e:
        err_console.print(f"[red]✗ diff-guard error: {e}[/red]")
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        rt = res["runtime"]
        nrt = res["non_runtime"]
        if res["status"] == "green":
            console.print(
                f"[green]✓ diff-guard GREEN[/green] ({res['scope']}): "
                f"runtime {rt['files_count']} file(s), +{rt['added']}/-{rt['deleted']} (net {rt['net']:+d}); "
                f"tests/docs {nrt['files_count']} file(s) (+{nrt['added']}/-{nrt['deleted']})"
            )
        else:
            console.print(
                f"[red]✗ diff-guard RED[/red] ({res['scope']}): "
                f"runtime {rt['files_count']} file(s), +{rt['added']}/-{rt['deleted']} (net {rt['net']:+d}); "
                f"tests/docs {nrt['files_count']} file(s) (+{nrt['added']}/-{nrt['deleted']})"
            )
            for t in res["triggers"]:
                console.print(f"  [yellow]![/yellow] {t}")

    if res["status"] == "red":
        sys.exit(2)


# ════════════════════════════════════════════════════════════════════
# baseline — 对标参考实现，扫覆盖度差距写入 spec
# ════════════════════════════════════════════════════════════════════


@main.command(
    "baseline",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
    help="对标参考实现，扫覆盖度差距写入 spec（用法: harness baseline scan --source ... --target ... [--spec ...]）",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def baseline(args):
    """转发到 harness_baseline skill 的 CLI（复用其 argparse 实现）。"""
    from .skills.harness_baseline.cli import main as baseline_main

    sys.exit(baseline_main(list(args)))


# ════════════════════════════════════════════════════════════════════
# visual-audit — 对渲染后的 UI 跑 DOM/视觉断言
# ════════════════════════════════════════════════════════════════════


@main.command(
    "visual-audit",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
    help="对渲染后的 UI（HTML 报告 / web app）跑 DOM/视觉断言"
    "（用法: harness visual-audit --target ... [--config ...] [--report ...]）",
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def visual_audit(args):
    """转发到 harness_visual_audit skill 的 CLI（复用其 argparse 实现）。"""
    from .skills.harness_visual_audit.cli import main as visual_audit_main

    sys.exit(visual_audit_main(list(args)))


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
    # 用 ensure_ascii=True 把所有非 ASCII 字符转义为 \uXXXX，输出为纯 ASCII。
    # 这样在任何 locale（包括 Windows GBK/cp936）下 python -m json.tool 等管道工具
    # 都能正确解析，同时 json.loads 仍会自动还原 \uXXXX 为 Unicode。
    # 直接写 bytes 到 stdout.buffer，绕过 Windows 文本模式的 \n→\r\n 转换。
    out = json.dumps(packed, ensure_ascii=True, indent=2)
    sys.stdout.buffer.write(out.encode("ascii"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


@main.command(help="对最近 diff 做 review（直接调 LLM provider；推荐走 skill 更灵活）")
@click.option("--spec", "spec_path", type=click.Path(exists=True), default=None)
@click.option("--base", type=str, default="HEAD", help="git diff base")
@click.option("--emit-prompt", is_flag=True,
              help="非轮询模式第一步：只把 review prompt 写到文件后退出（不调 LLM）")
@click.option("--response-file", "response_file", type=click.Path(), default=None,
              help="非轮询模式：从该文件读外部 AI 的 review JSON 回灌（不调 LLM、不轮询）")
def review(spec_path: str | None, base: str, emit_prompt: bool, response_file: str | None):
    """走 LLM provider（manual / 将来的 openai 等）。skill 模式下推荐 review-data。

    非轮询两步模式（适合 Hermes 等自跑 CLI 的 AI，避免 manual provider 轮询超时）：
      1. harness review --spec X --emit-prompt --response-file r.json   # 出 prompt 到 r.json.prompt.md
      2. <外部 AI 审 prompt，把 {"consistent":..,"issues":[..]} 写进 r.json>
      3. harness review --spec X --response-file r.json                 # 回灌，不轮询
    """
    from .review import build_review_prompt, parse_review_response, run_review

    cfg = load_config()
    cfg_path = find_config()
    root = _project_root(cfg_path)
    focus = ",".join(cfg.review.focus) if cfg.review.focus else "api_contract"
    spec = Path(spec_path) if spec_path else None

    # 第一步：只出 prompt
    if emit_prompt:
        prompt = build_review_prompt(root, spec, focus=focus, diff_base=base)
        if prompt is None:
            console.print("[yellow]空 diff，无需 review[/yellow]")
            return
        out = Path(response_file + ".prompt.md") if response_file else (root / ".harness" / "review_prompt.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt, encoding="utf-8")
        console.print(f"[green]✓ prompt 已写入:[/green] {out}")
        console.print(
            "把审查结果 JSON `{\"consistent\": bool, \"issues\": [\"文件:行 - 问题\"]}` 写入 "
            f"{response_file or '<file>'}，再跑 `harness review --spec ... --response-file <file>`"
        )
        return

    # 回灌：从文件读 review 结果（不调 LLM、不轮询）
    if response_file:
        rf = Path(response_file)
        if not rf.exists():
            err_console.print(f"[red]✗ response file 不存在: {rf}[/red]")
            err_console.print(
                "先跑 `harness review --spec ... --emit-prompt --response-file <file>` 生成 prompt，"
                "外部 AI 审完写入该文件再重跑。"
            )
            sys.exit(2)
        result = parse_review_response(rf.read_text(encoding="utf-8"))
    else:
        # 默认：调 provider（manual 会轮询；非交互场景推荐用上面的 --emit-prompt/--response-file 两步）
        from .llm import get_provider

        provider = get_provider(cfg.llm.provider, cfg.llm.model_dump())
        result = run_review(provider, root, spec, focus=focus, diff_base=base)

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

    # 空串特判：Claude Code hook 在某些场景（NotebookEdit / 多文件 MultiEdit / 删除）
    # 会传 $CLAUDE_TOOL_FILE_PATH="" 进来。下游用 `if changed_file:` 判断，空串会被
    # 误认为"未指定文件"从而 fallback 跑全量 pytest（曾导致 PyQt UI 测试弹窗抢焦点）。
    # 显式空串视为 hook race，静默 skip；和"完全不传 --on-edit（manual 全量）"语义不同。
    if on_edit is not None and not on_edit.strip():
        console.print("[dim]skipped: empty --on-edit (likely hook race / non-file edit)[/dim]")
        return

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
    # Codex 模式下若项目根没有 reports/，默认写进 .harness/reports/（被 .harness/.gitignore 忽略，不污染项目根目录）
    reports_dir = (
        root / ".harness" / "reports"
        if cfg.agent == "codex" and not (root / "reports").exists()
        else root / "reports"
    )

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

    # ── on-edit: 增量缓存（dry-run 跳过缓存）─────────────────
    if on_edit and cfg.incremental_cache.enabled and not dry_run:
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
    cfg = load_config()
    cfg_path = find_config()
    root = _project_root(cfg_path)
    # Codex 模式下若项目根没有 reports/，默认写进 .harness/reports/（被 .harness/.gitignore 忽略，不污染项目根目录）
    reports_dir = (
        root / ".harness" / "reports"
        if cfg.agent == "codex" and not (root / "reports").exists()
        else root / "reports"
    )
    if not reports_dir.exists():
        console.print("[dim]no reports/ yet[/dim]")
        return
    files = sorted(reports_dir.glob("check_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:count]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        icon = "✓" if data.get("all_green") else "✗"
        console.print(f"{icon} {f.name}  trigger={data.get('trigger', '?')}")


# ════════════════════════════════════════════════════════════════════
# verify
# ════════════════════════════════════════════════════════════════════

from .verify.cli import verify  # noqa: E402

main.add_command(verify)


if __name__ == "__main__":
    main()
