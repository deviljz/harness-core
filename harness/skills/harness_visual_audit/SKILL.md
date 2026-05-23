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

## Reference

- RFC: `docs/visual_audit_assertions.md`（已合 main 2c8229b）
- 参考实现起点: Periscope `Packages/com.ut.periscope/Tools/audit_charts.mjs`（Node Puppeteer MVP）
