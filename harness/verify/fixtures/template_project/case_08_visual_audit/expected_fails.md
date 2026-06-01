# Expected audit failures on case_08 fixture

跑 `harness visual-audit --target report.html --config config.json` 应失败的断言：

- **A1-1** chartMemBad hover 含 "frameMs = 33.05"（串入无关字段）
- **A2-2** chartMemBad 两线 hue Δ ≈ 5° (#79c0ff vs #5aaad7 都是蓝色)
- **A4-1** 表格列"贴图"/"网格" td 是 735/200 整数无单位，对应 th 也无 'MB' / '个' 等
- **A2-1** inline style 用了 #abcdef 非调色板色

应通过：
- A1-1 chartMemGood
- A1-2 (无 non_chart_ids 配置)
- A3-1 td.num text-align:left 一致
