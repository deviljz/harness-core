"""spec 合规校验：检查 7 大区 + complexity 字段都存在"""
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

# 推荐但不强制的段（缺失时仅 warning，不阻塞 validate）。
# - User Flow: UI 类任务用户动线 trace，纯后端可写 N/A
# - Data Migration: 防止"加字段 + 按字段过滤但不回填"这类盲区
RECOMMENDED_SECTIONS = [
    "User Flow",
    "Data Migration",
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

    # 1. 必填段全在
    for section in REQUIRED_SECTIONS:
        # 接受 "## 1. Objective" / "## Objective" 两种
        pattern = rf"^##\s+(?:\d+\.\s+)?{re.escape(section)}"
        if not re.search(pattern, content, re.MULTILINE):
            issues.append(
                ValidationIssue("error", f"missing required section: {section}")
            )

    # 1b. 推荐段缺失 → warning（避免老 spec 突然 fail）
    for section in RECOMMENDED_SECTIONS:
        pattern = rf"^##\s+(?:\d+\.\s+)?{re.escape(section)}"
        if not re.search(pattern, content, re.MULTILINE):
            issues.append(
                ValidationIssue(
                    "warning",
                    f"missing recommended section: {section} "
                    f"（涉及持久化/数据存储变更时必须显式说明迁移策略，否则填 N/A）",
                )
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
