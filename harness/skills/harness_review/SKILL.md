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

2. **构造 prompt**：上一步的 stdout 是 JSON，含 `spec_content` / `diff_content` / `template`。按 template 把 spec 和 diff 塞进去。

3. **起 subagent**：用你的 Agent tool（或等价机制）把 prompt 送给一个独立 subagent（`general-purpose` 类型）。

4. **解析回复**：subagent 会返回 JSON `{"consistent": true|false, "issues": [...]}`。支持裸 JSON 或 ```json 代码块包裹。

5. **输出结果**：
   - `consistent: true` → 简短报告"审查通过"
   - `consistent: false` → 列出所有 issues，按"文件:行号 - 问题"的格式
   - 把结果追加到 `reports/review_<ts>.md`（人话版）

## 硬约束

- 不允许自己"判"而不调 subagent（违反 harness 的红蓝隔离原则）
- subagent 必须拿到**完整的 diff 和 spec**，不能只 summarize
- `consistent: false` 时必须列出至少一条具体 issue

## 失败处理

- `harness review-data` 返回非 0：检查 spec 路径 / git 状态
- subagent 回复不是 JSON：重试一次，再不行就标记为 `parse_error` 交给用户
- 整体 review 依然要写进 `reports/review_<ts>.md`，哪怕失败
