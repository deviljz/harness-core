---
description: 独立 subagent 审查 diff 是否符合 spec（Structure + User Flow + 数据源 + 集成测试）
argument-hint: <spec-path>
---

审查当前 diff 是否符合 spec `$ARGUMENTS`。

## 执行步骤

1. 运行 `harness review-data --spec "$ARGUMENTS"`，stdout 是 JSON，含 `spec_content` / `diff_content` / `template`。
2. **单 Pass 审查**（用 `template` 默认模板，已含 Structure + User Flow trace + 数据源 + 集成测试全套核对）：
   - 把 spec + diff 塞进 template 得到完整 prompt。
   - 用 Agent 工具起**全新** `general-purpose` subagent（禁止 SendMessage 续跑旧 agent，防止上下文污染）。
   - prompt 只包含 spec + diff + 模板文字，**禁止**附加本会话讨论过的结论 / 倾向 / 你自己的判断。
   - 返回 JSON `{"consistent": bool, "issues": [...]}`。
3. 输出：
   - `consistent: true` → 报"审查通过"
   - `consistent: false` → 按"文件:行号 - 问题"格式列出所有 issues
4. 追加到 `reports/review_<ts>.md`，记录 raw 返回。

## 历史说明（0.3.2 简化）

0.3.1 之前是 Pass A + Pass B 双 subagent。0.3.1 把 User Flow trace + 偷工 push-back + 数据源 trace 全部合并到 Pass A 模板，**Pass B 完全被 Pass A 覆盖**。0.3.2 删除 Pass B 流程，单 Pass 跑完所有维度，省 1 次 LLM 调用 + 时间。

## 硬约束

- 禁止自己判断而不调 subagent
- subagent 是**全新** session（每次新起 Agent，禁用 SendMessage）
- prompt 内**禁止**带当前会话讨论过的倾向性结论
- subagent 必须拿完整 spec + diff，不允许 summarize
- `consistent: false` 必须至少一条具体 issue
- 如 spec 无 User Flow 段或明确 "N/A"，模板里 Step 2 自动跳过（其他 Step 仍跑）
