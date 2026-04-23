# Generic Adapter: 在非 Claude Code 环境使用

如果你用 Hermes / Cursor / Gemini CLI 等工具（它们没有 Claude Code 的 hook 机制），harness-core 仍然可用，只是需要让 AI 自己调 harness 命令。

## 做法

1. 在项目的 AI 规则文件（如 `.cursorrules` / `GEMINI.md` / Hermes system prompt）里加：

> **Harness 纪律**
>
> - 每次修改代码文件后，必须立即运行：
>   `harness check --on-edit <改动文件路径> --warn-only`
> - 想说"完成"前，必须运行：
>   `harness check`
>   然后运行：
>   `harness check --gate`
>   只有 gate 放行才能说"完成"。
> - 若 gate 拦住你，先修复问题再尝试。紧急情况可用：
>   `harness check --skip-gate --reason "理由"`
>   （会记入 reports/skipped.log）

2. 如果 AI 没 subagent 能力但你需要 review 层：把 `.harness/config.yaml` 里的 `llm.provider` 改成 `manual`，harness 会打印 prompt 到文件，你手动粘给任意 AI 再把回复粘回来。

3. 如果 AI 连 shell 都不能跑，你自己手动在项目里执行 `harness check`，把输出粘给 AI 作反馈。
