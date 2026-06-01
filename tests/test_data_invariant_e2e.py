"""数据不变量端到端：真 chromium 加载 HTML → JS 采集 → 解析数值 → 断言。

验证文档关心的可行性问题：能否从渲染后的报告里抠出机器可读数值并断言。
无 chromium 的环境自动 skip（playwright 是 opt-in extra）。
"""

import pytest


def _chromium_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _chromium_ok(), reason="playwright chromium 不可用（opt-in extra）")


def test_e2e_data_invariant_real_html(tmp_path):
    from harness.skills.harness_visual_audit.runner import run_audit, AuditConfig

    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><body>
          <div id="duration">600</div>
          <span class="total">100</span><span class="total">200</span><span class="total">500</span>
          <span class="pct">95%</span><span class="pct">120%</span>
          <ul><li class="spike">frameA</li><li class="spike">frameB</li></ul>
        </body></html>""",
        encoding="utf-8",
    )

    cfg = AuditConfig(
        target=str(html),
        config={
            "assertions": {},  # 只验 data_invariants 链路
            "data_invariants": [
                # marker 各线程 total(sum=800) ≤ 时长(600)×1.1=660 → FAIL
                {"id": "marker_total_le_duration", "value": {"selector": ".total", "aggregate": "sum"},
                 "op": "<=", "ref": {"selector": "#duration"}, "factor": 1.1},
                # 占比 max(120) ≤ 100 → FAIL（解析 "120%"）
                {"id": "pct_le_100", "value": {"selector": ".pct", "aggregate": "max"},
                 "op": "<=", "ref": {"const": 100}},
                # spike 列表非空 → PASS
                {"id": "spike_nonempty", "value": {"selector": ".spike"}, "op": "non_empty"},
            ],
        },
    )

    res = run_audit(cfg)
    by_id = {r.assertion_id: r.passed for r in res.results}
    assert by_id["marker_total_le_duration"] is False  # 真从 DOM 抠出 100/200/500 求和
    assert by_id["pct_le_100"] is False                # 真解析 "120%"
    assert by_id["spike_nonempty"] is True             # 真数到 2 个 .spike
