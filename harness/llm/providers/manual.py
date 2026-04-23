"""ManualProvider：人工把 prompt 粘到任意 AI，把回复粘回来。

使用流程：
1. harness 调 complete(prompt)
2. prompt 写到 .harness/manual_prompts/<ts>.md
3. 命令行打印一条提示："请把该文件内容粘给你的 AI，把回复保存为 .harness/manual_responses/<ts>.md"
4. harness 轮询 response 文件
5. 用户完成后，complete() 读取 response 返回

适合：Hermes / ChatGPT 网页版 / 本地 LLM / 任何没 API 的 AI 工具
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from ..base import LLMError, LLMProvider


class ManualProvider(LLMProvider):
    name = "manual"

    def complete(self, prompt: str, context: dict | None = None) -> str:
        timeout = self.config.get("timeout", 600)  # 默认给 10 分钟
        poll_interval = self.config.get("poll_interval", 2.0)

        root = Path(self.config.get("dir", ".harness"))
        prompts_dir = root / "manual_prompts"
        responses_dir = root / "manual_responses"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)

        ts = f"{int(time.time() * 1000):x}"
        prompt_file = prompts_dir / f"{ts}.md"
        response_file = responses_dir / f"{ts}.md"

        prompt_file.write_text(prompt, encoding="utf-8")
        print(
            f"\n[harness] 需要 LLM 判断。请：\n"
            f"  1. 复制 {prompt_file} 内容\n"
            f"  2. 粘贴到你的 AI（ChatGPT / Hermes / 本地 LLM 皆可）\n"
            f"  3. 把 AI 的回复保存为 {response_file}\n"
            f"  4. harness 会轮询自动读取（超时 {timeout}s）\n",
            file=sys.stderr,
        )

        waited = 0.0
        while waited < timeout:
            if response_file.exists():
                content = response_file.read_text(encoding="utf-8")
                return content
            time.sleep(poll_interval)
            waited += poll_interval

        raise LLMError(
            f"ManualProvider: no response within {timeout}s. "
            f"Prompt at {prompt_file}, expected response at {response_file}."
        )
