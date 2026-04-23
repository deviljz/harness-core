"""方案层：spec 模板生成 + 校验"""
from __future__ import annotations

from .template import DEFAULT_SPEC_TEMPLATE, render_template
from .validator import ValidationIssue, validate_spec

__all__ = [
    "DEFAULT_SPEC_TEMPLATE",
    "render_template",
    "ValidationIssue",
    "validate_spec",
]
