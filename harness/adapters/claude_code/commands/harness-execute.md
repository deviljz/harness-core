---
description: 按 harness spec 逐项执行实现
argument-hint: <spec-path>
---

按 spec `$ARGUMENTS` 执行实现。

## 执行步骤

1. 读 `$ARGUMENTS`，确认 complexity 字段：
   - **simple** → 直接在当前会话实现
   - **complex** → 为每个执行项起 subagent（通过 Agent 工具）
2. 运行 `harness execute "$ARGUMENTS"` 解析执行表（若存在）。
3. 按 Structure 区列出的文件逐项改动。每改完一个文件：
   - 自动有 PostToolUse hook 跑 `harness check --on-edit` 验证
   - 若 hook 报 fail → 先修再继续下一项
4. 全部实现后让用户跑 `/harness-review $ARGUMENTS` 审查。

## 硬约束

- 不允许偏离 spec 的 Boundaries（非目标）
- 每个执行项必须映射到 spec 的某一段
- complex 任务必须用 subagent 隔离，避免污染主上下文
- **TDD 红绿铁律**：每个执行项按 spec §6「RED → GREEN → REFACTOR」严格顺序：
  1. subagent 先按 §6 测试矩阵写测试代码
  2. **跑测试确认 FAIL（RED）** — 报告中必须贴 pytest/flutter test 错误输出作为证据
  3. **独立 commit**：`test(scope): RED for <feature>`
  4. 再写实现代码
  5. 跑测试确认 PASS（GREEN）— 贴证据
  6. **独立 commit**：`feat(scope): implement <feature>`
  7. 若需要重构，在测试全绿下做（REFACTOR），独立 commit `refactor:`
- subagent 报告若缺 RED 失败证据 = 跳了 RED step，主 AI 必须 push-back 重做
