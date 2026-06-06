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


# ============ 通用数据不变量断言（机制层，业务规则由项目 config 提供）============
#
# 从报告里按 selector 取数值 → 聚合（sum/max/min/none）→ 和参照值（常量或另一 selector
# 取值，可乘 factor）按谓词比较。具体业务不变量（marker≤时长、FPS≤cap、占比≤100% 等）
# **不写进 harness-core**，由调用方在 .harness/ config 的 `data_invariants` 提供。
#
# samples 结构（由 runner.py 的 DOM 采集产出，单测可直接构造）:
#   {selector: {"texts": [textContent, ...], "count": N}}

_NUM_OPS = {
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

_NUMERIC_TOKEN_RE = re.compile(r"[-+]?\d*\.?\d+")


def _parse_number(text: Optional[str]) -> Optional[float]:
    """从文本里抽第一个数值 token（去千分位逗号，容忍单位/百分号后缀）。"""
    if text is None:
        return None
    m = _NUMERIC_TOKEN_RE.search(str(text).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _resolve_numeric(sample: dict, extract: str, aggregate: str) -> tuple[Optional[float], str]:
    """从一个 selector 采样里解析出标量值。返回 (value, error)。error 非空表示失败。"""
    if extract == "count":
        return float(sample.get("count", 0)), ""
    if extract.startswith("attr:"):
        return None, "extract=attr 暂未支持（用 number / count）"
    if extract not in ("number", "text", ""):
        return None, f"未知 extract={extract!r}"
    texts = sample.get("texts", [])
    nums = [n for n in (_parse_number(t) for t in texts) if n is not None]
    if not nums:
        return None, f"未从 {len(texts)} 个元素解析出数值"
    agg = aggregate or "none"
    if agg == "none":
        if len(nums) != 1:
            return None, f"匹配 {len(nums)} 个值但 aggregate=none（请指定 sum/max/min）"
        return nums[0], ""
    if agg == "sum":
        return sum(nums), ""
    if agg == "max":
        return max(nums), ""
    if agg == "min":
        return min(nums), ""
    return None, f"未知 aggregate={agg!r}"


def assert_data_invariant(spec: dict, samples: dict) -> AssertionResult:
    """通用数据不变量断言。

    spec 字段：
      id          断言 id（必填，会显示在报告里）
      severity    error | warn（默认 error）
      remediation 修复建议（缺省用 description）
      description 人话说明
      value       {selector, extract=number|count, aggregate=none|sum|max|min}
      op          <= < >= > == != non_empty empty
      ref         {const: <num>} 或 {selector, extract, aggregate}（op 为 non_empty/empty 时可省）
      factor      ref * factor，默认 1.0
    """
    inv_id = spec.get("id", "data-invariant")
    sev = Severity.WARN if spec.get("severity") == "warn" else Severity.ERROR
    remediation = spec.get("remediation") or spec.get("description", "")
    value_spec = spec.get("value", {})
    vsel = value_spec.get("selector", "")
    op = spec.get("op", "")

    def fail(actual: str, expected: str, note: str = "") -> AssertionResult:
        return AssertionResult(inv_id, False, sev, vsel, actual, expected, remediation, note)

    def ok(note: str = "") -> AssertionResult:
        return AssertionResult(inv_id, True, sev, vsel, note=note)

    if not vsel:
        return fail("缺 value.selector", "value.selector 必填", "config 非法")

    vsample = samples.get(vsel)
    if vsample is None:
        return fail(f"selector {vsel!r} 未在快照中采集到", "存在可采集的匹配元素",
                    "selector 没采到——检查报告是否暴露了机器可读值")

    # non_empty / empty：基于匹配元素个数
    if op in ("non_empty", "empty"):
        cnt = vsample.get("count", 0)
        if op == "non_empty":
            return ok(f"count={cnt}") if cnt >= 1 else fail("count=0（空）", "至少 1 个匹配元素")
        return ok(f"count={cnt}") if cnt == 0 else fail(f"count={cnt}（非空）", "0 个匹配元素")

    if op not in _NUM_OPS:
        return fail(f"未知 op {op!r}", f"{list(_NUM_OPS)} / non_empty / empty", "config op 非法")

    actual_val, err = _resolve_numeric(
        vsample, value_spec.get("extract", "number"), value_spec.get("aggregate", "none")
    )
    if err:
        return fail(err, "可解析的数值", f"value selector {vsel}")

    ref_spec = spec.get("ref") or {}
    try:
        factor = float(spec.get("factor", 1.0))
    except (TypeError, ValueError):
        return fail(f"factor={spec.get('factor')!r} 非数值", "数值 factor", "config 非法")

    if "const" in ref_spec:
        try:
            ref_base = float(ref_spec["const"])
        except (TypeError, ValueError):
            return fail(f"ref.const={ref_spec['const']!r} 非数值", "数值常量", "config 非法")
    elif ref_spec.get("selector"):
        rsel = ref_spec["selector"]
        rsample = samples.get(rsel)
        if rsample is None:
            return fail(f"ref selector {rsel!r} 未采集到", "存在", "ref selector 不在快照")
        ref_base, err = _resolve_numeric(
            rsample, ref_spec.get("extract", "number"), ref_spec.get("aggregate", "none")
        )
        if err:
            return fail(err, "可解析的 ref 数值", f"ref selector {rsel}")
    else:
        return fail("缺 ref", "ref.const 或 ref.selector", "数值 op 必须给 ref")

    threshold = ref_base * factor
    if _NUM_OPS[op](actual_val, threshold):
        return ok(f"{actual_val:g} {op} {threshold:g}")
    expected = f"{op} {threshold:g}" + (f" (={ref_base:g}×{factor:g})" if factor != 1.0 else "")
    return fail(f"{actual_val:g}", expected)


# ============ 脚本不变量（在报告页内跑任意 JS 求值，全数据集 sanity）============
#
# Why this exists（区别于 assert_data_invariant）:
#   data_invariant 是「按 selector 取 DOM 文本 → 比较」，只能读 DOM 上**当前可见**的值。
#   但有些 sanity 要遍历**整个内存数据集**（如 Periscope 全部卡顿帧逐帧跑 spkCatNs，
#   验「单帧任何分类耗时 ≤ frameMs」「占比和 ≤ 100%」），DOM 一次只显一帧，selector 取不到。
#   且分类口径已经在报告 JS 里（spkCatNs），在 Python 重写一遍 = 口径漂移 = 新 bug 源。
#   → 直接在已加载报告的 chrome 页里跑 JS 表达式，复用报告自己的函数/数据，零口径漂移。
#
# eval_result 由 runner.py 在 page 内对 spec.expr 求值产出（单测可直接构造）:
#   - {"pass": bool, "actual": str, "expected": str}  ← 推荐：表达式自己给裁决+明细
#   - bool                                            ← 简写：true=pass
#   - {"error": str}                                  ← 表达式抛错
#   - None                                            ← 表达式没产出（id 未采集/页面没跑）


def assert_script_invariant(spec: dict, eval_result) -> AssertionResult:
    """脚本不变量断言。表达式在报告页全局作用域求值，可访问报告内联的全局函数/数据。

    spec 字段：
      id          断言 id（必填，显示在报告里）
      severity    error | warn（默认 error）
      description 人话说明（作为 selector 列显示）
      remediation 修复建议（缺省用 description）
      expr        页面内 JS 表达式（必填）。约定返回 {pass, actual, expected} 或 bool。
                  可访问报告全局变量（如 spkCatNs / JANK_FRAMES / COUNTERS / FRAMES_MS）。
    """
    inv_id = spec.get("id", "script-invariant")
    sev = Severity.WARN if spec.get("severity") == "warn" else Severity.ERROR
    desc = spec.get("description", "")
    remediation = spec.get("remediation") or desc

    def fail(actual: str, expected: str, note: str = "") -> AssertionResult:
        return AssertionResult(inv_id, False, sev, desc, actual, expected, remediation, note)

    def ok(note: str = "") -> AssertionResult:
        return AssertionResult(inv_id, True, sev, desc, note=note)

    if not spec.get("id"):
        # JS 采集侧 (!inv.id) 会直接跳过该条目——必须在这里给准确报错，
        # 否则落到「表达式未产出结果」分支，误导排查方向。
        return fail("缺 id", "id 必填（结果按 id 存取）", "config 非法")
    if not spec.get("expr"):
        return fail("缺 expr", "expr 必填（页面内 JS 表达式）", "config 非法")
    if eval_result is None:
        return fail("表达式未产出结果", "返回 {pass, actual, expected} 或 bool",
                    "页面未求值 / id 未采集——检查 runner 是否注入了该 invariant")
    if isinstance(eval_result, dict) and eval_result.get("error"):
        return fail(f"expr 抛错: {eval_result['error']}", "expr 正常求值",
                    "检查页面作用域是否有所需函数/数据（如 spkCatNs / JANK_FRAMES）")
    if isinstance(eval_result, bool):
        return ok("true") if eval_result else fail("expr 返回 false", "expr 返回 true")
    if isinstance(eval_result, dict) and "pass" in eval_result:
        if eval_result["pass"]:
            return ok(str(eval_result.get("actual", "")))
        return fail(str(eval_result.get("actual", "false")),
                    str(eval_result.get("expected", "pass=true")))
    return fail(f"无法识别的结果: {eval_result!r}",
                "{pass, actual, expected} 或 bool", "expr 返回值格式不符约定")
