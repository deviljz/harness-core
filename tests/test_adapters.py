"""Claude Code adapter 测试"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.adapters.claude_code import install_hooks, uninstall_hooks


class TestInstallHooks:
    def test_creates_settings_if_missing(self, tmp_path):
        path = install_hooks(tmp_path)
        assert path.exists()
        assert path.name == "settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "hooks" in data
        assert "PostToolUse" in data["hooks"]
        assert "Stop" in data["hooks"]

    def test_local_scope(self, tmp_path):
        path = install_hooks(tmp_path, scope="local")
        assert path.name == "settings.local.json"

    def test_idempotent(self, tmp_path):
        install_hooks(tmp_path)
        install_hooks(tmp_path)
        data = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        # 不会重复装
        posts = data["hooks"]["PostToolUse"]
        assert len([p for p in posts if "harness-core" in str(p)]) == 1

    def test_preserves_existing_hooks(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        settings = tmp_path / ".claude" / "settings.json"
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
                ]
            }
        }
        settings.write_text(json.dumps(existing), encoding="utf-8")

        install_hooks(tmp_path)
        data = json.loads(settings.read_text(encoding="utf-8"))
        posts = data["hooks"]["PostToolUse"]
        assert len(posts) == 2  # 保留 + 新增

    def test_uninstall_only_removes_harness(self, tmp_path):
        # 先装 + 加一条自己的
        install_hooks(tmp_path)
        settings = tmp_path / ".claude" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        data["hooks"]["PostToolUse"].append(
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
        )
        settings.write_text(json.dumps(data), encoding="utf-8")

        uninstall_hooks(tmp_path)
        data = json.loads(settings.read_text(encoding="utf-8"))
        # 自己的保留了，harness 的没了
        posts = data.get("hooks", {}).get("PostToolUse", [])
        assert any("echo mine" in str(p) for p in posts)
        assert not any("harness-core" in str(p) for p in posts)
