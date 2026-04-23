"""ClaudeAgentProvider：通过 Claude Code 的 Agent tool 调用子 agent。

工作原理：
- 这个 provider 只在 Claude Code 会话里有效
- 它把 prompt 写到一个文件，然后告诉主 Claude "去调用 Agent tool，把这段 prompt 送进去"
- 具体的 Agent tool 调用由主 Claude 执行（因为 provider 代码本身不是 Claude）

简化版做法（v1）：不实际调 Agent tool，而是把 prompt 写到文件，留给外部处理。
真正在 Claude Code hook 场景下，主 Claude 会读取 prompt 文件、起 subagent、把回复写回。

这其实就是 ManualProvider 的一个变体，只是文件存放路径约定不同。
"""
from __future__ import annotations

import time
from pathlib import Path

from ..base import LLMError, LLMProvider


class ClaudeAgentProvider(LLMProvider):
    name = "claude_agent"

    def complete(self, prompt: str, context: dict | None = None) -> str:
        """
        当前 v1 实现：落盘等 Claude 处理。

        流程：
        1. 写 prompt 到 .harness/claude_prompts/<ts>.md
        2. 等待 .harness/claude_responses/<ts>.md 出现
        3. 读回内容返回

        主 Claude 看到 prompts 文件就应该主动起 subagent 处理它（配合 skill/CLAUDE.md 指令）。

        超时：默认 120 秒
        """
        timeout = self.config.get("timeout", 120)
        poll_interval = self.config.get("poll_interval", 1.0)

        root = Path(self.config.get("dir", ".harness"))
        prompts_dir = root / "claude_prompts"
        responses_dir = root / "claude_responses"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)

        ts = f"{int(time.time() * 1000):x}"
        prompt_file = prompts_dir / f"{ts}.md"
        response_file = responses_dir / f"{ts}.md"

        prompt_file.write_text(prompt, encoding="utf-8")

        # 轮询等待响应
        waited = 0.0
        while waited < timeout:
            if response_file.exists():
                content = response_file.read_text(encoding="utf-8")
                # 清理 prompt 文件（保留 response 供 audit）
                try:
                    prompt_file.unlink()
                except OSError:
                    pass
                return content
            time.sleep(poll_interval)
            waited += poll_interval

        raise LLMError(
            f"ClaudeAgentProvider: no response within {timeout}s. "
            f"Prompt at {prompt_file}. "
            f"Write response to {response_file} or switch provider to 'manual'."
        )
