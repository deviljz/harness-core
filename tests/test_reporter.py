"""reporter 测试：报告结构、双输出、哈希"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from harness.reporter import (
    CheckResult,
    ValidationReport,
    content_hash,
    make_session_id,
    render_markdown,
    render_xml_compact,
    save_check_json,
    save_markdown,
)


def _sample_report(status="pass") -> ValidationReport:
    return ValidationReport(
        session_id=make_session_id(),
        timestamp=time.time(),
        project="test",
        trigger="manual",
        results=[
            CheckResult(
                check_name="pytest_runner",
                target="backend",
                status=status,
                message="5 passed, 0 failed",
                details={"passed": 5, "failed": 0},
                duration_ms=1234,
            )
        ],
    )


class TestReport:
    def test_all_green(self):
        r = _sample_report("pass")
        assert r.all_green
        assert not r.has_failures

    def test_has_failures(self):
        r = _sample_report("fail")
        assert not r.all_green
        assert r.has_failures

    def test_warning_only_not_all_green(self):
        # warning 不算失败，但也不算"有 pass"
        r = ValidationReport(
            session_id="x",
            timestamp=0,
            project="p",
            trigger="manual",
            results=[
                CheckResult(check_name="c", target="t", status="warn", message="m"),
            ],
        )
        # warn 不是 fail，但没 pass → 也不是 all_green
        assert not r.all_green
        assert not r.has_failures


class TestRender:
    def test_markdown_has_key_fields(self):
        r = _sample_report()
        md = render_markdown(r)
        assert "Harness Check Report" in md
        assert r.session_id in md
        assert "pytest_runner" in md
        assert "backend" in md
        assert "ALL GREEN" in md

    def test_xml_is_compact(self):
        r = _sample_report()
        xml = render_xml_compact(r)
        assert "<validation_report" in xml
        assert "<target" in xml
        assert "<check" in xml
        assert "<next_action>all_green</next_action>" in xml
        # 紧凑：没有换行缩进
        assert "\n" not in xml

    def test_xml_fail_next_action(self):
        r = _sample_report("fail")
        xml = render_xml_compact(r)
        assert "fix_failures" in xml

    def test_xml_escapes_special_chars(self):
        r = ValidationReport(
            session_id="s",
            timestamp=0,
            project="p",
            trigger="manual",
            results=[
                CheckResult(
                    check_name="c",
                    target="<danger>",
                    status="fail",
                    message='quotes"and<tags>',
                ),
            ],
        )
        xml = render_xml_compact(r)
        assert "&lt;danger&gt;" in xml
        assert "&quot;" in xml


class TestSave:
    def test_save_json_has_content_hash(self, tmp_path):
        r = _sample_report()
        out = save_check_json(r, tmp_path)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "content_hash" in data
        assert len(data["content_hash"]) == 16
        # 文件名包含 hash
        assert data["content_hash"] in out.name

    def test_save_json_content_hash_deterministic(self, tmp_path):
        r1 = ValidationReport(
            session_id="fixed",
            timestamp=1234567,
            project="p",
            trigger="manual",
            results=[
                CheckResult("c", "t", "pass"),
            ],
        )
        r2 = ValidationReport(
            session_id="fixed",
            timestamp=1234567,
            project="p",
            trigger="manual",
            results=[
                CheckResult("c", "t", "pass"),
            ],
        )
        out1 = save_check_json(r1, tmp_path / "d1")
        out2 = save_check_json(r2, tmp_path / "d2")
        # 同内容应得同 hash
        h1 = json.loads(out1.read_text())["content_hash"]
        h2 = json.loads(out2.read_text())["content_hash"]
        assert h1 == h2

    def test_save_markdown(self, tmp_path):
        r = _sample_report()
        out = save_markdown(r, tmp_path)
        assert out.exists()
        assert "Harness Check Report" in out.read_text(encoding="utf-8")


def test_content_hash_short_and_deterministic():
    h1 = content_hash("hello")
    h2 = content_hash("hello")
    assert h1 == h2
    assert len(h1) == 16
    assert content_hash("hello") != content_hash("world")
