"""测试 ignore_paths_global 对 anti_patterns 扫描的过滤效果。"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.config import AntiPatternRule, HarnessConfig
from harness.validate.anti_patterns import run_anti_patterns


BARE_EXCEPT_RULE = AntiPatternRule(
    name="bare_except",
    pattern=r"except\s*:",
    msg="bare except",
    severity="error",
)


def _make_config(ignore_paths: list[str]) -> HarnessConfig:
    return HarnessConfig(
        project="test",
        ignore_paths_global=ignore_paths,
        anti_patterns={"python": [BARE_EXCEPT_RULE]},
    )


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    # tmp/bad.py — 应被 ignore
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "bad.py").write_text("try:\n    pass\nexcept:\n    pass\n")

    # src/good.py — 不应被 ignore，含 bare except
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "good.py").write_text("try:\n    pass\nexcept:\n    pass\n")

    return tmp_path


class TestIgnorePathsGlobal:
    def test_ignored_file_not_reported(self, project_root: Path) -> None:
        """tmp/** 内文件不应出现在结果中。"""
        config = _make_config(["tmp/**"])
        result = run_anti_patterns(config, project_root, changed_file=None)

        reported_files = {f["file"] for f in result.details["findings"]}
        assert not any("tmp" in f for f in reported_files), (
            f"tmp/ 文件不应被报告，实际: {reported_files}"
        )

    def test_non_ignored_file_reported(self, project_root: Path) -> None:
        """src/good.py 未被 ignore，必须出现在结果中。"""
        config = _make_config(["tmp/**"])
        result = run_anti_patterns(config, project_root, changed_file=None)

        reported_files = {f["file"] for f in result.details["findings"]}
        assert any("src/good.py" in f for f in reported_files), (
            f"src/good.py 应被报告，实际: {reported_files}"
        )

    def test_changed_file_ignored(self, project_root: Path) -> None:
        """changed_file 指定忽略路径时不扫描该文件。"""
        config = _make_config(["tmp/**"])
        result = run_anti_patterns(
            config, project_root, changed_file="tmp/bad.py"
        )
        assert result.details["total"] == 0

    def test_changed_file_not_ignored(self, project_root: Path) -> None:
        """changed_file 未被忽略时正常扫描。"""
        config = _make_config(["tmp/**"])
        result = run_anti_patterns(
            config, project_root, changed_file="src/good.py"
        )
        assert result.details["total"] > 0

    def test_empty_ignore_paths_unchanged_behavior(self, project_root: Path) -> None:
        """ignore_paths_global 为空时不影响原有行为——两个文件都应被扫到。"""
        config = _make_config([])
        result = run_anti_patterns(config, project_root, changed_file=None)

        reported_files = {f["file"] for f in result.details["findings"]}
        assert any("tmp" in f for f in reported_files), "空 ignore 时 tmp/ 应被扫描"
        assert any("src" in f for f in reported_files), "空 ignore 时 src/ 应被扫描"
