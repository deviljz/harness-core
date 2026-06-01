# Spec: Periscope 对标 UWA GOT Online（mock）

## Objective

实现 Unity 性能报告工具，对标 UWA GOT Online (https://www.uwa4d.com/u/got/) 提供同等覆盖的子页面。

## User Flow

1. 用户在 Unity Editor 触发录制
2. 真机/Editor 运行采集 → device pull 拉数据
3. 生成 HTML 报告
4. 浏览器打开 → sidebar 切各子页查指标

## Commands

- `harness-recorder start` / `stop`
- `harness-pull-device`
- `harness-gen-report`

## Structure

- `Packages/com.ut.periscope/Editor/PeriscopeReportGenerator.cs`
- `Packages/com.ut.periscope/Runtime/PeriscopeRecorder.cs`

## Style

C# verbatim string 嵌入 HTML / JS — 注意注释里不能用孤立 `"`。

## Testing

- pytest fixture 验报告 sidebar 结构
- chrome MCP DOM 断言（M2 后续）

## Boundaries

- 不实现 UWA 的"对比分析"（多报告 diff）— 后续 milestone
- 不实现 AI 诊断（依赖 UWA 后端模型）

## Data Migration

N/A
