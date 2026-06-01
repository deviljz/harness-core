"""Review 层 runner：调 LLM provider，解析 JSON 响应"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..llm import LLMProvider
from .diff_packager import package_diff


@dataclass
class ReviewResult:
    consistent: bool
    issues: list[str] = field(default_factory=list)
    raw_response: str = ""
    error: str | None = None


def _load_template() -> str:
    here = Path(__file__).parent
    return (here / "prompt_template.md").read_text(encoding="utf-8")


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复里抠 JSON（可能包在 ```json 里）"""
    # 先试直接 parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 再试 code fence 内
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    # 再试裸 JSON 对象
    m = re.search(r"\{[^{}]*\"consistent\"[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def build_review_prompt(
    project_root: Path,
    spec_path: Path | None,
    *,
    focus: str = "api_contract, error_handling",
    diff_base: str = "HEAD",
) -> str | None:
    """打包 diff+spec 填模板，返回 review prompt。空 diff 返 None。

    供非轮询两步模式（--emit-prompt）和 run_review 共用。
    """
    packed = package_diff(project_root, spec_path, diff_base=diff_base)
    if not packed["diff_content"].strip():
        return None
    template = _load_template()
    return template.format(
        spec_content=packed["spec_content"] or "(no spec provided)",
        diff_content=packed["diff_content"],
        focus=focus,
    )


def parse_review_response(response: str) -> ReviewResult:
    """把外部 AI 回的文本解析成 ReviewResult（裸 JSON / ```json``` 均可）。

    供非轮询 --response-file 模式和 run_review 共用。
    """
    data = _extract_json(response)
    if data is None:
        return ReviewResult(
            consistent=False,
            issues=["LLM response could not be parsed as JSON"],
            raw_response=response[:2000],
            error="parse_error",
        )
    return ReviewResult(
        consistent=bool(data.get("consistent", False)),
        issues=list(data.get("issues", [])),
        raw_response=response[:2000],
    )


def run_review(
    provider: LLMProvider,
    project_root: Path,
    spec_path: Path | None,
    *,
    focus: str = "api_contract, error_handling",
    diff_base: str = "HEAD",
) -> ReviewResult:
    """跑一次 review：打包 → 填模板 → 调 provider.complete → 解析 JSON。"""
    prompt = build_review_prompt(project_root, spec_path, focus=focus, diff_base=diff_base)
    if prompt is None:
        return ReviewResult(consistent=True, issues=[], error="empty diff, nothing to review")

    try:
        response = provider.complete(prompt)
    except Exception as e:
        return ReviewResult(consistent=False, issues=[], error=f"LLM call failed: {e}")

    return parse_review_response(response)
