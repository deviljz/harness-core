---
description: 跑 harness 自我验证 fixture（regression + template-test），看 review 能力是否回归
argument-hint: [--fixture=NNN] [--case=NN]
---

跑 harness-core 的 self-verify fixture，在 Claude Code 进程内调真实 LLM（绕过 CLI 外部 claude_agent timeout）。

## 执行步骤

### 第 1 步：拿 fixture 列表
跑 `harness verify run --json --dry-run` 输出含每个 fixture 的：
- spec_content / diff_content（来自 worktree 与空 baseline 的 git diff）
- expected.json（consistent / required_keywords / soft_keywords / min_issues_count）
- subagent_report（如有）

解析 JSON 拿 fixture 列表。

### 第 2 步：每个 fixture 起独立 subagent 跑 review
对每个 fixture：

1. 用 `harness/review/prompt_template.md` 当前版本 + 该 fixture 的 spec_content + diff_content 组装完整 prompt
2. 用 Agent 工具起**全新** general-purpose subagent，subagent_type=general-purpose，model=sonnet
3. prompt 末尾加："**严格按模板审，输出 JSON `{\"consistent\": ..., \"issues\": [...]}`，不要附加任何解释**"
4. 收集 subagent 返回的 JSON

### 第 3 步：matcher 对比 expected
对每个 fixture 的实际 review 结果 vs expected：

```python
# 等价伪代码（实际用 Bash/Python 执行）
all_issue_text = " ".join(actual["issues"])
required_caught = sum(1 for kw in expected["required_keywords"] if re.search(kw, all_issue_text, re.I))
soft_caught = sum(1 for kw in expected["soft_keywords"] if re.search(kw, all_issue_text, re.I))

passes = (
    actual["consistent"] == expected["consistent"]
    and required_caught == len(expected["required_keywords"])
    and soft_caught >= len(expected["soft_keywords"]) * 0.5
    and len(actual["issues"]) >= expected.get("min_issues_count", 1)
)
```

### 第 4 步：输出 PASS/FAIL 表格

```
=== Regression Fixtures ===
001_settings_check_update_missing   PASS  required 1/1, soft 2/3
002_download_url_relative           PASS  required 1/1, soft 2/3

=== Template-test Cases ===
case_01_happy_path                  PASS  consistent=true (expected true)
case_02_ui_skipped                  PASS  required 1/1, soft 2/2
...

Total: 7 PASS / 0 FAIL  | Recall: 7/7 = 100%
```

### 第 5 步：失败时汇报
任一 fixture FAIL 时：
- 列出 fixture 名 + 期望 vs 实际差异
- 给改 prompt_template.md 的具体建议（缺哪个 keyword 类型）
- exit 视为 review 模板回归，**禁止 commit harness 改动**

## TDD 红绿铁律（必读）

**改 review 模板 / 规则前**：
1. 先确认目标 fixture 当前会 FAIL（RED）— 跑一次 verify 看现状
2. 改完模板 / 规则
3. 再跑同一 fixture 确认变 PASS（GREEN）
4. **不能跳过 RED step** — 否则没法证明改动真有效

具体步骤：
```
# 1. RED: 在改之前
/harness-verify --fixture=001  # 看是不是 FAIL（如果已 PASS 说明问题不在这）

# 2. 改 harness/review/prompt_template.md（或其他文件）

# 3. GREEN: 改完
/harness-verify --fixture=001  # 验证变 PASS
```

## 硬约束

- subagent 必须**独立** session（每次新起 Agent，禁用 SendMessage 续跑）
- subagent prompt 不能附带本会话讨论过的倾向（spec + diff + 模板文字而已）
- LLM 非确定 → 同一 fixture 出现单次 FAIL 时**重试 1 次**，2 次都 FAIL 才算真 FAIL
- 跑全套 7 fixture 大约消耗 7 次 LLM 调用 + 5-10 分钟（每次 review 1-2 分钟）

## 何时该用

- 改 `harness/review/prompt_template.md` 前后（验证红绿）
- 升级 harness-core 版本前（看 recall 是否回归）
- 沉淀新生产 bug 到 `tests/fixtures/regression/00X/` 后（验证当前版本能 catch）
