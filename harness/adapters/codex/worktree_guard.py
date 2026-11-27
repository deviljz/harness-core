"""Worktree 槽位硬上限与孤儿目录守卫（`python -m harness wt-check`）。

防止 AI 每开一个子任务/构建/排查就随手新建 `<repo>-<topic>-<date>` 目录且结项不清理：
1. 统计当前仓库注册的额外 git worktree 数量（超过 max_extra 默认 2 即亮红灯）
2. 扫描主仓同级目录与项目配置的 extra_roots，揪出已脱离 git worktree 但残留在磁盘的 `<repo>-*` 孤儿目录
3. 揪出 prunable（目录已删但 `.git/worktrees` 残留元数据）的僵尸项
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _norm_key(p: Path) -> str:
    try:
        return str(p.resolve()).replace("\\", "/").rstrip("/").lower()
    except OSError:
        return str(p).replace("\\", "/").rstrip("/").lower()


def parse_worktree_porcelain(output: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            if cur:
                entries.append(cur)
                cur = None
            continue
        if line.startswith("worktree "):
            if cur:
                entries.append(cur)
            cur = {
                "path": line[len("worktree "):].strip().replace("\\", "/"),
                "head": "",
                "branch": "",
                "detached": False,
                "prunable": False,
                "bare": False,
            }
        elif cur is not None:
            if line.startswith("HEAD "):
                cur["head"] = line[5:].strip()[:10]
            elif line.startswith("branch "):
                b = line[7:].strip()
                cur["branch"] = b[len("refs/heads/"):] if b.startswith("refs/heads/") else b
            elif line == "detached":
                cur["detached"] = True
            elif line.startswith("prunable"):
                cur["prunable"] = True
            elif line == "bare":
                cur["bare"] = True
    if cur:
        entries.append(cur)
    return entries


def evaluate_worktrees(
    main_root: Path,
    registered: list[dict[str, Any]],
    *,
    extra_roots: list[Path] | None = None,
    max_extra: int = 2,
    prefix: str | None = None,
) -> dict[str, Any]:
    main_resolved = main_root.resolve()
    main_key = _norm_key(main_resolved)
    repo_prefix = (prefix or main_resolved.name).lower() + "-"

    reg_keys = {_norm_key(Path(e["path"])) for e in registered}
    extra_registered = [e for e in registered if _norm_key(Path(e["path"])) != main_key]
    prunable = [e for e in extra_registered if e.get("prunable")]

    scan_roots: list[Path] = []
    seen_roots: set[str] = set()
    for candidate in [main_resolved.parent, *(extra_roots or [])]:
        k = _norm_key(candidate)
        if k not in seen_roots:
            seen_roots.add(k)
            scan_roots.append(candidate)

    orphan_dirs: list[str] = []
    for base in scan_roots:
        if not base.is_dir():
            continue
        try:
            children = sorted(base.iterdir(), key=lambda x: x.name.lower())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if not child.name.lower().startswith(repo_prefix):
                continue
            ck = _norm_key(child)
            if ck == main_key or ck in reg_keys:
                continue
            orphan_dirs.append(str(child).replace("\\", "/"))

    triggers: list[str] = []
    if len(extra_registered) > max_extra:
        triggers.append(
            f"额外 worktree 数量超上限：{len(extra_registered)} 个 > 上限 {max_extra} 个"
            "（禁止新建第 3 个，请复用固定槽位或先 `git worktree remove` 清理旧槽）"
        )
    if orphan_dirs:
        triggers.append(
            f"发现 {len(orphan_dirs)} 个脱离 git worktree 的残留目录（请核对后彻底删除顶层目录，防止残留缓存/空壳）："
            + ", ".join(orphan_dirs)
        )
    if prunable:
        triggers.append(
            f"发现 {len(prunable)} 条僵尸 worktree 元数据（请运行 `git worktree prune`）："
            + ", ".join(e["path"] for e in prunable)
        )

    return {
        "status": "red" if triggers else "green",
        "main_root": str(main_resolved).replace("\\", "/"),
        "max_extra": max_extra,
        "extra_worktrees": extra_registered,
        "orphan_dirs": orphan_dirs,
        "prunable": prunable,
        "triggers": triggers,
    }


def run_worktree_guard(
    root: Path,
    *,
    max_extra: int = 2,
    extra_roots: list[str] | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "worktree", "list", "--porcelain"],
        cwd=root.resolve(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git worktree list failed (exit {proc.returncode})")
    registered = parse_worktree_porcelain(proc.stdout)
    main_root = Path(registered[0]["path"]) if registered else root.resolve()
    roots = [Path(r) for r in (extra_roots or [])]
    return evaluate_worktrees(
        main_root,
        registered,
        extra_roots=roots,
        max_extra=max_extra,
        prefix=prefix,
    )
