"""加载和校验 .harness/config.yaml。

设计原则：
- pydantic 做 schema 校验，config 合法性在入口就挂掉
- 未知字段宽容（方便老 config 兼容新版本）
- 路径字段一律转 PurePosixPath 规范化
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


# ════════════════════════════════════════════════════════════════════
# Schema 定义
# ════════════════════════════════════════════════════════════════════


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str = "claude_agent"


class CircuitBreakerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    max_retries: int = 3
    same_error_limit: int = 2
    on_trigger: str = "pause_and_notify"


class IncrementalCacheConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = True
    debounce_seconds: int = 30
    skip_if_hash_unchanged: bool = True


class PlanConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    spec_dir: str = "docs/tasks"
    template: str = "default"
    require_complexity_field: bool = True


class ExecuteConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    complexity_source: str = "spec_field"


class ReviewConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = True
    focus: list[str] = Field(default_factory=list)


class TargetConfig(BaseModel):
    """一个多语言项目里的一个 target（如 backend/mobile/web）"""
    model_config = ConfigDict(extra="allow")
    name: str
    root: str
    language: str = "fallback"
    test_paths: list[str] = Field(default_factory=list)
    ignore_paths: list[str] = Field(default_factory=list)
    core_modules: list[str] = Field(default_factory=list)
    checks: dict = Field(default_factory=dict)


class GateConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    require_evidence: bool = True
    evidence_source: str = "harness_report"
    max_age_seconds: int = 300


class HarnessConfig(BaseModel):
    """顶层 config"""
    model_config = ConfigDict(extra="allow")
    project: str
    llm: LLMConfig = Field(default_factory=LLMConfig)
    ignore_paths_global: list[str] = Field(default_factory=list)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    incremental_cache: IncrementalCacheConfig = Field(default_factory=IncrementalCacheConfig)
    plan: PlanConfig = Field(default_factory=PlanConfig)
    execute: ExecuteConfig = Field(default_factory=ExecuteConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    targets: list[TargetConfig] = Field(default_factory=list)
    gate: GateConfig = Field(default_factory=GateConfig)


# ════════════════════════════════════════════════════════════════════
# 加载入口
# ════════════════════════════════════════════════════════════════════


class ConfigError(Exception):
    """配置相关错误的统一异常"""


def find_config(start: Path | None = None) -> Path:
    """从当前目录向上找 .harness/config.yaml。

    返回配置文件的绝对路径。找不到就 raise ConfigError。
    """
    cur = (start or Path.cwd()).resolve()
    for parent in [cur] + list(cur.parents):
        candidate = parent / ".harness" / "config.yaml"
        if candidate.is_file():
            return candidate
    raise ConfigError(
        f"No .harness/config.yaml found in {cur} or any parent directory. "
        "Run `harness init` first."
    )


def load_config(path: Path | None = None) -> HarnessConfig:
    """加载并校验 config。path 为 None 时自动查找。"""
    cfg_path = path or find_config()
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    try:
        return HarnessConfig(**raw)
    except Exception as e:
        raise ConfigError(f"Invalid config at {cfg_path}: {e}") from e


def project_root(config_path: Path) -> Path:
    """config 所在 .harness 目录的父目录 = 项目根"""
    return config_path.parent.parent.resolve()
