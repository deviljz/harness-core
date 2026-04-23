"""审查层测试：用 fake LLM provider"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.llm.base import LLMProvider
from harness.review import run_review
from harness.review.diff_packager import package_diff
from harness.review.runner import _extract_json


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str = ""):
        super().__init__()
        self.response = response
        self.last_prompt = None

    def complete(self, prompt: str, context: dict | None = None) -> str:
        self.last_prompt = prompt
        return self.response


class TestExtractJson:
    def test_plain(self):
        assert _extract_json('{"consistent": true, "issues": []}') == {
            "consistent": True,
            "issues": [],
        }

    def test_code_fence(self):
        txt = "here is my review:\n```json\n{\"consistent\": false, \"issues\": [\"x\"]}\n```\n"
        data = _extract_json(txt)
        assert data == {"consistent": False, "issues": ["x"]}

    def test_invalid_returns_none(self):
        assert _extract_json("definitely not json") is None


class TestRunReview:
    def _setup_git_repo(self, tmp_path: Path):
        """搞一个有 diff 的临时 git repo"""
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        (tmp_path / "app.py").write_text("def foo(): pass\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
        # 改动
        (tmp_path / "app.py").write_text("def foo(): return 42\n")

    def test_consistent_response(self, tmp_path):
        self._setup_git_repo(tmp_path)
        prov = FakeProvider('{"consistent": true, "issues": []}')
        result = run_review(prov, tmp_path, spec_path=None)
        assert result.consistent
        assert result.issues == []

    def test_inconsistent_response(self, tmp_path):
        self._setup_git_repo(tmp_path)
        prov = FakeProvider(
            '```json\n{"consistent": false, "issues": ["返回值类型与 spec 不符"]}\n```'
        )
        result = run_review(prov, tmp_path, spec_path=None)
        assert not result.consistent
        assert "返回值类型与 spec 不符" in result.issues

    def test_prompt_contains_diff(self, tmp_path):
        self._setup_git_repo(tmp_path)
        prov = FakeProvider('{"consistent": true, "issues": []}')
        run_review(prov, tmp_path, spec_path=None)
        assert "def foo(): return 42" in prov.last_prompt

    def test_prompt_contains_spec(self, tmp_path):
        self._setup_git_repo(tmp_path)
        spec = tmp_path / "spec.md"
        spec.write_text("# My Spec\nSpec body marker XYZ123")
        prov = FakeProvider('{"consistent": true, "issues": []}')
        run_review(prov, tmp_path, spec_path=spec)
        assert "XYZ123" in prov.last_prompt

    def test_empty_diff_short_circuits(self, tmp_path):
        # 没 git init 时
        prov = FakeProvider("xxx")
        result = run_review(prov, tmp_path, spec_path=None)
        # 不该调 provider
        assert prov.last_prompt is None

    def test_unparseable_response(self, tmp_path):
        self._setup_git_repo(tmp_path)
        prov = FakeProvider("I think your code is fine, no JSON here.")
        result = run_review(prov, tmp_path, spec_path=None)
        assert not result.consistent
        assert result.error == "parse_error"


class TestPackageDiff:
    def test_includes_spec_content(self, tmp_path):
        spec = tmp_path / "s.md"
        spec.write_text("spec content here")
        data = package_diff(tmp_path, spec_path=spec)
        assert data["spec_content"] == "spec content here"

    def test_truncates_large_diff(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        (tmp_path / "big.py").write_text("x = 1\n" * 10000)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
        (tmp_path / "big.py").write_text("y = 2\n" * 10000)
        data = package_diff(tmp_path, max_diff_chars=500)
        assert len(data["diff_content"]) <= 600  # 500 + truncation msg
        assert "truncated" in data["diff_content"]
