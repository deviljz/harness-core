"""config 加载 + 校验测试"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from harness.config import ConfigError, HarnessConfig, find_config, load_config


def _write_config(tmp_path: Path, content: str) -> Path:
    """在 tmp_path 下写一份 .harness/config.yaml，返回 config 路径"""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    cfg_path = harness_dir / "config.yaml"
    cfg_path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return cfg_path


# ════════════════════════════════════════════════════════════════════
# 基本加载
# ════════════════════════════════════════════════════════════════════


def test_load_minimal(tmp_path):
    cfg_path = _write_config(tmp_path, "project: myproj\n")
    cfg = load_config(cfg_path)
    assert cfg.project == "myproj"
    assert cfg.llm.provider == "claude_agent"
    assert cfg.targets == []


def test_load_full(tmp_path):
    cfg_path = _write_config(
        tmp_path,
        """
        project: miao-study
        llm:
          provider: manual
        ignore_paths_global:
          - .git/**
          - "**/*.log"
        circuit_breaker:
          max_retries: 5
        targets:
          - name: backend
            root: app/
            language: python
            ignore_paths:
              - "**/*.pyc"
        gate:
          require_evidence: true
        """,
    )
    cfg = load_config(cfg_path)
    assert cfg.project == "miao-study"
    assert cfg.llm.provider == "manual"
    assert cfg.circuit_breaker.max_retries == 5
    assert len(cfg.targets) == 1
    assert cfg.targets[0].name == "backend"
    assert cfg.targets[0].language == "python"


def test_load_missing_project_field(tmp_path):
    cfg_path = _write_config(tmp_path, "llm:\n  provider: claude_agent\n")
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_load_unknown_field_ignored(tmp_path):
    """未知字段不 fail（向后兼容需要）"""
    cfg_path = _write_config(
        tmp_path,
        """
        project: test
        future_feature_xyz: true
        """,
    )
    cfg = load_config(cfg_path)
    assert cfg.project == "test"


def test_load_invalid_yaml(tmp_path):
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    cfg = harness_dir / "config.yaml"
    cfg.write_text("project: [unclosed\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_config(cfg)


# ════════════════════════════════════════════════════════════════════
# find_config
# ════════════════════════════════════════════════════════════════════


def test_find_config_in_cwd(tmp_path, monkeypatch):
    cfg_path = _write_config(tmp_path, "project: test\n")
    monkeypatch.chdir(tmp_path)
    found = find_config()
    assert found == cfg_path


def test_find_config_from_subdir(tmp_path, monkeypatch):
    cfg_path = _write_config(tmp_path, "project: test\n")
    sub = tmp_path / "app" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    found = find_config()
    assert found == cfg_path


def test_find_config_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError):
        find_config()
