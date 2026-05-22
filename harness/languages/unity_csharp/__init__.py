"""Unity C# 语言模块。

支持 Unity Test Framework (EditMode + PlayMode)，通过 `Unity.exe -batchmode -runTests` 跑。

核心坑（详见 Phase B baseline 文档 docs/unity_batchmode_baseline.md）：
- Editor 开着 + 同 projectPath → batchmode abort + exit 21 + crash dump。
  runner.run_tests 必须 pre-flight check Editor 锁，fail-fast。
"""
from __future__ import annotations

from .module import UnityCSharpModule

__all__ = ["UnityCSharpModule"]
