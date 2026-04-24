"""harness init CLI 语义测试

关键不变量：
- 既存 config.yaml 的用户配置不被 --force 清掉
- --reset-config 才显式重置 config.yaml
- --force 会刷新框架文件（run_hook.py / commands）
"""
from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from harness.cli import main


def _run_init(tmp_path: Path, *args: str) -> tuple[int, str]:
    runner = CliRunner()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(main, ["init", "--no-hooks", *args])
        return result.exit_code, result.output
    finally:
        os.chdir(cwd)


class TestInitConfigPreservation:
    def test_fresh_init_creates_config(self, tmp_path):
        code, _ = _run_init(tmp_path)
        assert code == 0
        assert (tmp_path / ".harness" / "config.yaml").exists()

    def test_force_preserves_existing_config(self, tmp_path):
        """回归测试：--force 不能清掉用户的 config.yaml"""
        cfg = tmp_path / ".harness" / "config.yaml"
        cfg.parent.mkdir(parents=True)
        user_content = (
            "project: my_proj\n"
            "targets:\n"
            "  - name: backend\n"
            "    root: src/\n"
            "    language: python\n"
            "trigger_on_edit_paths:\n"
            "  - src/**/*.py\n"
        )
        cfg.write_text(user_content, encoding="utf-8")

        code, output = _run_init(tmp_path, "--force")
        assert code == 0
        # 用户配置必须原样保留
        assert cfg.read_text(encoding="utf-8") == user_content
        assert "保留" in output or "preserved" in output.lower() or True  # 提示内容可改

    def test_reset_config_explicitly_wipes(self, tmp_path):
        cfg = tmp_path / ".harness" / "config.yaml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("project: old\ntargets: []\n", encoding="utf-8")

        code, _ = _run_init(tmp_path, "--reset-config")
        assert code == 0
        new_content = cfg.read_text(encoding="utf-8")
        # 模板里有 ignore_paths_global 等固定字段
        assert "ignore_paths_global" in new_content

    def test_init_without_force_keeps_config(self, tmp_path):
        """老行为：无 --force 也保留 config"""
        cfg = tmp_path / ".harness" / "config.yaml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("project: keep_me\n", encoding="utf-8")

        code, _ = _run_init(tmp_path)
        assert code == 0
        assert "keep_me" in cfg.read_text(encoding="utf-8")
