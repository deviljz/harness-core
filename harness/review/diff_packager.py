"""打包 diff + spec 片段，喂给 review agent"""
from __future__ import annotations

import subprocess
from pathlib import Path


def get_git_diff(project_root: Path, base: str = "HEAD") -> str:
    """取 git diff（工作区 vs HEAD）"""
    try:
        result = subprocess.run(
            ["git", "diff", base],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"(git diff failed: {e})"


def package_diff(
    project_root: Path,
    spec_path: Path | None = None,
    diff_base: str = "HEAD",
    max_diff_chars: int = 30000,
) -> dict:
    """返回 {spec_content, diff_content, summary}"""
    diff = get_git_diff(project_root, diff_base)
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + f"\n\n[diff truncated at {max_diff_chars} chars]"

    spec_content = ""
    if spec_path and spec_path.exists():
        spec_content = spec_path.read_text(encoding="utf-8")

    return {
        "spec_content": spec_content,
        "diff_content": diff,
        "diff_base": diff_base,
        "spec_path": str(spec_path) if spec_path else "",
    }
