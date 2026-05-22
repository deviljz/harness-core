"""从改动 .cs 文件找相关 Unity 测试文件。

Unity Test Framework 约定（基于 asmdef）：
- 每个 asmdef 模块可以有同 root 下的 Tests/ 子目录（含 Editor/ Runtime/ 子分类）
- 测试文件命名约定：FooTests.cs 或 Foo_Test.cs

启发式规则（按优先级）：
1. 改的是 *Tests.cs / *_Test.cs → 就测它本身
2. 改 `Packages/<pkg>/Runtime/Foo.cs` → 找 `Packages/<pkg>/Tests/Editor|Runtime/FooTests.cs`
3. 改 `Assets/Scripts/.../Foo.cs` → 找 `Assets/Tests/.../FooTests.cs` 或 `Assets/Scripts/.../Editor/FooTests.cs`
4. 反向 grep 「class FooTests」找其它命名约定外的测试
5. 都没找到 → 返回空（runner 决定是否全量跑）
"""
from __future__ import annotations

import re
from pathlib import Path


_TEST_FILE_PATTERN = re.compile(r".*(Tests?|_Test)\.cs$", re.IGNORECASE)


def is_test_file(path: str) -> bool:
    """Unity Test Framework 命名约定：FooTests.cs / FooTest.cs / Foo_Test.cs"""
    name = Path(path).name
    return bool(_TEST_FILE_PATTERN.match(name))


def find_related_test_files(
    changed_file: str,
    target_config: dict,
    project_root: Path,
) -> list[str]:
    """
    target_config 里读 test_paths（Unity 默认 ["Assets/Tests", "Packages/*/Tests"]）。
    返回相对于 project_root 的 POSIX 路径列表。
    """
    changed = Path(changed_file)
    try:
        rel_changed = changed if not changed.is_absolute() else changed.relative_to(project_root)
    except ValueError:
        # changed_file 不在 project_root 内 → 不是这个 target 的文件
        return []

    # 规则 1：test 文件本身
    if is_test_file(str(rel_changed)):
        return [str(rel_changed).replace("\\", "/")]

    # 不是 .cs 文件直接跳过
    if rel_changed.suffix.lower() != ".cs":
        return []

    module_name = rel_changed.stem  # "Foo"
    candidates = [f"{module_name}Tests.cs", f"{module_name}Test.cs", f"{module_name}_Test.cs"]

    test_paths = target_config.get("test_paths") or _default_test_paths()
    found: list[str] = []

    for tp in test_paths:
        tp_abs = project_root / tp if not Path(tp).is_absolute() else Path(tp)
        # 支持 glob：Packages/*/Tests
        if "*" in str(tp):
            roots = list(project_root.glob(tp))
        else:
            roots = [tp_abs] if tp_abs.exists() else []
        for root in roots:
            if not root.exists():
                continue
            for cand in candidates:
                for path in root.rglob(cand):
                    rel = path.relative_to(project_root)
                    found.append(str(rel).replace("\\", "/"))

    # 规则 4：反向 grep `class FooTests` 找命名约定外的测试
    # （仅在前面没找到时做，避免每次扫全工程）
    if not found:
        class_decl = re.compile(rf"class\s+{re.escape(module_name)}Tests?\b")
        for tp in test_paths:
            roots = list(project_root.glob(tp)) if "*" in str(tp) else [project_root / tp]
            for root in roots:
                if not root.exists():
                    continue
                for cs in root.rglob("*.cs"):
                    try:
                        content = cs.read_text(encoding="utf-8", errors="replace")
                        if class_decl.search(content):
                            rel = cs.relative_to(project_root)
                            found.append(str(rel).replace("\\", "/"))
                    except OSError:
                        pass

    return sorted(set(found))


def _default_test_paths() -> list[str]:
    """Unity 项目默认测试路径（含 glob）"""
    return [
        "Assets/Tests",
        "Packages/*/Tests",
        # asmdef 同 root 下的 Tests 子目录是 Unity 主流惯例
    ]
