"""路径 → target 路由。

职责：
1. 跨平台规范化（Windows 反斜杠 → 正斜杠，大小写不敏感）
2. 全局 ignore + 每 target 的 ignore 匹配
3. 按 target.root 判断改动属于哪个 target

关键约束（见 spec 架构约束 7）：
- 强制用 PurePosixPath，禁止 os.path.sep 或硬编码 "/"
- Windows 下大小写不敏感比较
"""
from __future__ import annotations

import fnmatch
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .config import HarnessConfig, TargetConfig


# ════════════════════════════════════════════════════════════════════
# 路径规范化工具
# ════════════════════════════════════════════════════════════════════


_IS_WINDOWS = sys.platform == "win32"


def normalize_path(p: str | Path) -> str:
    """统一成 POSIX 风格字符串。Windows 下额外转小写供比较。

    返回值供**比较/匹配**使用。原路径请另行保存（比如要打开文件）。
    """
    pp = PurePosixPath(str(p).replace("\\", "/"))
    # 去除 ./ 前缀
    s = str(pp)
    if s.startswith("./"):
        s = s[2:]
    if _IS_WINDOWS:
        s = s.lower()
    return s


def relative_to_project(path: str | Path, project_root: Path) -> str:
    """把绝对路径/相对路径转成相对于 project_root 的 POSIX 字符串"""
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.relative_to(project_root)
        except ValueError:
            # 不在 project_root 下，保留原样
            pass
    return normalize_path(p)


def match_glob(path: str, pattern: str) -> bool:
    """glob 匹配。path 已经是 normalize_path 的结果。

    pattern 也会先被 normalize，支持 "**/*.py" / "build/**" 这类 glob。
    """
    norm_pattern = normalize_path(pattern)
    # fnmatch 不原生支持 "**"，手动展开：把 "**" 当 "任意深度目录" 处理
    # 简化实现：用 fnmatch 对路径各段匹配
    return _glob_match(path, norm_pattern)


def _glob_match(path: str, pattern: str) -> bool:
    """自实现 glob 匹配，支持 **。"""
    path_parts = path.split("/")
    pat_parts = pattern.split("/")
    return _match_parts(path_parts, pat_parts)


def _match_parts(path: list[str], pat: list[str]) -> bool:
    if not pat:
        return not path
    head, *rest = pat
    if head == "**":
        # ** 匹配任意多段（含 0）
        if not rest:
            return True
        # 尝试让 ** 吃 0..n 段
        for i in range(len(path) + 1):
            if _match_parts(path[i:], rest):
                return True
        return False
    if not path:
        return False
    if fnmatch.fnmatchcase(path[0], head):
        return _match_parts(path[1:], rest)
    return False


# ════════════════════════════════════════════════════════════════════
# 路由逻辑
# ════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RouteResult:
    """路由决策结果"""
    ignored: bool
    ignore_reason: str = ""
    matched_targets: tuple[str, ...] = ()


def is_ignored(
    rel_path: str,
    config: HarnessConfig,
    target: TargetConfig | None = None,
) -> tuple[bool, str]:
    """判断 rel_path（已 normalize）是否被 ignore。

    全局 ignore 优先匹配；target 指定则再查 target.ignore_paths。
    """
    for pat in config.ignore_paths_global:
        if match_glob(rel_path, pat):
            return True, f"global:{pat}"
    if target:
        for pat in target.ignore_paths:
            if match_glob(rel_path, pat):
                return True, f"target[{target.name}]:{pat}"
    return False, ""


def route_file(
    file_path: str | Path,
    config: HarnessConfig,
    project_root: Path,
) -> RouteResult:
    """给一个改动文件路径，决定触发哪些 target。

    - 全局 ignore 命中 → ignored
    - 否则，对每个 target：检查 target.root 是否是 file 路径前缀；若是，再查 target.ignore_paths
    - 可能命中 0 或多个 target
    """
    rel = relative_to_project(file_path, project_root)

    # 1. 全局 ignore 早退
    ignored, reason = is_ignored(rel, config)
    if ignored:
        return RouteResult(ignored=True, ignore_reason=reason)

    matched: list[str] = []
    for target in config.targets:
        root_norm = normalize_path(target.root).rstrip("/")
        # "." 或 "" 表示整个项目根 → 匹配所有文件
        if root_norm in ("", "."):
            target_matches = True
        else:
            prefix = root_norm + "/"
            target_matches = rel == root_norm or rel.startswith(prefix)

        if target_matches:
            ig, _reason = is_ignored(rel, config, target)
            if ig:
                continue
            matched.append(target.name)

    return RouteResult(ignored=False, matched_targets=tuple(matched))
