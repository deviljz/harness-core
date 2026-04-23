"""spec 合规校验：检查 6 大区 + complexity 字段都存在"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str


REQUIRED_SECTIONS = [
    "Objective",
    "Commands",
    "Structure",
    "Style",
    "Testing",
    "Boundaries",
]


def validate_spec(spec_path: Path) -> list[ValidationIssue]:
    """校验 spec 文档。返回问题列表（空 = 通过）"""
    if not spec_path.exists():
        return [ValidationIssue("error", f"spec file not found: {spec_path}")]

    try:
        content = spec_path.read_text(encoding="utf-8")
    except OSError as e:
        return [ValidationIssue("error", f"read error: {e}")]

    issues: list[ValidationIssue] = []

    # 1. 6 大区全在
    for section in REQUIRED_SECTIONS:
        # 接受 "## 1. Objective" / "## Objective" 两种
        pattern = rf"^##\s+(?:\d+\.\s+)?{re.escape(section)}"
        if not re.search(pattern, content, re.MULTILINE):
            issues.append(
                ValidationIssue("error", f"missing required section: {section}")
            )

    # 2. complexity 字段
    m = re.search(r"\*\*complexity\*\*\s*:\s*(simple|complex)", content, re.IGNORECASE)
    if not m:
        issues.append(
            ValidationIssue(
                "error",
                "missing `**complexity**: simple|complex` field (needed by execute layer)",
            )
        )

    # 3. Objective 里必须有"成功标准"
    # 简单用文本搜索
    if "成功标准" not in content and "Success criteria" not in content.lower():
        issues.append(
            ValidationIssue(
                "warning",
                "Objective section should mention 成功标准 / Success criteria for verifiability",
            )
        )

    # 4. 不能全是空模板（避免 AI 把没填的 spec 当完成的提交）
    stripped_len = len(content.replace(" ", "").replace("\n", ""))
    if stripped_len < 100:
        issues.append(
            ValidationIssue("error", "spec appears empty or minimal; please fill content")
        )

    return issues


def extract_complexity(spec_path: Path) -> str | None:
    """从 spec 抽出 complexity 字段值（供 execute 层用）"""
    if not spec_path.exists():
        return None
    content = spec_path.read_text(encoding="utf-8")
    m = re.search(r"\*\*complexity\*\*\s*:\s*(simple|complex)", content, re.IGNORECASE)
    return m.group(1).lower() if m else None
