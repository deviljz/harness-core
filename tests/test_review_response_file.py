"""review 非轮询模式：--emit-prompt 出 prompt + --response-file 回灌 JSON。

修 Hermes 反馈：manual provider 轮询 600s 但 CLI 终端 60s 先超时，且重跑换新 ts 对不上。
非轮询两步走：出 prompt → 外部 AI 审 → 回灌 response 文件。
"""

from pathlib import Path

import pytest

from harness.review.runner import parse_review_response, build_review_prompt


# ── parse_review_response：解析外部 AI 回的 review JSON ──

def test_parse_plain_json():
    r = parse_review_response('{"consistent": true, "issues": []}')
    assert r.consistent is True
    assert r.issues == []
    assert r.error is None


def test_parse_code_fenced():
    r = parse_review_response('前言\n```json\n{"consistent": false, "issues": ["a.py:1 - x"]}\n```\n')
    assert r.consistent is False
    assert r.issues == ["a.py:1 - x"]


def test_parse_unparseable():
    r = parse_review_response("这根本不是 JSON")
    assert r.consistent is False
    assert r.error == "parse_error"


# ── build_review_prompt：打包 spec+diff 填模板（空 diff 返 None）──

def test_build_prompt_none_on_empty_diff(monkeypatch):
    import harness.review.runner as R
    monkeypatch.setattr(R, "package_diff", lambda *a, **k: {"diff_content": "   ", "spec_content": ""})
    assert R.build_review_prompt(Path("."), None, focus="x") is None


def test_build_prompt_fills_spec_and_diff(monkeypatch):
    import harness.review.runner as R
    monkeypatch.setattr(R, "package_diff", lambda *a, **k: {"diff_content": "DIFFBODY", "spec_content": "SPECBODY"})
    p = R.build_review_prompt(Path("."), None, focus="api_contract")
    assert p is not None
    assert "DIFFBODY" in p and "SPECBODY" in p


# ── CLI：--response-file 回灌（不轮询、不调 LLM）──

def _mini_project(root: Path):
    (root / ".harness").mkdir()
    (root / ".harness" / "config.yaml").write_text(
        "project: t\nllm:\n  provider: manual\ntargets: []\n", encoding="utf-8"
    )


def test_cli_response_file_inconsistent_exits_2(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from harness.cli import main

    _mini_project(tmp_path)
    (tmp_path / "reviewed.json").write_text(
        '{"consistent": false, "issues": ["x.py:1 - bug"]}', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["review", "--response-file", "reviewed.json"])
    assert res.exit_code == 2
    assert "x.py:1" in res.output


def test_cli_response_file_consistent_exits_0(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from harness.cli import main

    _mini_project(tmp_path)
    (tmp_path / "ok.json").write_text('{"consistent": true, "issues": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["review", "--response-file", "ok.json"])
    assert res.exit_code == 0


def test_cli_response_file_missing_exits_nonzero_with_hint(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from harness.cli import main

    _mini_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["review", "--response-file", "nope.json"])
    assert res.exit_code != 0
    assert "emit-prompt" in res.output  # 提示先生成 prompt
