"""从改动文件找相关测试文件。

启发式规则（按优先级匹配）：
1. 改 test 文件本身 → 就测它
2. 改 `app/foo.py` → 找 `tests/test_foo.py` 或 `tests/**/test_foo.py`
3. 改 `package/module.py` → 找 `tests/**/test_module.py`
4. 都没找到 → 返回空（调用方决定是否全量跑）
"""
from __future__ import annotations

from pathlib import Path


def is_test_file(path: str) -> bool:
    """pytest 约定：test_xxx.py 或 xxx_test.py"""
    name = Path(path).name
    return (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py")


def find_related_test_files(
    changed_file: str,
    target_config: dict,
    project_root: Path,
) -> list[str]:
    """
    target_config 里读 test_paths（默认 ["tests"]）。
    返回相对于 project_root 的 POSIX 路径列表。
    """
    changed = Path(changed_file)
    rel_changed = changed if not changed.is_absolute() else changed.relative_to(project_root)

    # 规则 1：test 文件本身
    if is_test_file(str(rel_changed)):
        return [str(rel_changed).replace("\\", "/")]

    test_paths = target_config.get("test_paths", ["tests"])
    module_name = rel_changed.stem  # "prompt_builder"
    target_name = f"test_{module_name}.py"

    found: list[str] = []
    for tp in test_paths:
        tp_abs = project_root / tp
        if not tp_abs.exists():
            continue
        for path in tp_abs.rglob(target_name):
            rel = path.relative_to(project_root)
            found.append(str(rel).replace("\\", "/"))
    return found
