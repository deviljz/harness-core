---
name: harness-visual-audit
description: Run DOM/visual assertions on a rendered UI (HTML report / web app). Use after implementation to catch tooltip leakage, color palette violations, table alignment issues, missing units, low contrast, cross-page inconsistency. Triggers when objective mentions audit/verify rendered UI or when called explicitly via /harness-visual-audit.
trigger:
  keywords:
    - 视觉审计
    - visual audit
    - chart hover audit
    - 报告审计
    - UI 巡检
    - DOM 断言
  requires_html_target: true
---

# harness-visual-audit

UI 工程开发完后跑 DOM/视觉断言，对应 RFC `docs/visual_audit_assertions.md` 的 6 大类断言 MVP。

**Why this exists**: 代码改完后即使编译过 + baseline 覆盖度对了，UI 渲染的"颜色不一致 / hover 串入无关字段 / 单位标错"等 bug 仍要靠用户截图反馈。视觉断言把这步自动化。

## When triggered

- 用户显式 `/harness-visual-audit <html-path-or-url>`
- objective 含触发词（见 frontmatter `trigger.keywords`）+ HTML target

## What it does

1. **Load target**: chrome MCP / playwright 加载 HTML 报告或 URL
2. **Run assertions**: 按 config (默认 6 项 MVP) 跑 DOM 断言
   - A1-1: tooltip 不串入无关字段
   - A1-2: 非曲线图 mousemove 隐 global tooltip
   - A2-1: 颜色调色板限制
   - A2-2: 同 chart 多线 hue 差 > 30°
   - A3-1: 表格 td.num 对齐统一
   - A4-1: 数值列必须标单位
3. **Output**: markdown report + 失败明细 (selector + 实际 vs 期望)
4. **Exit code**: 0 全通过 / 1 有 fail / 2 加载失败

## Inputs

| flag | required | desc |
|---|---|---|
| `--target <url\|path>` | yes | HTML 报告或 URL |
| `--config <yaml>` | no | 断言开关 + 业务参数（颜色调色板 / chart selector / forbidden keywords） |
| `--charts <selector,...>` | no | 限定 chart selector 范围（默认 svg.chart） |
| `--report <out-path>` | no | 报告输出路径 markdown |
| `--fail-on <warn\|error>` | no | 哪种严重度退出非零（默认 error） |

## Output

stdout (默认 markdown):
```
== Visual Audit Report ==
Target: <html-path>
Charts scanned: 21
Total assertions: 84

✓ PASS: 78
✗ FAIL: 6

[A1-1] chartMemGfx hover 不串入无关字段
  fail: tooltip 含 'frameMs = 33.05'
  selector: #chartMemGfx
  remediation: 在 chart preset 用 label='' + fmt 自定义只输出当前曲线
  
[A2-2] chartMemTotal 3 线 hue 差 > 30°
  fail: TotalUsed (#79c0ff h=210) vs SystemUsed (#5aaad7 h=200) hue diff = 10°
  remediation: 改 SystemUsed 为对比色相 (建议 #7ee787 / #ec4899 / #ffa657)
```

## Limits (MVP)

- 静态 HTML 模式（用 playwright，必需）
- URL 模式同样需 playwright + chromium install
- 6 项断言（P0 3 + P1 3），后续 PR 加 A5（对比度）+ A6（跨页一致性）

## Examples

```bash
# 跑 Periscope 报告
harness visual-audit \
  --target ./Library/PeriscopeDevicePulls/.../framelog.bin.html \
  --config ./visual_audit_periscope.yaml \
  --report ./audit_report.md

# 用默认配置跑（无业务侧配置文件）
harness visual-audit --target ./report.html
```

## Config schema

```yaml
# visual_audit_periscope.yaml
charts_selector: "svg.chart, svg[id^=chart]"
non_chart_selector: "svg[id=phaseTimeline], svg[id=sceneTimeline], svg[id=chartScenes], svg[id=flameChart]"

palette:
  allowed_hex: ["#79c0ff", "#7ee787", "#ffa657", "#d2a8ff", "#ffd479", "#ec4899", "#888"]
  semantic_reserved:
    "#dc2626": [".nav-badge", ".kpi-issue-dot.bad"]
    "#f85149": [".log-level-error"]
  
assertions:
  A1-1:
    enabled: true
    forbidden_keywords: ["frameMs", "GPU=", "DC=", "GC="]
    chart_exceptions:
      chartFrameMs: ["frameMs"]
      chartBrush: ["frameMs"]
      chartCpuGpu: ["CPU", "GPU"]
      chartGc: ["GC"]
  A1-2:
    enabled: true
    non_chart_ids: [phaseTimeline, sceneTimeline, chartScenes, flameChart]
  A2-2:
    enabled: true
    min_hue_diff_deg: 30
  A3-1:
    enabled: true
    expected_align: left
  A4-1:
    enabled: true
    units_required_keywords: [MB, ms, KB, '个', '%', 's', mV, mW]
```

## 数据不变量 (data_invariants) — 验"盒子里的数对不对"

A1–A4 验视觉/呈现；`data_invariants` 验**数据正确性**：从报告按 selector 取数值 → 聚合 → 和参照值比较。
**harness-core 只提供这个通用机制，不内置任何业务规则**（DEFAULT 为空）。具体不变量由项目在 config 的
`data_invariants` 提供——这样任何产出 HTML 报告的工程都能写自己的"物理/逻辑不变量"防回归。

### schema（每条一个 dict）

```yaml
data_invariants:
  - id: marker_total_le_duration      # 必填，显示在报告里
    description: marker 各线程 total 不超录制时长×1.1
    severity: error                   # error | warn（默认 error）
    value:                            # 被检查的值
      selector: ".marker-thread .total"   # CSS selector（必填）
      extract: number                 # number | count（默认 number；number 从文本抠首个数值，去千分位、容忍单位/%）
      aggregate: sum                  # none | sum | max | min（默认 none；none 时必须只匹配 1 个元素）
    op: "<="                          # <= < >= > == != non_empty empty
    ref:                              # 参照值（op 为 non_empty/empty 时省略）
      selector: "#recording-duration" # 二选一：另一个取值…
      # const: 100                    # …或常量
      extract: number
      aggregate: none
    factor: 1.1                       # 阈值 = ref × factor（默认 1.0）
    remediation: "..."                # 可选修复建议
```

语义：`聚合(value.selector 的数值)  op  ref × factor`。
`op: non_empty/empty` 改判匹配元素**个数**（≥1 / =0），此时忽略 ref。

### 覆盖的不变量形状（示例）

| 想表达 | 关键字段 |
|---|---|
| X ≤ 时长×1.1 | `value.aggregate: sum` + `ref.selector` + `factor: 1.1` |
| 占比 ≤ 100% | `value.aggregate: max` + `ref.const: 100`（"120%" 会被解析成 120） |
| FPS max ≤ cap×1.5 | `value.aggregate: max` + `ref.selector` + `factor: 1.5` |
| 帧号 < 捕获数×2 | `op: "<"` + `factor: 2` |
| breakdown 和 ≥ frameMs×0.6 | `op: ">="` + `value.aggregate: sum` + `factor: 0.6` |
| spike 栈必须非空 | `op: non_empty` |

**前置（项目侧）**：被取的数值必须在 DOM 里**机器可读**（textContent / 表格单元格）。若只渲染成图表柱高，
selector 抠不出数字——报告生成器要把数值落到可 query 的元素（见 spec 模板 §9「数据采集 vs 渲染层边界」）。

**用法（RED-first）**：每修一个数据 bug → 加一条不变量；先用旧的坏报告确认新断言能抓到（FAIL），再修。

## Reference

- RFC: `docs/visual_audit_assertions.md`（已合 main 2c8229b）
- 数据不变量机制: `assertions.assert_data_invariant` + `tests/test_data_invariant{,_e2e}.py`
- 参考实现起点: Periscope `Packages/com.ut.periscope/Tools/audit_charts.mjs`（Node Puppeteer MVP）
