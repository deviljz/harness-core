"""verify fixture 的 review prompt 必须带隔离约束.

事故：verify 跑 fixture 时，reviewer subagent 有 Read/Grep 工具，会顺着 diff 里的
文件路径去读真实仓库的同名文件——若真实仓库已修复，fixture 的"坏代码"被"好代码"
覆盖，review 误判 consistent=true（假绿）。

修法：verify 的 prompt（仅此路径，不动正常 review 模板）前置硬约束——
被审代码就是 diff 全部，禁止读仓库其他文件。
"""

from harness.verify.runner import _build_prompt, FixtureData


def _fx() -> FixtureData:
    return FixtureData(
        name="x",
        spec_content="SPEC_MARKER",
        diff_content="DIFF_MARKER",
        subagent_report="REPORT_MARKER",
        expected={},
    )


_TEMPLATE = "## Spec\n{spec_content}\n## Diff\n{diff_content}\nfocus {focus}"


def test_prompt_has_isolation_guard():
    p = _build_prompt(_fx(), _TEMPLATE)
    # 必须明确禁止读仓库其他文件
    assert "禁止" in p
    assert ("Read" in p or "Grep" in p or "Glob" in p)
    assert "仓库" in p or "其他文件" in p
    # 必须声明 diff 即全部真相
    assert "diff" in p.lower()


def test_prompt_still_contains_spec_diff_report():
    p = _build_prompt(_fx(), _TEMPLATE)
    assert "SPEC_MARKER" in p
    assert "DIFF_MARKER" in p
    assert "REPORT_MARKER" in p


def test_isolation_guard_precedes_material():
    # 隔离约束应在材料之前（reviewer 先看到约束再读 diff）
    p = _build_prompt(_fx(), _TEMPLATE)
    assert p.index("禁止") < p.index("DIFF_MARKER")
