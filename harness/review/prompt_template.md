# Review Task

You are a senior engineer reviewing a code change against its specification.

## Specification (the source of truth)

{spec_content}

## Code Change (diff)

```diff
{diff_content}
```

## Your Task

Check whether the code change:
1. Implements what the spec says
2. Doesn't violate the spec's boundaries (绝不做 section)
3. Matches the spec's testing and style requirements
4. **Data compatibility**: 改动是否引入新字段 / 新枚举值 / 新过滤条件？如有，是否配套了回填策略或对老数据的显式兼容？典型盲区例子：
   - 加 `kind` 列 + API 按 `WHERE kind='X'` 过滤 → 老数据 kind=NULL 全部被排除掉
   - 新增 enum 值 → 老数据用旧值，反序列化时可能崩
   - schema 加 NOT NULL 字段 → 老行没填会失败
   若 spec 有 Data Migration 段，校验迁移策略是否真在 diff 中体现（grep migration SQL / startup hook / 回填脚本）；若无 Data Migration 段或写 N/A，但 diff 实际涉及上述场景 → 报偏差。

## 严格核对步骤（必做，先做这一步再下结论）

1. 列出 spec "## 4. Structure（目录/模块）" 段所有提到的文件路径
2. 对每个文件：
   - 用 Bash + `git ls-files <path>` 验证文件**在工作树存在**（不是只看 diff）
   - 如果文件存在 + diff 没显示 = 可能 diff 截断了，**不要直接报"未实现"**
   - 用 Read 工具看文件实际内容，检查是否实现了 spec 要求的功能
3. 只有文件**真的不存在** 或 内容**真的与 spec 不符** 才作为 issue
4. diff_content 是参考，**工作树状态是真相**

允许工具：Bash、Grep、Read、Glob

Respond **only** in this format:

```json
{{"consistent": true|false, "issues": ["issue1", "issue2"]}}
```

- `consistent: true` means the change fully implements what spec asks without violating boundaries.
- `consistent: false` means there's at least one deviation. List each in `issues`.
- Keep `issues` short and specific (one sentence each, point to file:line when possible).

Focus: {focus}
