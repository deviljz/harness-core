---
name: thin-orchestrator
description: 在同一个主对话里连续处理多个 bug、UI 微调或小功能时，让主线程只当“薄总控”，把每条任务隔离派给干净子 Agent，并用 `python -m harness task` 硬校验状态、改动文件边界与验收标准。避免主对话上下文膨胀变傻，也避免用户频繁手动开新对话。
---

# 薄总控与按单隔离（不让用户当人肉路由器）

当用户在**同一个对话**里连续推进多条 bug、多个 UI/动效微调或多个小功能时，主对话必须保持极轻，**把脏活和上下文隔离交给干净子 Agent，把状态和防撞车交给 `python -m harness task`**。

## 1. 主线程边界：只做调度与汇总，不亲自下场啃脏活

- **以下重活一律派给全新干净的子 Agent**（零历史污染，严格守对应 Skill）：
  - 翻大量日志、跨文件查因（给子 Agent `bug-investigation` 要求）
  - 修改业务代码、跑编译/打包/回归验证（给子 Agent `existing-flow-review` 或 `web-prototype-to-unity` 要求）
  - 大规模截图对比、资源扫描
- 主线程只保留：用户目标、任务总板摘要、每条任务 5～10 行回执、以及需要用户拍板的取舍。**不把长日志、整段源码或十轮轮询过程留在主对话。**
- 只有 30 秒内能一眼看清的极小查询/单行改动才由主线程顺手做（遵守 `COST-AWARE-DELEGATION-v1`）。

## 2. 所有任务统一走本地任务板 `python -m harness task`（硬校验防敷衍）

1. **先登记再派发**：
   ```powershell
   python -m harness task add QA72 "英语环境下出现中文提示" --kind bug
   python -m harness task brief QA72   # 生成精简子 Agent 任务包
   ```
2. **收到子 Agent 回执后立刻落盘**（由 CLI 硬校验，缺字段直接报错）：
   ```powershell
   python -m harness task update QA72 --verdict need_fix --fact "SilentDownloadVM.cs:794 硬编码中文提示" --files "client/Assets/.../SilentDownloadVM.cs" --verify "切英语触发未初始化提示，确认走多语言表"
   ```
   - `need_fix` **必须**同时提供 `--fact`、`--files`、`--verify`；
   - `blocked_external` **必须**通过 `--note` 写明缺哪项本机测不了的外部条件。
3. **派子 Agent 修代码前先标 `fixing` 防撞车**：
   ```powershell
   python -m harness task update QA72 --status fixing --owner subagent
   python -m harness task brief QA72 --mode fix
   ```
   - 如果两条并行任务改到**同一个文件**，CLI 会直接报错拦截，必须等前一条改完 `done` 再派后一条；不重叠文件的单子可以放心**一边派子 Agent 修旧单、一边派新子 Agent 查下一单**。
4. **修完验收通过后收口**：
   ```powershell
   python -m harness task update QA72 --status done --verdict done --fact "已改用多语言 key，英语实测通过"
   ```

## 3. 调用外部 CLI（如 Kimi）的纪律

- 交给 Kimi CLI 等外部工具时，同样传 `python -m harness task brief <id>` 的紧凑模板（明确只读、限 10 行结构化回执）。
- 等待后台任务期间**不要连续刷屏发十条碎片进度消息**；等结果回来后一次核对并录入任务板再汇总。

## 4. 向用户汇报：只给一张 3 秒能看懂的总表

- 每次阶段汇报直接给紧凑总表（或贴 `python -m harness task list` 摘要）：`编号 | 状态 | 定性 | 一句话结论 | 等你拍板什么`。
- 凡标 `确认需改代码` 的条目，明确问用户“直接派子 Agent 修，还是先放着”。
- `.harness/handoff.md` 只在真的跨天/换大阶段时覆写精简为 **≤60 行**；多条任务的明细由 `.harness/tasks.json` / `.harness/tasks.md` 接管，禁止往 `handoff.md` 无限追加流水账。
