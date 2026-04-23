---
description: 用 harness 为新任务写 spec（6 段 + complexity）
argument-hint: <task-name>
---

为任务 `$ARGUMENTS` 写 harness spec。

## 执行步骤（必须按顺序）

1. 运行 `harness plan new "$ARGUMENTS"` 生成骨架，记录输出路径。
2. 打开生成的文件，按 6 大区逐个引导用户填写：
   - **Objective**：一句话目标 + 可验证的成功标准
   - **Commands**：需要跑的命令（测试/构建/lint）
   - **Structure**：涉及的文件/模块列表
   - **Style**：编码规范（如有特殊要求）
   - **Testing**：测试策略（单元/集成/E2E）
   - **Boundaries**：非目标（绝不做什么）
3. 问用户 `complexity: simple | complex`：
   - 1-2 文件 / 单模块 → simple
   - 跨模块 / 改架构 / 改 DB → complex
4. 运行 `harness plan validate <path>`，不过就修到过。
5. 告诉用户下一步：`/harness-execute <path>`

## 硬约束

- 每段填完立即写入文件（增量更新）
- Boundaries 必须列具体项，不允许空/模糊
- validate 不通过不能结束
