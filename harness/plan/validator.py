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

    # 5. §6 Testing 必须含交互性测试关键词，否则 warn
    # 防止 "selector count / typeof 只测存在性" → smoke 全绿但功能 100% 坏
    testing_match = re.search(
        r"^##\s+(?:\d+\.\s+)?Testing(.*?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if testing_match:
        testing_body = testing_match.group(1)
        interaction_markers = [
            "dispatchEvent",
            "fireEvent",
            "page.click",
            "page.tap",
            "simulate.click",
            "tester.tap",
            "find.byIcon",
            "find.byTooltip",
            "userEvent.",
            "await tester",
            "MouseEvent",
            "TouchEvent",
            "KeyboardEvent",
            "click(",
        ]
        if not any(m in testing_body for m in interaction_markers):
            issues.append(
                ValidationIssue(
                    "warning",
                    "Testing 段未发现交互性测试关键词（dispatchEvent / page.click / "
                    "tester.tap / fireEvent / find.byIcon 等）。spec §6 三类测试规则要求"
                    "至少 1 条交互性测试，否则 'selector 存在但 handler 没绑' 类 bug 抓不到。",
                )
            )

        # 6. 若涉及异步操作 + UI，检查是否有"时序竞态"测试
        # 关键词识别：spec 全文出现 upload / async / await / loading 同时含 button / 按钮 / 提交
        full_lower = content.lower()
        async_markers = ["upload", "async", "await ", "loading", "异步", "上传", "submit"]
        ui_markers = ["button", "按钮", "提交", "点击", "click", "tap"]
        has_async = any(m in full_lower for m in async_markers)
        has_ui = any(m in full_lower for m in ui_markers)
        if has_async and has_ui:
            race_markers = [
                "toBeDisabled",
                "isDisabled",
                "toHaveAttribute('disabled'",
                "isNull.*onPressed",
                "LoadingIndicator",
                "竞态",
                "race",
                "disable.*loading",
                "_busy",
                "_uploading",
            ]
            if not any(m in testing_body for m in race_markers):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Testing 段涉及异步操作 + UI 按钮但未发现时序竞态测试关键词"
                        "（toBeDisabled / LoadingIndicator / _busy 等）。"
                        "spec §6 四类测试要求至少 1 条时序竞态测试，否则用户在 "
                        "9 图上传 10-30s 期间反复点提交导致 race / 重复 draft 类 bug 抓不到。",
                    )
                )

        # 7. 状态累积（涉及重试/失败恢复时必须测连续 N 轮不累积）
        # 来源：2026-06 选图打卡失败重试缩略图翻倍 1→2→4——单次重试被掩盖，连续 N 轮才暴露
        retry_markers = ["重试", "retry", "失败恢复", "失败重试", "resetFailed"]
        if any(m in full_lower for m in [x.lower() for x in retry_markers]):
            accumulation_markers = [
                "累积", "连续", "n 轮", "n轮", "多轮", "不重复", "不翻倍",
                "invariant", "removewhere", "alreadypending", "去重",
            ]
            if not any(m in testing_body.lower() for m in accumulation_markers):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Testing 段涉及重试/失败恢复但未发现状态累积守卫关键词"
                        "（连续 N 轮 / 累积 / 不重复 / invariant 等）。"
                        "重试类必须测「失败→重试→再失败→再重试，断言状态不累积」——"
                        "单次重试看不出（2026-06 选图打卡重试缩略图翻倍 1→2→4 即此盲区）。",
                    )
                )

        # 8. 异步慢依赖中间态（涉及上传进度/乐观渲染时必须注入慢依赖断言中间态）
        # 来源：2026-06 选图打卡进度卡 100%——小图秒传把"100%→完成"空窗压成 0ms 掩盖
        midstate_trigger = ["进度", "progress", "乐观", "optimistic", "百分比", "loading"]
        if any(m in full_lower for m in [x.lower() for x in midstate_trigger]):
            slowdep_markers = [
                "慢依赖", "中间态", "延迟", "delay", "completer", "fake service",
                "fakeservice", "处理中", "未完成", "in-flight", "in flight", "stub",
            ]
            if not any(m in testing_body.lower() for m in slowdep_markers):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Testing 段涉及上传进度/乐观渲染但未发现慢依赖中间态测试关键词"
                        "（注入慢依赖 / Completer 延迟 / 处理中 / 中间态 等）。"
                        "异步进度类必须注入「慢依赖」(延迟 resolve 的 fake) 断言中间态——"
                        "100% ≠ 完成；用秒传/小图验证会把空窗压成 0ms 掩盖问题"
                        "（2026-06 选图打卡进度卡 100%+按钮转圈即此盲区）。",
                    )
                )

    return issues


def extract_complexity(spec_path: Path) -> str | None:
    """从 spec 抽出 complexity 字段值（供 execute 层用）"""
    if not spec_path.exists():
        return None
    content = spec_path.read_text(encoding="utf-8")
    m = re.search(r"\*\*complexity\*\*\s*:\s*(simple|complex)", content, re.IGNORECASE)
    return m.group(1).lower() if m else None
