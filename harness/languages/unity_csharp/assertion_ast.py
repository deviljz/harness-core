"""C# AST 静态检查占位。

Python 端没有 production-grade C# parser。要实做需要：
- 调 `dotnet` 子进程 + Roslyn analyzer 输出 sarif 格式
- 或集成 tree-sitter-c-sharp
- 或调 Mono.CSharp

当前空实现 — deep_check 返回 []，C# 项目的"卫生检查"完全靠 anti_patterns 正则（harness/validate 层）。

未来实现路径见：
- https://github.com/dotnet/roslyn-analyzers
- harness/languages/unity_csharp/README.md（待写）
"""
from __future__ import annotations

from pathlib import Path

from ..base import Issue


def check_test_file(path: Path) -> list[Issue]:
    """占位：当前不做 C# AST 检查。返回空 list。"""
    return []
