# Expected gap result

baseline.html 含 16 项，target/report.html 含 8 项。

## Aligned (✓ 8)
- 性能简报
- 场景概览
- GPU 渲染分析
- 模块耗时统计
- 内存占用
- 耗电量
- 温度变化量
- 运行日志

## Partial (🟡 0)
(none — fuzzy threshold 0.6 default 未触发)

## Missing (❌ 8)
- GPU 带宽分析
- GPU 指标汇总
- UI 模块性能
- 物理系统性能
- 资源内存
- Lua 内存
- 自定义面板
- GPU 分析 (group title 在 nav 中作为 li.el-submenu__title 也被抽出来)
