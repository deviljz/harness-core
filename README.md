# harness-core

AI 工程化 Harness 框架。实现 4 层闭环：方案 → 执行 → 审查 → 验证。

## 安装（开发模式）

```bash
cd ~/workspace/harness-core
pip install -e .
```

安装后 `harness` 命令在 PATH 里可用。

## 快速开始

```bash
cd <your-project>
harness init         # 生成 .harness/ 骨架
# 编辑 .harness/config.yaml 填 target
harness doctor       # 诊断接入是否正确
harness check        # 手动跑一次
```

## 设计文档

spec 位于 `<project>/docs/tasks/harness_core.md`（最早一版在 MiaoStudy 项目下）。

## 架构层次

```
harness/
├── core（语言无关 + AI 无关）
│   ├── plan/execute/review/validate
├── languages/    ← 语言模块（python/dart/fallback）
├── llm/          ← LLM provider 抽象
└── adapters/     ← AI 工具适配器（claude_code/generic）
```

跨项目通用，每个项目加一个 `.harness/config.yaml` 即可接入。
