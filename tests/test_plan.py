"""方案层测试：模板 + validator"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.plan import render_template, validate_spec
from harness.plan.template import spec_filename
from harness.plan.validator import REQUIRED_SECTIONS, extract_complexity


class TestTemplate:
    def test_renders_with_task_name(self):
        out = render_template("Reward v2")
        assert "Reward v2" in out
        assert "complexity" in out.lower()
        for section in REQUIRED_SECTIONS:
            assert section in out

    def test_filename_has_date_and_slug(self):
        name = spec_filename("Reward v2")
        assert "_Reward_v2.md" in name

    def test_filename_spaces_replaced(self):
        assert "激励_v2" in spec_filename("激励 v2")


class TestValidator:
    def _write_spec(self, tmp_path: Path, content: str, name: str = "test_spec.md") -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_template_passes_once_filled(self, tmp_path):
        spec = render_template("Test")
        # 添加一些内容达到最低字数
        spec = spec.replace("**做什么**：", "**做什么**：做一个测试功能，verify a use case")
        spec = spec.replace("**为什么做**：", "**为什么做**：理由是一个合理的 rationale")
        spec += "\n\n内容填充填充填充填充填充填充填充填充填充填充填充" * 5
        p = self._write_spec(tmp_path, spec)
        issues = validate_spec(p)
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_missing_section(self, tmp_path):
        spec = "# x\n\n**complexity**: simple\n\n## 1. Objective\n内容" * 30
        p = self._write_spec(tmp_path, spec)
        issues = validate_spec(p)
        assert any("Commands" in i.message for i in issues)

    def test_missing_complexity(self, tmp_path):
        spec = render_template("x")
        spec = spec.replace("**complexity**: simple", "")
        p = self._write_spec(tmp_path, spec)
        issues = validate_spec(p)
        assert any("complexity" in i.message for i in issues)

    def test_empty_spec_flagged(self, tmp_path):
        p = self._write_spec(tmp_path, "")
        issues = validate_spec(p)
        assert any(i.severity == "error" for i in issues)

    def test_nonexistent_file(self, tmp_path):
        issues = validate_spec(tmp_path / "does_not_exist.md")
        assert any("not found" in i.message.lower() for i in issues)


class TestExtractComplexity:
    def test_simple(self, tmp_path):
        p = tmp_path / "s.md"
        p.write_text("**complexity**: simple\n")
        assert extract_complexity(p) == "simple"

    def test_complex(self, tmp_path):
        p = tmp_path / "s.md"
        p.write_text("**complexity**: complex\n")
        assert extract_complexity(p) == "complex"

    def test_missing(self, tmp_path):
        p = tmp_path / "s.md"
        p.write_text("no field here")
        assert extract_complexity(p) is None

    def test_case_insensitive(self, tmp_path):
        p = tmp_path / "s.md"
        p.write_text("**complexity**: Simple\n")
        assert extract_complexity(p) == "simple"
