"""6 大类断言实现（pure logic，不依赖 playwright）.

每个 assert_xxx 接收已采集的 DOM 数据快照 (dict / list)，返回 AssertionResult。
playwright DOM 抓取在 runner.py。这样断言可独立 unit test。
"""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    WARN = "warn"
    ERROR = "error"


@dataclass
class AssertionResult:
    assertion_id: str
    passed: bool
    severity: Severity = Severity.ERROR
    selector: str = ""
    actual: str = ""
    expected: str = ""
    remediation: str = ""
    note: str = ""

    @property
    def summary(self) -> str:
        if self.passed:
            return f"✓ {self.assertion_id} {self.selector}"
        return f"✗ {self.assertion_id} {self.selector}: {self.actual} (expected: {self.expected})"


# ============ A1-1: hover tooltip 不串入无关字段 ============


def assert_tooltip_no_unrelated(
    chart_id: str,
    tooltip_text: str,
    forbidden_keywords: list[str],
    allowed_for_chart: Optional[list[str]] = None,
) -> AssertionResult:
    """断言: chart hover tooltip 不含 forbidden_keywords 中的字段（除非该 chart 显式 allow）.

    Args:
        chart_id: chart SVG id
        tooltip_text: hover 后 tooltip innerText
        forbidden_keywords: 禁止出现的关键词
        allowed_for_chart: 该 chart 允许出现的关键词（如 chartFrameMs 可有 frameMs）
    """
    allowed = set(allowed_for_chart or [])
    violated = []
    for kw in forbidden_keywords:
        if kw in allowed:
            continue
        # 用 word boundary 匹配 frameMs=33 不匹配 frameMs 子串在其他 token 内
        pattern = re.escape(kw) + r"(?:\s*=|\s+\d)"
        if re.search(pattern, tooltip_text):
            violated.append(kw)
    if violated:
        return AssertionResult(
            assertion_id="A1-1",
            passed=False,
            selector=f"#{chart_id}",
            actual=f"tooltip 含 {', '.join(violated)} (text: {tooltip_text[:80]!r})",
            expected=f"不应含 {', '.join(forbidden_keywords)}",
            remediation="chart preset label='' + fmt 只输出当前曲线值；多线用 ● 同色 span",
        )
    return AssertionResult(assertion_id="A1-1", passed=True, selector=f"#{chart_id}")


# ============ A1-2: 非曲线图 mousemove 隐 global tooltip ============


def assert_non_chart_hides_tooltip(
    element_id: str,
    tooltip_display_after_hover: str,
) -> AssertionResult:
    """断言: 非曲线图（横条/堆叠/火焰）mousemove 后 #tooltip display=none.

    Args:
        element_id: 元素 id
        tooltip_display_after_hover: hover 后 #tooltip 的 getComputedStyle.display
    """
    # 'none' / 'hidden' / '' 都算不可见（不同浏览器/CSS 表现）
    if tooltip_display_after_hover in ("none", "hidden", "", None):
        return AssertionResult(assertion_id="A1-2", passed=True, selector=f"#{element_id}")
    return AssertionResult(
        assertion_id="A1-2",
        passed=False,
        selector=f"#{element_id}",
        actual=f"tooltip display={tooltip_display_after_hover!r}（残留前 chart 值）",
        expected="display='none'",
        remediation="渲染函数末尾 addEventListener('mousemove', () => tooltip.style.display='none')",
    )


# ============ A2-1: 颜色调色板限制 ============


def assert_color_palette(
    used_colors: dict[str, list[str]],  # {color_hex: [selectors_using_it]}
    allowed_palette: list[str],
    semantic_reserved: Optional[dict[str, list[str]]] = None,
    ignore_grayscale: bool = True,
) -> list[AssertionResult]:
    """断言: 所有 inline color/background/fill/stroke 必须属于 allowed_palette.

    semantic_reserved: {hex: [allowed-selectors]} 这些 hex 仅允许这些 selector
    ignore_grayscale: 灰阶色（#000-#fff 同 RGB）跳过
    """
    results: list[AssertionResult] = []
    allowed = {c.lower() for c in allowed_palette}
    semantic = {k.lower(): v for k, v in (semantic_reserved or {}).items()}

    for color, selectors in used_colors.items():
        c = color.lower()
        if ignore_grayscale and _is_grayscale(c):
            continue
        if c in allowed:
            continue
        if c in semantic:
            # 检查所有使用此色的 selector 是否在 allowed list
            allowed_sels = semantic[c]
            for sel in selectors:
                if not any(_selector_matches(sel, allowed_sel) for allowed_sel in allowed_sels):
                    results.append(AssertionResult(
                        assertion_id="A2-1",
                        passed=False,
                        selector=sel,
                        actual=f"语义保留色 {c} 用在非允许位置",
                        expected=f"{c} 仅允许 {allowed_sels}",
                        remediation=f"改用调色板色或限制 {c} 仅用在 {allowed_sels}",
                    ))
            continue
        # 完全不在 palette
        results.append(AssertionResult(
            assertion_id="A2-1",
            passed=False,
            selector=", ".join(selectors[:3]) + (" ..." if len(selectors) > 3 else ""),
            actual=f"用了非调色板色 {c}",
            expected=f"调色板: {allowed_palette}",
            remediation=f"用调色板内最接近色相替换 {c}",
        ))
    if not results:
        results.append(AssertionResult(assertion_id="A2-1", passed=True))
    return results


def _is_grayscale(hex_color: str) -> bool:
    h = hex_color.lstrip("#").lower()
    if len(h) == 3:
        return h[0] == h[1] == h[2]
    if len(h) == 6:
        return h[0:2] == h[2:4] == h[4:6]
    return False


def _selector_matches(sel: str, pattern: str) -> bool:
    # 简化：子串匹配（pattern 是 CSS 选择器片段如 ".nav-badge"）
    return pattern in sel


# ============ A2-2: 同 chart 多线 hue 差 ============


def assert_distinct_hues(
    chart_id: str,
    line_colors: list[str],  # ['#79c0ff', '#7ee787', ...]
    min_hue_diff_deg: float = 30.0,
) -> AssertionResult:
    """断言: 同 chart 内多线颜色 HSL hue 差 > min_hue_diff_deg.

    用 RGB->HSL 计算 hue（0-360 度）。两两距离取最小值（环形）。
    """
    if len(line_colors) <= 1:
        return AssertionResult(assertion_id="A2-2", passed=True, selector=f"#{chart_id}")
    hues: list[tuple[str, float]] = []
    for c in line_colors:
        h = _hex_to_hue(c)
        if h is None:
            continue
        hues.append((c, h))
    if len(hues) <= 1:
        return AssertionResult(assertion_id="A2-2", passed=True, selector=f"#{chart_id}")
    violations: list[str] = []
    for i in range(len(hues)):
        for j in range(i + 1, len(hues)):
            ci, hi = hues[i]
            cj, hj = hues[j]
            diff = abs(hi - hj)
            diff = min(diff, 360 - diff)  # 环形距离
            if diff < min_hue_diff_deg:
                violations.append(f"{ci}(h={hi:.0f}) vs {cj}(h={hj:.0f}) Δ={diff:.0f}°")
    if violations:
        return AssertionResult(
            assertion_id="A2-2",
            passed=False,
            selector=f"#{chart_id}",
            actual=" / ".join(violations),
            expected=f"任意两线 hue Δ ≥ {min_hue_diff_deg}°",
            remediation="用对比色相替换其中一线（蓝/橙/绿/紫/黄/粉差异化）",
        )
    return AssertionResult(assertion_id="A2-2", passed=True, selector=f"#{chart_id}")


def _hex_to_hue(hex_color: str) -> Optional[float]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    except ValueError:
        return None
    hue, _, _ = colorsys.rgb_to_hls(r, g, b)
    return hue * 360


# ============ A3-1: 表格对齐统一 ============


def assert_table_alignment(
    td_aligns: dict[str, str],  # {selector: computed_text_align}
    expected_align: str = "left",
) -> list[AssertionResult]:
    """断言: 所有 td.num 的 text-align 必须一致 (=expected_align).

    Args:
        td_aligns: {td selector: getComputedStyle.textAlign}
        expected_align: "left" / "right" / "center" / "start"
    """
    if not td_aligns:
        return [AssertionResult(assertion_id="A3-1", passed=True, note="no td.num found")]
    bad = {sel: al for sel, al in td_aligns.items() if al not in (expected_align, "start")}
    if bad:
        first_three = list(bad.items())[:3]
        return [AssertionResult(
            assertion_id="A3-1",
            passed=False,
            selector=", ".join(s for s, _ in first_three),
            actual=f"text-align 不一致: {dict(first_three)}",
            expected=f"全部 {expected_align}",
            remediation=f"CSS td.num {{text-align:{expected_align}}} 统一规则",
        )]
    return [AssertionResult(assertion_id="A3-1", passed=True)]


# ============ A4-1: 数值列必须标单位 ============

# 数值正则: 整数 / 小数 / 千分位 / 百分号
NUMERIC_RE = re.compile(r"^[+-]?[\d,]+(\.\d+)?$")


def assert_units_on_numeric(
    table_cells: list[dict],  # [{th_text, td_text}, ...]
    units_whitelist: list[str],
) -> list[AssertionResult]:
    """断言: 数值类 td 必须含单位文本，或所属 th 含单位.

    table_cells: 每个 dict {th_text, td_text}
    units_whitelist: 允许的单位关键词 (MB / ms / KB / 个 / % / s / mV / mW 等)
    """
    bad: list[dict] = []
    for cell in table_cells:
        td = (cell.get("td_text") or "").strip()
        th = (cell.get("th_text") or "").strip()
        if not td or not NUMERIC_RE.match(td.replace(",", "")):
            continue  # 不是纯数字
        # td 自身含单位?
        if any(u in td for u in units_whitelist):
            continue
        # th 含单位?
        if any(u in th for u in units_whitelist):
            continue
        bad.append(cell)
    if bad:
        first = bad[:3]
        return [AssertionResult(
            assertion_id="A4-1",
            passed=False,
            selector=f"table th='{first[0].get('th_text','?')}'",
            actual=f"{len(bad)} 个数值 td 无单位，示例: {first}",
            expected=f"td 或对应 th 必须含 {units_whitelist} 之一",
            remediation="在 <th> 加单位 (如 '内存(MB)') 或 td 文本带单位",
        )]
    return [AssertionResult(assertion_id="A4-1", passed=True)]
