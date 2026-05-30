---
name: harness-review
description: 用 harness-core 框架审查当前 diff 是否符合对应 spec 文档。触发：用户说 /harness-review 或 "review this change against spec"。
---

# harness-review skill

这个 skill 让 AI 拿 harness-core 打包好的 prompt 去自己起 subagent 审查代码改动。

## 何时触发

- 用户显式调用 `/harness-review`
- 用户说"审查这次改动" / "review this change against spec"
- `harness check --gate` 失败后想诊断为什么

## 执行步骤

1. **拿打包数据**：运行
   ```bash
   harness review-data --spec <spec.md>
   ```
   （如果用户没指定 spec，问他：`docs/tasks/` 下哪份 spec 对应本次改动？）

2. **构造 prompt**：上一步的 stdout 是 JSON，含 `spec_content` / `diff_content` / `template`。按 template 把 spec 和 diff 塞进去。模板已含 Structure + User Flow trace + 数据源 + 集成测试全套核对（**单 Pass** 跑完所有维度）。

3. **起 subagent**：用你的 Agent tool（或等价机制）把 prompt 送给一个**全新**独立 subagent（`general-purpose` 类型，**必须显式 `model="sonnet"`**——不传默认 Opus 烧钱 5x；review 是语义判断，sonnet 足够）。禁止 SendMessage 续跑旧 agent，防止上下文污染。prompt 只包含 spec + diff + 模板文字，**禁止**附加本会话讨论过的结论 / 倾向 / 你自己的判断。

4. **解析回复**：subagent 会返回 JSON `{"consistent": true|false, "issues": [...]}`。支持裸 JSON 或 ```json 代码块包裹。

5. **输出结果**：
   - `consistent: true` → 简短报告"审查通过"
   - `consistent: false` → 列出所有 issues，按"文件:行号 - 问题"的格式
   - 把结果追加到 `reports/review_<ts>.md`（人话版）

## 硬约束

- 不允许自己"判"而不调 subagent（违反 harness 的红蓝隔离原则）
- subagent 是**全新** session（每次新起 Agent，禁用 SendMessage）
- prompt 内**禁止**带当前会话讨论过的倾向性结论
- subagent 必须拿到**完整的 diff 和 spec**，不能只 summarize
- `consistent: false` 时必须列出至少一条具体 issue
- 如 spec 无 User Flow 段或明确 "N/A"，模板里相应 Step 自动跳过（其他 Step 仍跑）

## 失败处理

- `harness review-data` 返回非 0：检查 spec 路径 / git 状态
- subagent 回复不是 JSON：重试一次，再不行就标记为 `parse_error` 交给用户
- 整体 review 依然要写进 `reports/review_<ts>.md`，哪怕失败

## 历史说明（0.3.2 简化）

0.3.1 之前是 Pass A + Pass B 双 subagent。0.3.1 把 User Flow trace + 偷工 push-back + 数据源 trace 全部合并到 Pass A 模板，**Pass B 完全被 Pass A 覆盖**。0.3.2 删除 Pass B 流程，单 Pass 跑完所有维度，省 1 次 LLM 调用 + 时间。
