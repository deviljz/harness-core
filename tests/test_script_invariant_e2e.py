"""脚本不变量端到端：真 chromium 加载 HTML → 页内 new Function 求值 expr → 断言.

验证关键可行性：expr 在页面全局作用域跑、能访问报告内联 <script> 的顶层 function/var、
Promise 结果被 await、抛错自动判 FAIL。
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


def test_e2e_script_invariant_real_html(tmp_path):
    from harness.skills.harness_visual_audit.runner import run_audit, AuditConfig

    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><body>
        <script>
          var DATA = [1, 2, 3];
          function double(x) { return x * 2; }
        </script>
        </body></html>""",
        encoding="utf-8",
    )

    cfg = AuditConfig(
        target=str(html),
        config={
            "assertions": {},  # 只验 script_invariants 链路
            "data_invariants": [],
            "script_invariants": [
                # 复用页面全局 function/var 遍历全数据集 → PASS
                {"id": "uses_page_globals", "expr": (
                    "(function(){"
                    "  var bad = DATA.filter(function(x){ return double(x) !== x * 2; });"
                    "  return {pass: bad.length === 0, actual: bad.length + ' bad', expected: '0 bad'};"
                    "})()"
                )},
                # bool 简写 → FAIL（DATA 长度是 3 不是 4）
                {"id": "bool_shorthand_fail", "expr": "DATA.length === 4"},
                # Promise 结果被 await → PASS
                {"id": "promise_awaited", "expr": "Promise.resolve({pass: true, actual: 'async ok', expected: ''})"},
                # 抛错（未定义函数）→ 自动判 FAIL，错误信息进 actual
                {"id": "throw_is_fail", "expr": "notDefinedAnywhere()"},
            ],
        },
    )

    res = run_audit(cfg)
    by_id = {r.assertion_id: r for r in res.results}
    assert by_id["uses_page_globals"].passed is True       # 真访问到了页面全局 DATA/double
    assert by_id["bool_shorthand_fail"].passed is False    # bool false → FAIL
    assert by_id["promise_awaited"].passed is True         # Promise 被 await
    assert by_id["throw_is_fail"].passed is False
    assert "notDefinedAnywhere" in by_id["throw_is_fail"].actual
