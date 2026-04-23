"""AST 查假测试（只做 tautology 检测，不卡 assert 数量）。

检查规则：
1. forbid_tautology: 禁止 `assert True`、`assert 1 == 1`、`assert 1`、`assert "x"`、无 assert 函数名以 test_ 开头
2. 空函数体（只有 pass / ...）且函数名 test_ 开头 → 标记
"""
from __future__ import annotations

import ast
from pathlib import Path

from ..base import Issue


def check_test_file(
    file_path: Path,
    rules: dict | None = None,
) -> list[Issue]:
    """对一个 test 文件跑 AST 检查。返回问题列表。

    rules 常见：
      - forbid_tautology: True
    """
    rules = rules or {"forbid_tautology": True}
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        return [
            Issue(
                severity="error",
                file=str(file_path),
                line=getattr(e, "lineno", None),
                rule="parse_error",
                message=f"cannot parse: {e}",
            )
        ]

    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        # 收集函数体里所有 Assert
        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        # 规则 1：完全没断言（且函数不是只有 pytest.raises 等上下文管理器）
        has_raises_ctx = _has_pytest_raises(node)
        if not asserts and not has_raises_ctx:
            issues.append(
                Issue(
                    severity="error",
                    file=str(file_path),
                    line=node.lineno,
                    rule="no_assertion",
                    message=f"test `{node.name}` has no assertion and no pytest.raises",
                )
            )
            continue

        # 规则 2：tautology
        if rules.get("forbid_tautology", True):
            for a in asserts:
                if _is_tautology(a.test):
                    issues.append(
                        Issue(
                            severity="error",
                            file=str(file_path),
                            line=a.lineno,
                            rule="forbid_tautology",
                            message=f"tautological assertion in `{node.name}`: {ast.unparse(a.test)[:80]}",
                        )
                    )

    return issues


def _is_tautology(expr: ast.expr) -> bool:
    """判断 assert 表达式是不是永真"""
    # assert True
    if isinstance(expr, ast.Constant) and expr.value is True:
        return True
    # assert 1, assert "x", assert non-zero literal
    if isinstance(expr, ast.Constant) and bool(expr.value) is True and not isinstance(expr.value, bool):
        return True
    # assert 1 == 1, assert "a" == "a"
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1:
        left = expr.left
        right = expr.comparators[0]
        op = expr.ops[0]
        if (
            isinstance(left, ast.Constant)
            and isinstance(right, ast.Constant)
            and isinstance(op, ast.Eq)
            and left.value == right.value
        ):
            return True
    # assert True == True / False == False
    if isinstance(expr, ast.NameConstant) if False else False:
        pass
    # assert x or True  → always true 右操作数是 True
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.Or):
        for v in expr.values:
            if isinstance(v, ast.Constant) and v.value is True:
                return True
    return False


def _has_pytest_raises(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """函数体里是否用到 pytest.raises 作为 with 上下文"""
    for node in ast.walk(func):
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    func_expr = ctx.func
                    if isinstance(func_expr, ast.Attribute) and func_expr.attr == "raises":
                        return True
    return False
