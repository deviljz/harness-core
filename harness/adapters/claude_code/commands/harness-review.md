---
description: 用独立 subagent 对比 diff 与 spec，找偏差
argument-hint: <spec-path>
---

审查当前 diff 是否符合 spec `$ARGUMENTS`。

## 执行步骤

1. 运行 `harness review-data --spec "$ARGUMENTS"`，stdout 是 JSON，含 `spec_content` / `diff_content` / `template`。
2. 按 template 把 spec 和 diff 塞进 prompt。
3. **必须**用 Agent 工具起 `general-purpose` subagent 送 prompt（红蓝隔离，不许自审）。
4. subagent 返回 JSON `{"consistent": true|false, "issues": [...]}`。支持裸 JSON 或 ```json ``` 包裹。
5. 输出：
   - `consistent: true` → 报"审查通过"
   - `consistent: false` → 按"文件:行号 - 问题"格式列出所有 issues
6. 不管成功失败，都追加到 `reports/review_<ts>.md`。

## 硬约束

- 禁止自己判断而不调 subagent
- subagent 必须拿完整 spec + diff，不允许 summarize
- `consistent: false` 必须至少一条具体 issue
