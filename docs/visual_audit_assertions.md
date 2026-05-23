# Visual Audit Assertions Checklist

> UI 工程开发后，用 chrome/playwright DOM 断言巡检报告/页面。本文档列**与具体 UI 解耦的断言模板**，作为 `harness-visual-audit` skill（RFC 待提）的设计基础。
> 来源：Periscope 项目（Unity 性能报告工具，HTML 单文件）+ 喵辅导前端可复用。

## 设计原则

1. **断言模板与具体业务解耦**：模板定义"什么是 ✓"，业务 spec 定义"哪些元素需要满足"。
2. **断言可独立运行**：每条 assertion 自包含数据采集 + 判定。
3. **失败信息可定位**：fail 时输出元素 selector + 实际值 + 期望值。
4. **覆盖 6 大类**：hover / 颜色 / 对齐 / 单位 / 对比度 / 跨页面一致性。

## 6 大类断言

### 类 1: Hover Tooltip 断言

#### A1-1 tooltip 不串入无关字段

**场景**：多 chart 共享全局 `#tooltip` 容器时，前 chart hover 残留值/无关字段污染下一 chart 显示。

**断言**：hover 任意 chart 后，tooltip 内容**只能**包含：
- 当前帧号 / 时间戳
- 场景名（可选）
- **该 chart 自身**的曲线/指标值

**禁止**：硬编码全局指标（frameMs / GPU / DC / GC）出现在与之无关的 chart hover 中。

**实现**：
```python
def assert_hover_no_unrelated_fields(page, chart_selector, allowed_keywords, forbidden_keywords):
    # forbidden_keywords 默认 ['frameMs', 'GPU=', 'DC=', 'GC=']
    # allowed_keywords 由业务 spec 给（每 chart 不同）
```

#### A1-2 非曲线图（横条/堆叠/火焰图）mousemove 时主动隐 tooltip

**场景**：phaseTimeline / sceneTimeline / flameChart 等用 SVG `<title>` 原生 tooltip，全局 #tooltip 残留前 chart 值看着像是它的。

**断言**：先 hover 一个有 tooltip 的 chart 让 #tooltip 显示，再 hover 非曲线图，#tooltip `display: none`。

#### A1-3 多线 chart hover 必须显每条线 + 颜色与曲线一致

**断言**：多线 chart hover tooltip 含 N 行（N = 曲线数），每行带视觉标识（如 `●`）+ span 颜色与对应曲线颜色一致。

---

### 类 2: 颜色规范断言

#### A2-1 颜色调色板限制

**场景**：项目定义了固定调色板（如 7 主色 + 2 语义保留色），杜绝任意 hex 滥用。

**断言**：扫描所有 inline `style` + CSS 规则的 `color` / `background` / `fill` / `stroke`，hex 值必须属于调色板（除 grey scale `#1a1a1a~#fff` 兜底）。

**实现**：
```python
def assert_color_palette(page, palette_hexes, ignore_scales=True):
    # palette_hexes = ['#79c0ff', '#7ee787', ...]
    # 收集所有 color/background/fill/stroke 值
    # 校对是否属于 palette
```

#### A2-2 同 chart 多线必须对比色相

**场景**：同 chart 的 2-3 条线用同色系深浅（`#79c0ff` + `#5aaad7`）肉眼分不清。

**断言**：同 chart 内多线颜色 HSL hue 差 > 30 度。

**实现**：
```python
def assert_distinct_hues(line_colors, min_hue_diff=30):
    # HSL 转换 + 两两 hue 距离判定
```

#### A2-3 语义色专用性

**场景**：红色 = 错误 / 警告，但又被滥用于"装饰色"导致真实错误不显眼。

**断言**：定义"语义保留色"列表（如 `#dc2626 真红` / `#f85149 错误红`），扫描这些色仅出现在 spec 允许位置（如 nav-badge / error log level）。

---

### 类 3: 对齐规范断言

#### A3-1 表格数值列对齐统一

**断言**：所有 `td.num` 的 `text-align` 必须一致（业务 spec 指定 left / right / center 其一），不允许个别 td 不一致。

#### A3-2 sticky / absolute 元素无重叠

**断言**：固定位置元素（CSS `position: absolute / fixed / sticky`）的 boundingRect 不与下方内容首行 `boundingRect` 重叠 > 5px。

---

### 类 4: 单位标注断言

#### A4-1 数值列必须标单位

**场景**：表格列 `735` 用户误读 — 实际是 `Texture Count` 但没标"个"，用户当 MB。

**断言**：所有显示数字的 `<th>` / `<td>` 必须含单位文本（MB / ms / KB / 个 / % / s 等），或所属表格存在统一的单位列说明。

**实现**（启发式）：
```python
def assert_units_on_numeric_cells(page, units_whitelist):
    # 找所有 td 数字且不带单位 → 检查 thead 对应 th 是否含单位
    # 都没有 → fail
```

#### A4-2 单位 vs 数据范围合理性

**场景**：标 "MB" 但值范围 0-1000 整数（明显是 Count）。

**断言**：基于规则启发：
- 标 `MB`：值合理范围 0.01-10000，大多非整数
- 标 `ms`：0.01-1000
- 标 `个`：整数 0-1e6

值范围与单位严重不符 → flag warning。

---

### 类 5: 对比度断言

#### A5-1 文字与背景对比度

**断言**：所有文本 `color` vs 实际背景（含父级 background + opacity 叠加）WCAG 对比度 ≥ 4.5（正文）或 3.0（大字号）。

**实现**：
```python
def assert_text_contrast(page, min_ratio=4.5):
    # 遍历所有文本节点
    # 取 color + 计算实际背景（traverse parents）
    # WCAG 公式判定
```

#### A5-2 透明叠加层不透明度 ≥ 阈值

**场景**：absolute 按钮浮在内容上，半透明背景看不清字。

**断言**：`position: absolute / fixed` 元素的背景 `rgba(...,alpha)` alpha ≥ 0.6（默认）。

---

### 类 6: 跨 tab / 跨页面一致性断言

#### A6-1 同语义指标在多 tab 数值一致

**场景**：tab A 显示 "贴图峰值 270 MB"，tab B 同时间区间显示不同值。

**断言**：spec 列出"同语义指标 cluster"（如 `{tab:'memory', chart:'chartMemAsset.peak_texture'}` 和 `{tab:'rendering', kpi:'textureMemoryPeak'}`），断言数值一致（差 < 1%）。

#### A6-2 同 KPI 在 KPI 卡 / 表格 / chart hover 一致

类似 A6-1 但跨 UI 元素类型。

---

## skill 输入设计

```yaml
# audit_config.yaml
assertions:
  - id: A1-1
    enabled: true
    config:
      forbidden_keywords: [frameMs, "GPU=", "DC=", "GC="]
      chart_specific:
        chartFrameMs:
          allowed_keywords: [frameMs]
  - id: A2-1
    enabled: true
    config:
      palette: ["#79c0ff", "#7ee787", "#ffa657", "#d2a8ff", "#ffd479", "#ec4899", "#888"]
      semantic_reserved: 
        "#dc2626": [".nav-badge", ".kpi-issue-dot.bad"]
        "#f85149": [".log-level-error", ".log-level-exception"]
  - id: A2-2
    enabled: true
    config:
      min_hue_diff: 30
  - id: A4-2
    enabled: true
    config:
      ranges:
        MB: { min: 0.01, max: 10000, integer_ratio_max: 0.3 }
        ms: { min: 0.001, max: 5000 }
        个: { min: 0, max: 1000000, must_be_integer: true }
```

## skill 输出设计

```
== Visual Audit Report ==
Source: file:///path/to/report.html
Total assertions: 14
✓ PASS: 11
✗ FAIL: 3

[A1-1] chartMemGfx hover 不串入无关字段
  fail: tooltip 含 "frameMs = 33.05"
  expected: 只显 GfxUsed/GfxReserved
  selector: #chartMemGfx
  
[A2-2] chartMemTotal 3 线 hue 差 > 30 度
  fail: TotalUsed (#79c0ff h=210) vs SystemUsed (#5aaad7 h=200) hue diff = 10
  
[A4-1] memCountTable 第 2 列缺单位标注
  fail: <th>最小</th> 无单位文本
```

## 实现优先级（MVP）

| 优先级 | 类别 | 实现复杂度 |
|---|---|---|
| P0 | A1-1 tooltip 串入 | 低（DOM 文本匹配） |
| P0 | A3-1 表格对齐 | 低（getComputedStyle） |
| P0 | A4-1 单位标注 | 中（启发式） |
| P1 | A1-2 非曲线图隐 tooltip | 中（要 hover 序列） |
| P1 | A2-1 调色板 | 中（hex 收集 + 集合判定） |
| P1 | A2-2 多线 hue 差 | 中（HSL 转换） |
| P2 | A5-1 文字对比度 | 高（背景叠加计算） |
| P2 | A6-1 跨 tab 一致性 | 高（要 spec 标注 cluster） |

MVP 先做 P0 3 项 + P1 3 项 = 6 项断言模板，已覆盖 80% 真实场景。

## 跟 harness-baseline 的关系

`harness-baseline` 验**覆盖度**（应该有的 sidebar/子页有没有）；
`harness-visual-audit` 验**质量**（已有的 UI 元素显示对不对）。

两者顺序：plan 阶段 baseline 列出应做的子页 → execute 实现 → audit 验质量。

## 参考实现起点

Periscope 项目 `Packages/com.ut.periscope/Tools/audit_charts.mjs`（Node + Puppeteer）实现了 P0/P1 共 5 类断言的 MVP，可作为 Python skill 移植参考。
