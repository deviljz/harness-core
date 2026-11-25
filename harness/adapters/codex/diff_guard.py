"""改动预算硬闸门（`python -m harness diff-guard`）：防止 AI 修小 bug 时悄悄大改机制、动核心枢纽文件或打出巨无霸提交。

检查逻辑（毫秒级，只读 git diff --numstat）：
- 将改动拆成「运行代码」与「测试/文档/工具」两组，分别统计文件数与净增行数
- 减法友好：净增行数 = added - deleted（靠删旧补丁修 bug 不会触发超限）
- 任一条件越界即亮红灯（exit 2）：
  1. 运行代码文件数 > max_runtime_files（默认 3）
  2. 运行代码净增行数 > max_net_added_lines（默认 80）
  3. 触及项目配置的高危核心枢纽文件 hub_files（需先亮红灯与用户对齐方向）
"""
from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

RUNTIME_EXTS: frozenset[str] = frozenset(
    {
        ".cs",
        ".lua",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".dart",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".swift",
    }
)

NON_RUNTIME_PATH_PATTERNS: tuple[str, ...] = (
    "doc/**",
    "docs/**",
    "01_Docs/**",
    "tools/**",
    "reports/**",
    ".harness/**",
    "tests/**",
    "**/Editor/**",
    "**/Tests/**",
    "**/test_*.py",
    "**/*_test.py",
    "**/*Test.cs",
    "**/*Tests.cs",
)


def _match_any(rel_posix: str, patterns: list[str] | tuple[str, ...]) -> bool:
    rel = rel_posix.replace("\\", "/")
    low = rel.lower()
    for pat in patterns:
        p = pat.replace("\\", "/").lower()
        if fnmatch.fnmatch(low, p):
            return True
        if p.endswith("/**"):
            prefix = p[:-3]
            if low == prefix or low.startswith(prefix + "/"):
                return True
        if "/**/" in p and fnmatch.fnmatch(low, p.replace("/**/", "/")):
            return True
        # 允许在 hub_files 里只写文件名（如 LocalPlayBridge.cs）或路径后缀
        if "/" not in p and low.endswith("/" + p) or low == p:
            return True
    return False


def _is_runtime_code(rel_posix: str, extra_ignore: list[str]) -> bool:
    ext = Path(rel_posix).suffix.lower()
    if ext not in RUNTIME_EXTS:
        return False
    if _match_any(rel_posix, NON_RUNTIME_PATH_PATTERNS):
        return False
    if extra_ignore and _match_any(rel_posix, extra_ignore):
        return False
    return True


def parse_numstat(numstat_output: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in numstat_output.splitlines():
        parts = raw.split("\t")
        if len(parts) != 3:
            continue
        a_str, d_str, path = parts
        added = int(a_str) if a_str.isdigit() else 0
        deleted = int(d_str) if d_str.isdigit() else 0
        entries.append(
            {
                "file": path.strip().replace("\\", "/"),
                "added": added,
                "deleted": deleted,
                "net": added - deleted,
                "binary": not (a_str.isdigit() and d_str.isdigit()),
            }
        )
    return entries


def evaluate_diff_entries(
    entries: list[dict[str, Any]],
    *,
    max_runtime_files: int = 3,
    max_net_added_lines: int = 80,
    hub_files: list[str] | None = None,
    extra_ignore: list[str] | None = None,
) -> dict[str, Any]:
    hubs = hub_files or []
    ignores = extra_ignore or []

    runtime_entries: list[dict[str, Any]] = []
    other_entries: list[dict[str, Any]] = []
    touched_hubs: list[dict[str, Any]] = []

    for e in entries:
        fp = e["file"]
        if _is_runtime_code(fp, ignores):
            runtime_entries.append(e)
            if hubs and _match_any(fp, hubs):
                touched_hubs.append(e)
        else:
            other_entries.append(e)

    rt_added = sum(e["added"] for e in runtime_entries)
    rt_deleted = sum(e["deleted"] for e in runtime_entries)
    rt_net = rt_added - rt_deleted

    other_added = sum(e["added"] for e in other_entries)
    other_deleted = sum(e["deleted"] for e in other_entries)

    triggers: list[str] = []
    if len(runtime_entries) > max_runtime_files:
        triggers.append(
            f"运行代码文件数超预算：{len(runtime_entries)} 个 > 上限 {max_runtime_files} 个（请拆小或先亮红灯请示）"
        )
    if rt_net > max_net_added_lines:
        triggers.append(
            f"运行代码净增行数超预算：+{rt_net} 行（+{rt_added}/-{rt_deleted}）> 上限 +{max_net_added_lines} 行"
        )
    if touched_hubs:
        names = ", ".join(f"{e['file']}(+{e['added']}/-{e['deleted']})" for e in touched_hubs)
        triggers.append(f"触及高危核心枢纽文件：{names}（改公共状态流转前须先给 5 行方向卡请示）")

    return {
        "status": "red" if triggers else "green",
        "triggers": triggers,
        "budget": {
            "max_runtime_files": max_runtime_files,
            "max_net_added_lines": max_net_added_lines,
            "hub_files": hubs,
        },
        "runtime": {
            "files_count": len(runtime_entries),
            "added": rt_added,
            "deleted": rt_deleted,
            "net": rt_net,
            "files": runtime_entries,
        },
        "non_runtime": {
            "files_count": len(other_entries),
            "added": other_added,
            "deleted": other_deleted,
        },
        "touched_hubs": [e["file"] for e in touched_hubs],
    }


def run_diff_guard(
    root: Path,
    *,
    base: str = "HEAD",
    staged: bool = False,
    max_runtime_files: int = 3,
    max_net_added_lines: int = 80,
    hub_files: list[str] | None = None,
    extra_ignore: list[str] | None = None,
) -> dict[str, Any]:
    cmd = ["git", "-c", "core.quotepath=false", "diff", "--numstat"]
    if staged:
        cmd.append("--cached")
    else:
        cmd.append(base)
    proc = subprocess.run(
        cmd,
        cwd=root.resolve(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git diff failed (exit {proc.returncode})")
    entries = parse_numstat(proc.stdout)
    res = evaluate_diff_entries(
        entries,
        max_runtime_files=max_runtime_files,
        max_net_added_lines=max_net_added_lines,
        hub_files=hub_files,
        extra_ignore=extra_ignore,
    )
    res["scope"] = "--cached" if staged else f"diff {base}"
    return res
