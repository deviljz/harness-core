"""visual-audit runner: playwright 抓 DOM → 调 assertions → 汇总.

可选依赖 playwright (URL / 复杂 hover); 静态 HTML 也走 playwright (file:// 协议)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .assertions import (
    AssertionResult,
    Severity,
    assert_tooltip_no_unrelated,
    assert_non_chart_hides_tooltip,
    assert_color_palette,
    assert_distinct_hues,
    assert_table_alignment,
    assert_units_on_numeric,
    assert_data_invariant,
)


# 默认 Periscope-friendly 配置（可被用户 config 覆盖）
DEFAULT_CONFIG: dict = {
    "charts_selector": "svg.chart, svg[id^=chart]",
    "non_chart_ids": ["phaseTimeline", "sceneTimeline", "chartScenes", "flameChart"],
    "palette": {
        "allowed_hex": ["#79c0ff", "#7ee787", "#ffa657", "#d2a8ff", "#ffd479", "#ec4899", "#888", "#a3c75a", "#9874c4"],
        "semantic_reserved": {
            "#dc2626": [".nav-badge", ".kpi-issue-dot.bad"],
            "#f85149": [".log-level-error", ".log-level-exception"],
        },
    },
    "assertions": {
        "A1-1": {
            "enabled": True,
            "forbidden_keywords": ["frameMs", "GPU=", "DC=", "GC="],
            "chart_exceptions": {
                "chartFrameMs": ["frameMs"],
                "chartBrush": ["frameMs"],
                "chartCpuGpu": ["CPU", "GPU"],
                "chartGc": ["GC"],
            },
        },
        "A1-2": {"enabled": True},
        "A2-1": {"enabled": True, "ignore_grayscale": True},
        "A2-2": {"enabled": True, "min_hue_diff_deg": 30.0},
        "A3-1": {"enabled": True, "expected_align": "left"},
        "A4-1": {"enabled": True, "units": ["MB", "ms", "KB", "个", "%", "s", "mV", "mW", "fps", "FPS", "B", "次", "帧"]},
    },
    # 通用数据不变量：harness-core 不内置任何业务规则；由项目 config 提供具体不变量。
    # 每条 schema 见 assertions.assert_data_invariant / SKILL.md。
    "data_invariants": [],
}


@dataclass
class AuditConfig:
    target: str
    config: dict = field(default_factory=lambda: dict(DEFAULT_CONFIG))
    report_path: Optional[str] = None


@dataclass
class AuditResult:
    target: str
    results: list[AssertionResult] = field(default_factory=list)

    @property
    def passed(self) -> list[AssertionResult]:
        return [r for r in self.results if r.passed]

    @property
    def failed(self) -> list[AssertionResult]:
        return [r for r in self.results if not r.passed]


def run_audit(cfg: AuditConfig) -> AuditResult:
    """执行 audit. 用 playwright 抓 DOM 然后跑断言."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as e:
        raise ImportError(
            "harness-visual-audit requires playwright. "
            "Install: pip install 'harness-core[playwright]' "
            "and run: playwright install chromium"
        ) from e

    target_url = _to_url(cfg.target)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(800)

        snapshot = _collect_dom_snapshot(page, cfg.config)
        browser.close()

    return evaluate_snapshot(cfg, snapshot)


def evaluate_snapshot(cfg: AuditConfig, snapshot: dict) -> AuditResult:
    """纯函数：给定已采集的 DOM 快照，按 config 跑全部断言。不依赖 playwright，可单测。"""
    result = AuditResult(target=cfg.target)

    # === 跑 6 项断言 ===
    a = cfg.config.get("assertions", {})

    if a.get("A1-1", {}).get("enabled"):
        forbidden = a["A1-1"].get("forbidden_keywords", [])
        exceptions = a["A1-1"].get("chart_exceptions", {})
        for chart_id, tooltip_text in snapshot.get("chart_tooltips", {}).items():
            allowed = exceptions.get(chart_id)
            result.results.append(
                assert_tooltip_no_unrelated(chart_id, tooltip_text, forbidden, allowed_for_chart=allowed)
            )

    if a.get("A1-2", {}).get("enabled"):
        for el_id, disp in snapshot.get("non_chart_tooltip_display", {}).items():
            result.results.append(assert_non_chart_hides_tooltip(el_id, disp))

    if a.get("A2-1", {}).get("enabled"):
        palette = cfg.config["palette"]["allowed_hex"]
        semantic = cfg.config["palette"].get("semantic_reserved", {})
        ignore_gs = a["A2-1"].get("ignore_grayscale", True)
        for res in assert_color_palette(
            snapshot.get("used_colors", {}), palette, semantic, ignore_gs
        ):
            result.results.append(res)

    if a.get("A2-2", {}).get("enabled"):
        min_hue = a["A2-2"].get("min_hue_diff_deg", 30.0)
        for chart_id, line_colors in snapshot.get("chart_line_colors", {}).items():
            result.results.append(assert_distinct_hues(chart_id, line_colors, min_hue))

    if a.get("A3-1", {}).get("enabled"):
        for res in assert_table_alignment(
            snapshot.get("td_num_aligns", {}), a["A3-1"].get("expected_align", "left")
        ):
            result.results.append(res)

    if a.get("A4-1", {}).get("enabled"):
        units = a["A4-1"].get("units", [])
        for res in assert_units_on_numeric(snapshot.get("table_cells", []), units):
            result.results.append(res)

    # === 通用数据不变量（业务规则由项目 config 的 data_invariants 提供；默认空）===
    di_samples = snapshot.get("data_invariant_samples", {})
    for inv in cfg.config.get("data_invariants", []):
        result.results.append(assert_data_invariant(inv, di_samples))

    return result


def _to_url(target: str) -> str:
    if target.startswith(("http://", "https://", "file://")):
        return target
    p = Path(target).resolve()
    return p.as_uri()


# === DOM 数据采集 (playwright 内执行 JS) ===

_COLLECT_JS = r"""
async (config) => {
  await new Promise(r => setTimeout(r, 300));

  function getChartIds(selector) {
    return [...document.querySelectorAll(selector)].map(e => e.id).filter(Boolean);
  }

  async function hoverChart(id) {
    const svg = document.getElementById(id);
    if (!svg) return null;
    const r = svg.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) return null;
    svg.dispatchEvent(new MouseEvent('mousemove', {
      clientX: r.left + r.width / 2,
      clientY: r.top + r.height / 2,
      bubbles: true
    }));
    await new Promise(r => setTimeout(r, 80));
    const tip = document.getElementById('tooltip');
    return tip ? tip.innerText : '';
  }

  const out = {
    chart_tooltips: {},
    non_chart_tooltip_display: {},
    used_colors: {},
    chart_line_colors: {},
    td_num_aligns: {},
    table_cells: [],
    data_invariant_samples: {},
  };

  // Chart tooltips (A1-1)
  const chartIds = getChartIds(config.charts_selector);
  for (const id of chartIds) {
    const txt = await hoverChart(id);
    if (txt !== null) out.chart_tooltips[id] = txt;
  }

  // Non-chart tooltip residual (A1-2): hover chartFrameMs 让 tip 显示, 再 hover non-chart, 看 display
  const firstChart = document.getElementById('chartFrameMs') || document.getElementById('chartBrush');
  for (const id of (config.non_chart_ids || [])) {
    const el = document.getElementById(id);
    if (!el) continue;
    // 先让 tip 显示
    if (firstChart) {
      const r = firstChart.getBoundingClientRect();
      firstChart.dispatchEvent(new MouseEvent('mousemove', {
        clientX: r.left + r.width / 2,
        clientY: r.top + r.height / 2,
        bubbles: true
      }));
      await new Promise(r => setTimeout(r, 80));
    }
    const r = el.getBoundingClientRect();
    if (r.width < 5) { out.non_chart_tooltip_display[id] = 'hidden'; continue; }
    el.dispatchEvent(new MouseEvent('mousemove', {
      clientX: r.left + r.width / 2,
      clientY: r.top + r.height / 2,
      bubbles: true
    }));
    await new Promise(r => setTimeout(r, 100));
    const tip = document.getElementById('tooltip');
    out.non_chart_tooltip_display[id] = tip ? getComputedStyle(tip).display : 'none';
  }

  // Color palette scan (A2-1): 收集所有 inline color/background/fill/stroke hex
  function collectColor(el, prop, sel) {
    const style = el.getAttribute('style') || '';
    const m = style.match(new RegExp(prop + ':\\s*(#[0-9a-fA-F]{3,6})'));
    if (m) {
      const c = m[1].toLowerCase();
      if (!out.used_colors[c]) out.used_colors[c] = [];
      if (out.used_colors[c].length < 5) out.used_colors[c].push(sel);
    }
  }
  document.querySelectorAll('[style]').forEach(el => {
    const sel = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').filter(Boolean).join('.') : '');
    collectColor(el, 'color', sel);
    collectColor(el, 'background', sel);
    collectColor(el, 'fill', sel);
    collectColor(el, 'stroke', sel);
  });

  // Chart line colors (A2-2): 抽 svg.chart 内 path 的 stroke
  document.querySelectorAll(config.charts_selector).forEach(svg => {
    if (!svg.id) return;
    const colors = new Set();
    svg.querySelectorAll('path[stroke]').forEach(p => {
      const c = p.getAttribute('stroke');
      if (c && c.startsWith('#') && c !== '#111' && c !== '#333' && c !== '#888' && c !== '#fff') {
        colors.add(c.toLowerCase());
      }
    });
    if (colors.size > 1) out.chart_line_colors[svg.id] = [...colors];
  });

  // Table alignment (A3-1): td.num 的 computed text-align
  document.querySelectorAll('td.num').forEach((td, i) => {
    if (i > 30) return;
    const sel = '#' + (td.closest('[id]')?.id || '?') + ' td.num:nth-child(' + (i + 1) + ')';
    out.td_num_aligns[sel] = getComputedStyle(td).textAlign;
  });

  // Table cells units (A4-1): 抽 table 每个 td 和对应 th 文本
  document.querySelectorAll('table').forEach(tbl => {
    const thEls = tbl.querySelectorAll('thead th');
    const ths = [...thEls].map(t => t.textContent.replace(/\s+/g, ' ').trim());
    tbl.querySelectorAll('tbody tr').forEach((tr, ri) => {
      if (ri > 5) return;  // 限制采样
      [...tr.children].forEach((td, ci) => {
        if (out.table_cells.length > 80) return;
        const td_text = td.textContent.replace(/\s+/g, ' ').trim();
        const th_text = ths[ci] || '';
        if (td_text) out.table_cells.push({ td_text, th_text });
      });
    });
  });

  // Data invariants (通用): 为每个 invariant 的 value/ref selector 采集 {texts, count}
  function collectSelectorSamples(sel) {
    if (!sel || out.data_invariant_samples[sel]) return;
    const els = [...document.querySelectorAll(sel)];
    out.data_invariant_samples[sel] = {
      texts: els.slice(0, 1000).map(e => (e.textContent || '').replace(/\s+/g, ' ').trim()),
      count: els.length,
    };
  }
  for (const inv of (config.data_invariants || [])) {
    if (inv && inv.value && inv.value.selector) collectSelectorSamples(inv.value.selector);
    if (inv && inv.ref && inv.ref.selector) collectSelectorSamples(inv.ref.selector);
  }

  return out;
}
"""


def _collect_dom_snapshot(page, config: dict) -> dict:
    return page.evaluate(_COLLECT_JS, config)
