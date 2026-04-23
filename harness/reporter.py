"""报告生成：双输出（人话 markdown + AI 紧凑 XML），带哈希的 check JSON。

设计要点：
- 人话版：markdown，有 emoji，给用户读
- AI 版：XML 紧凑，无冗余，给 AI 解析
- check JSON：带内容哈希，用于 gate 验真。Claude 无法伪造（哈希对不上）
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "warn", "skip"]


@dataclass
class CheckResult:
    """单个 check 的结果"""
    check_name: str
    target: str
    status: CheckStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass
class ValidationReport:
    """一次 harness check 的完整报告"""
    session_id: str
    timestamp: float
    project: str
    trigger: str  # "manual" | "on_edit:<file>" | "gate" | ...
    results: list[CheckResult] = field(default_factory=list)

    @property
    def all_green(self) -> bool:
        return all(r.status in ("pass", "warn", "skip") for r in self.results) and any(
            r.status == "pass" for r in self.results
        )

    @property
    def has_failures(self) -> bool:
        return any(r.status == "fail" for r in self.results)


# ════════════════════════════════════════════════════════════════════
# 生成器
# ════════════════════════════════════════════════════════════════════


def make_session_id() -> str:
    """短会话 id：基于时间戳，够唯一且人眼可辨"""
    return f"{int(time.time() * 1000):x}"


def content_hash(data: str) -> str:
    """SHA-256 前 16 位，够用"""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def render_markdown(report: ValidationReport) -> str:
    """人话 markdown"""
    lines = [
        f"# Harness Check Report",
        f"",
        f"- **Session**: `{report.session_id}`",
        f"- **Project**: {report.project}",
        f"- **Trigger**: {report.trigger}",
        f"- **Time**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}",
        f"- **Overall**: {'✅ ALL GREEN' if report.all_green else '❌ HAS FAILURES' if report.has_failures else '⚠️ WARNINGS'}",
        f"",
        f"## Results",
        f"",
    ]
    for r in report.results:
        icon = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}[r.status]
        lines.append(f"### {icon} [{r.target}] {r.check_name}")
        lines.append(f"- Status: **{r.status}**")
        if r.message:
            lines.append(f"- Message: {r.message}")
        if r.duration_ms:
            lines.append(f"- Duration: {r.duration_ms} ms")
        if r.details:
            lines.append(f"- Details:")
            lines.append("```")
            lines.append(json.dumps(r.details, indent=2, ensure_ascii=False))
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def render_xml_compact(report: ValidationReport) -> str:
    """AI 紧凑 XML。无缩进节省 token，标签语义明确。"""
    parts = [
        f'<validation_report session_id="{report.session_id}" '
        f'timestamp="{int(report.timestamp)}" '
        f'all_green="{str(report.all_green).lower()}">'
    ]
    # 按 target 分组
    by_target: dict[str, list[CheckResult]] = {}
    for r in report.results:
        by_target.setdefault(r.target, []).append(r)
    for target_name, results in by_target.items():
        parts.append(f'<target name="{_xml_escape(target_name)}">')
        for r in results:
            parts.append(f'<check name="{_xml_escape(r.check_name)}" status="{r.status}">')
            if r.message:
                parts.append(f"<msg>{_xml_escape(r.message)}</msg>")
            for k, v in r.details.items():
                parts.append(f'<d k="{_xml_escape(k)}">{_xml_escape(str(v))}</d>')
            parts.append("</check>")
        parts.append("</target>")
    # next_action 提示 AI
    if report.all_green:
        parts.append("<next_action>all_green</next_action>")
    elif report.has_failures:
        parts.append("<next_action>fix_failures</next_action>")
    else:
        parts.append("<next_action>review_warnings</next_action>")
    parts.append("</validation_report>")
    return "".join(parts)


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def save_check_json(report: ValidationReport, reports_dir: Path) -> Path:
    """保存 check 报告为 JSON（带内容哈希，防伪造）"""
    reports_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "session_id": report.session_id,
        "timestamp": report.timestamp,
        "project": report.project,
        "trigger": report.trigger,
        "all_green": report.all_green,
        "has_failures": report.has_failures,
        "results": [asdict(r) for r in report.results],
    }
    body_str = json.dumps(body, sort_keys=True, ensure_ascii=False)
    h = content_hash(body_str)
    body["content_hash"] = h
    filename = f"check_{report.session_id}_{h}.json"
    out = reports_dir / filename
    with out.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    return out


def save_markdown(report: ValidationReport, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"evidence_{report.session_id}.md"
    with out.open("w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return out
