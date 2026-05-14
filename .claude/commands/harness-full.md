---
description: 一条龙跑完 harness：execute → check → review → commit，全程无人工介入
argument-hint: <spec-path>
---

按 spec `$ARGUMENTS` **自动跑完整链**，全程不询问用户，失败时停下来汇报。

## 执行步骤

### 第 0 步：登记任务（必须最先做）
在启动任何 subagent 之前，**立即**调用以下逻辑把所有待完成步骤写入 `.harness/active_tasks.json`：

```python
# 伪代码——用 Bash 工具执行等价操作
import json, pathlib
data = {"pending": ["execute", "check", "review", "commit"], "completed": []}
pathlib.Path(".harness").mkdir(exist_ok=True)
pathlib.Path(".harness/active_tasks.json").write_text(json.dumps(data, indent=2))
```

或直接用 Write 工具写入 `.harness/active_tasks.json`：
```json
{"pending": ["execute", "check", "review", "commit"], "completed": []}
```

**不写这个文件 → Stop hook 会误放行 → 流程会提前终止。**

### 第 1 步：execute
按 `.claude/commands/harness-execute.md` 的规则跑：
- 读 spec，确认 complexity
- complex → 每个执行项起独立 subagent（Agent 工具，subagent_type=general-purpose）
- 按 Structure 区列出的文件逐项改
- PostToolUse hook 自动跑 `harness check --on-edit` 增量验证
- 单个 hook fail → **当场自修**，不打断流程
- **execute subagent 完成后立即**：把 `execute` 从 pending 移到 completed（更新 active_tasks.json）

#### 偷工模式 push-back（强制）
subagent 完成后**必须**扫描其报告文字，命中以下任一模式即视为"未完成 spec 要求"，必须**重起 subagent 续做**而非视为通过：

- 「**先跳过 UI 入口** / 先不做 UI / UI 入口暂时不加 / UI 留后续」
- 「**留 service API 可调** / 留接口给后续 / 暂未接入 UI」
- 「**主动触发暂时不做** / 主动按钮暂时跳过 / 仅留 service / 仅留 API」
- 「**先实现核心逻辑**（暗示 UI / 触发点没做）」
- 「**X 没有就跳过** / 找不到 X 就略过」（如 spec 要求改某文件但实际跳过）

唯一豁免：subagent 报告**明确说明**为什么 spec 该要求不可实现（如"spec 写要改 file X 但文件不存在且 spec 无创建说明"），并且**主 AI 必须复核**该解释合理才能放行。

push-back 时给 subagent 的 prompt 模板：
```
你上次的报告里出现「先跳过 UI 入口」等措辞，但 spec 第 X 段明确要求 <具体功能>。
请补做：<具体要求>。完整实现，不要再跳过。
```

### 第 2 步：check（全量）
所有改动完成后，运行 `harness check`，解析 XML 报告：
- `all_green="true"` → 把 `check` 从 pending 移到 completed → 进入第 3 步
- 有 fail → 读 raw_output 定位根因 → **自修一次** → 重跑
- 连续 2 次失败 → 把 `check` 保留在 pending → **清空 active_tasks.json（`{"pending":[],"completed":[]}`)** → 停下来汇报

### 第 3 步：review
按 `.claude/commands/harness-review.md` 的规则跑：
- `harness review-data --spec "$ARGUMENTS"` 拿 JSON
- 起新的 subagent 跑单 Pass 审查（模板含 Structure + User Flow trace + 数据源 + 集成测试全套核对）
- 返回 JSON：
  - `consistent: true` → 把 `review` 从 pending 移到 completed → 进入 commit
  - `consistent: false` → **清空 active_tasks.json** → 停下来列出所有 issues，不进入 commit

### 第 4 步：commit
全部绿后：
- `git status` 看改动
- 当前必须在 dev 分支（按 [[feedback_git_workflow]] 规则）
- 写 commit message：`feat: 完成 spec <spec-名>` + spec 里 Objective 段一句话摘要
- `git add` 仅 spec 列出的 Structure 文件 + 测试文件 + spec 本身（不要 add 未追踪的临时文件）
- commit 到 dev（不 push，让用户决定是否 push）
- **commit 成功后**：把 `commit` 从 pending 移到 completed，**清空 active_tasks.json**（`{"pending":[],"completed":[]}`）

### 第 5 步：汇报
最后打印：
- ✅ spec 名 + 4 步全绿
- 改动文件清单
- 提示：「dev 分支已 commit，未 push。需要的话跑 `git push origin dev`」

## 失败汇报格式

任一步骤失败立刻停下来，输出：

```
❌ harness-full 在第 X 步失败：<execute / check / review / commit>

失败详情：
<具体的 fail test / issue / git 错误>

已完成：
- 第 1 步：✅/❌
- 第 2 步：✅/❌
- 第 3 步：✅/❌

建议下一步：
<人工修复点的具体提示>
```

## 硬约束

- **全程不问用户**：不弹 AskUserQuestion、不调 EnterPlanMode
- **第 0 步必须最先做**：在任何 subagent 之前写好 active_tasks.json，否则 Stop hook 无法正确工作
- **subagent 完成后禁止输出 final text**：立即更新 active_tasks.json，然后直接起下一个 subagent
- check / review 失败时**不要继续往后跑**，并清空 active_tasks.json 再汇报
- commit 前必须验证 dev 分支
- subagent 必须独立起新会话（不复用 SendMessage）
- 每步 fail 自修上限 1 次，超过就停
- **active_tasks.json 格式固定**：`{"pending": [...], "completed": [...]}`，不要加其他字段

## 何时该用

- spec 已经写好且 deviljz 确认过（plan 阶段已通过）
- 一次性想跑完一个或多个需求 section
- 信任 AI 在 fail 时停下来汇报，而不是糊弄过去
