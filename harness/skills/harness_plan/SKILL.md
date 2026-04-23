---
name: harness-plan
description: 用 harness-core 模板为新任务生成 6 大区 spec 骨架并引导填写。触发：用户说 /harness-plan <task> 或 "为 X 写 spec"。
---

# harness-plan skill

## 何时触发

- 用户显式 `/harness-plan <task-name>`
- 用户说"开始新任务之前先写 spec" / "给 X 写 spec"
- 用户提出一个**需求**但没写 spec 文档

## 执行步骤

1. **生成骨架**：
   ```bash
   harness plan new "<task-name>"
   ```
   输出会打印生成路径（如 `docs/tasks/20260422_task_name.md`）。

2. **引导填写**：逐一帮用户填 6 大区（Objective / Commands / Structure / Style / Testing / Boundaries）+ **complexity** 字段。
   - 问封闭问题，不让用户自由发挥（比如"目标用户是谁？"比"介绍一下这个任务"好）
   - 每个区填完就写入文件，增量更新

3. **校验**：
   ```bash
   harness plan validate <spec_path>
   ```
   不通过就修到通过。

4. **确认 complexity**：
   - 只动 1-2 个文件 / 单模块内 → **simple**
   - 跨多个模块 / 改架构 / 改数据库 → **complex**
   - 有疑问就跟用户确认

## 硬约束

- spec 没过 validate 不能开工
- 填写过程要把"非目标"（Boundaries 的"绝不做"）明确列出，不允许模糊
- 不允许偷懒用"通用目标"代替"可验证的成功标准"
