---
name: harness-baseline
description: Audit coverage gap against a reference implementation. Use when an Objective targets aligning with an existing tool/site/app (URL or local HTML). Writes gap table into spec.md.
trigger:
  keywords:
    - 对标
    - 对齐
    - 对照
    - aligned with
    - compatible with
    - parity with
    - vs UWA
    - vs GraphyPro
  requires_url_in_objective: true
---

# harness-baseline

对标场景（mirror/parity tool development）的 `harness-plan` 前置 skill。

**Why this exists**: 对标类工具开发，工程师视角"已实现 X 模块"，但用户视角"功能缺一半" — 因为没有强制流程把"对照参考实现列功能点"放入 plan 阶段。本 skill 把这步自动化。

## When triggered

`harness-plan` 解析 Objective 第一段时，检测：
- 触发词（见 frontmatter `trigger.keywords`）
- Objective 中含 URL 或本地 HTML 路径

→ 自动调用 `harness baseline scan` 并把结果写入 spec.md。

用户也可手动：
```
/harness-baseline <source-url-or-html-path>
```

## What it does

1. **Scan baseline**: 抓取参考实现 sidebar / menu / nav 的树形结构（页面 → 子项 → 关键 metric/table 列）
2. **Scan target**: 同样抓当前实现
3. **Gap diff**: 三态分类
   - ✓ aligned（同名同位置）
   - 🟡 partial（同名但缺 sub-metric / columns）
   - ❌ missing（baseline 有 target 没有）
4. **Write spec**: 在 spec.md 末尾追加"## 覆盖度差距 (baseline: <source>)"小节，markdown 表 + 三态计数

## Inputs

| flag | required | desc |
|---|---|---|
| `--source <url\|path>` | yes | 参考实现 URL 或本地 HTML 路径 |
| `--target <path>` | yes | 当前实现 HTML / 入口文件 |
| `--spec <path>` | no | 要写入 gap 小节的 spec.md（不传只输出 stdout） |
| `--sidebar-selector <css>` | no | 自定义 sidebar CSS selector（不传自动检测） |
| `--fuzzy-threshold <0.0-1.0>` | no | partial 匹配阈值，默认 0.6 |

## Output

stdout (markdown):
```
== Baseline Coverage Audit ==
Source: <url>
Target: <path>

Aligned (✓ 15): 性能简报 / 场景概览 / ...
Partial (🟡 7): 运行信息 (缺 CPU 频率 / Big Jank Cards) / ...
Missing (❌ 9): GPU 指标汇总 / 各线程CPU调用堆栈 / ...

→ Spec written: ./spec.md (section: 覆盖度差距)
```

spec.md (追加小节):
```markdown
## 覆盖度差距 (baseline: <source>, scanned: 2026-05-23)

| 大类 | 子项 | 参考 | 当前 | 状态 |
|---|---|---|---|---|
| GPU 分析 | 指标汇总 | UWA: ... | ❌ 无 | ❌ |
...

**Counts**: ✓ 15 / 🟡 7 / ❌ 9

**Action**: 此处列出的 missing/partial 项必须在 §7 Boundaries 显式声明"不做"（带 reason），或在后续 milestone 实现。
```

## Limits (MVP)

- 仅本地 HTML（URL 模式用 `playwright` extras：`pip install harness-core[playwright]`）
- 一层 sidebar 展平（树形深度 ≥2 截断到 leaf，后续支持）
- 文本匹配：normalize + 子串 + Levenshtein（fuzzy_threshold）

## Examples

### 例 1: Periscope 对标 UWA
```bash
harness baseline scan \
  --source ./reference/uwa_report.html \
  --target ./Library/PeriscopeDevicePulls/.../framelog.bin.html \
  --spec ./harness/specs/20260523_periscope-uwa-align.md
```

### 例 2: 喵辅导对标 GraphyPro
```bash
harness baseline scan \
  --source https://graphy.pro/dashboard \
  --target ./apps/web/src/pages/dashboard.html \
  --spec ./specs/dashboard-parity.md
```

## Reference RFC

See RFC: `docs/rfcs/harness-baseline.md`（待提；附在本 PR）
