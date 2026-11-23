"""零 LLM、有界深度的仓库结构扫描器，供 `harness init --agent codex` 与 Agent 自助接入使用。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# 扫描时一律跳过的大体积/构建/缓存目录，确保 Unity / 大型工程也能毫秒级完成
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".harness",
        ".claude",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "Library",
        "Temp",
        "Obj",
        "Logs",
        "Build",
        "Builds",
        "Work_Local",
        ".ui_pipeline",
        "HybridCLRData",
        "ExtAssets",
        "GeneratedLocalRepo",
        "BuildTarget",
        "dist",
        "target",
        ".pytest_cache",
        ".mypy_cache",
    }
)

SCRIPT_EXTS: frozenset[str] = frozenset({".ps1", ".bat", ".cmd", ".sh"})
BUILD_KEYWORDS = ("build", "pack", "package", "apk", "release")
VERIFY_KEYWORDS = ("verify", "test", "check", "lint", "parity", "audit")
EXPORT_KEYWORDS = ("export", "excel", "config", "gen")


def _rel_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _detect_unity_roots(root: Path, max_depth: int = 3) -> list[str]:
    """寻找含 Assets/ 和 ProjectSettings/ 的 Unity 工程根目录。"""
    found: list[str] = []
    root = root.resolve()

    def _walk(cur: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(cur.iterdir())
        except OSError:
            return
        names = {e.name for e in entries if e.is_dir()}
        if "Assets" in names and "ProjectSettings" in names:
            rel = _rel_posix(cur, root)
            found.append("." if rel == "" else rel)
            return  # 不再钻进 Unity 工程内部找嵌套
        for e in sorted(entries, key=lambda p: p.name.lower()):
            if e.is_dir() and e.name not in SKIP_DIRS and not e.name.startswith("."):
                _walk(e, depth + 1)

    _walk(root, 0)
    return found


def _scan_scripts(root: Path, max_depth: int = 3) -> dict[str, list[str]]:
    """有界深度扫描常见构建/验证/导出脚本。"""
    build: list[str] = []
    verify: list[str] = []
    export: list[str] = []

    root = root.resolve()
    root_depth = len(root.parts)

    for dirpath, dirnames, filenames in os.walk(root):
        cur = Path(dirpath)
        depth = len(cur.parts) - root_depth
        # 原地剪枝
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") and depth < max_depth
        )
        for fname in sorted(filenames):
            fpath = cur / fname
            ext = fpath.suffix.lower()
            if ext not in SCRIPT_EXTS:
                continue
            low = fname.lower()
            rel = _rel_posix(fpath, root)
            if any(k in low for k in VERIFY_KEYWORDS):
                verify.append(rel)
            elif any(k in low for k in BUILD_KEYWORDS):
                build.append(rel)
            elif any(k in low for k in EXPORT_KEYWORDS):
                export.append(rel)

    return {
        "build": build[:10],
        "verify": verify[:10],
        "export": export[:6],
    }


def _detect_types(root: Path, unity_roots: list[str]) -> list[str]:
    types: list[str] = []
    if unity_roots:
        types.append("unity")
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "requirements.txt").exists():
        types.append("python")
    if (root / "package.json").exists():
        types.append("node")
    if (root / "Cargo.toml").exists():
        types.append("rust")
    if (root / "go.mod").exists():
        types.append("go")
    if (root / "pubspec.yaml").exists():
        types.append("dart")
    if (root / "server").is_dir() or (root / "CMakeLists.txt").exists():
        # 检查是否有 lua / cpp 迹象（浅层）
        for sub in (root / "server", root / "src", root):
            if not sub.is_dir():
                continue
            try:
                children = list(sub.iterdir())
            except OSError:
                continue
            if any(c.suffix.lower() == ".lua" or "lua" in c.name.lower() for c in children):
                if "lua" not in types:
                    types.append("lua")
            if any(c.suffix.lower() in {".cpp", ".h", ".hpp"} or c.name == "CMakeLists.txt" for c in children):
                if "cpp" not in types:
                    types.append("cpp")
    return types


def _detect_docs(root: Path) -> list[str]:
    docs: list[str] = []
    for name in ("README.md", "AGENTS.md", "CLAUDE.md", "HANDOFF.md"):
        if (root / name).is_file():
            docs.append(name)
    for dname in ("01_Docs", "doc", "docs"):
        if (root / dname).is_dir():
            docs.append(f"{dname}/")
    return docs


def inspect_project(root: Path) -> dict[str, Any]:
    """扫描项目并返回适合人类阅读与 Agent 直接消费的结构化摘要。"""
    root = root.resolve()
    unity_roots = _detect_unity_roots(root)
    types = _detect_types(root, unity_roots)
    scripts = _scan_scripts(root)
    docs = _detect_docs(root)

    agents_path = root / "AGENTS.md"
    agents_exists = agents_path.is_file()
    agents_lines = (
        len(agents_path.read_text(encoding="utf-8", errors="replace").splitlines())
        if agents_exists
        else 0
    )

    cfg_path = root / ".harness" / "config.yaml"

    return {
        "project": root.name,
        "root": root.as_posix(),
        "types": types,
        "unity_roots": unity_roots,
        "docs": docs,
        "scripts": scripts,
        "existing_agents_md": {
            "exists": agents_exists,
            "path": "AGENTS.md",
            "line_count": agents_lines,
        },
        "existing_config": {
            "exists": cfg_path.is_file(),
            "path": ".harness/config.yaml",
        },
    }
