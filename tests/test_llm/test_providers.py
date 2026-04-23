"""LLM provider 测试"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from harness.llm import get_provider, list_providers
from harness.llm.base import LLMError
from harness.llm.providers.claude_agent import ClaudeAgentProvider
from harness.llm.providers.manual import ManualProvider


def test_providers_registered():
    provs = list_providers()
    assert "claude_agent" in provs
    assert "manual" in provs


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider("nonexistent_xyz")


# ════════════════════════════════════════════════════════════════════
# ManualProvider
# ════════════════════════════════════════════════════════════════════


class TestManualProvider:
    def test_complete_reads_response_file(self, tmp_path):
        prov = ManualProvider({"dir": str(tmp_path), "timeout": 5, "poll_interval": 0.1})

        responses_dir = tmp_path / "manual_responses"

        def provide_response():
            # 模拟用户粘贴回复
            time.sleep(0.3)
            # 找刚写的 prompt 文件，对应写一个 response
            prompts_dir = tmp_path / "manual_prompts"
            for p in prompts_dir.glob("*.md"):
                (responses_dir / p.name).write_text("mocked reply", encoding="utf-8")
                return

        threading.Thread(target=provide_response, daemon=True).start()
        result = prov.complete("Hello LLM")
        assert result == "mocked reply"

    def test_timeout_raises(self, tmp_path):
        prov = ManualProvider({"dir": str(tmp_path), "timeout": 0.5, "poll_interval": 0.1})
        with pytest.raises(LLMError):
            prov.complete("Hello")

    def test_prompt_file_written(self, tmp_path):
        prov = ManualProvider({"dir": str(tmp_path), "timeout": 0.3, "poll_interval": 0.1})
        try:
            prov.complete("Test prompt content")
        except LLMError:
            pass
        prompts = list((tmp_path / "manual_prompts").glob("*.md"))
        assert len(prompts) == 1
        assert prompts[0].read_text(encoding="utf-8") == "Test prompt content"


# ════════════════════════════════════════════════════════════════════
# ClaudeAgentProvider (测试接口，没真调 Claude Code)
# ════════════════════════════════════════════════════════════════════


class TestClaudeAgentProvider:
    def test_is_registered(self):
        prov = get_provider("claude_agent")
        assert isinstance(prov, ClaudeAgentProvider)

    def test_file_io_roundtrip(self, tmp_path):
        prov = ClaudeAgentProvider({"dir": str(tmp_path), "timeout": 5, "poll_interval": 0.1})

        def provide_response():
            time.sleep(0.3)
            prompts_dir = tmp_path / "claude_prompts"
            resp_dir = tmp_path / "claude_responses"
            for p in prompts_dir.glob("*.md"):
                (resp_dir / p.name).write_text("agent reply", encoding="utf-8")
                return

        threading.Thread(target=provide_response, daemon=True).start()
        result = prov.complete("Ask Claude")
        assert result == "agent reply"

    def test_timeout_raises(self, tmp_path):
        prov = ClaudeAgentProvider({"dir": str(tmp_path), "timeout": 0.5, "poll_interval": 0.1})
        with pytest.raises(LLMError):
            prov.complete("Hello")
