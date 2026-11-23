# harness-core

AI 工程化 Harness 框架。实现 4 层闭环：方案 → 执行 → 审查 → 验证。

> **AI 代理首次接入新工程：直接读 [AGENTS.md](./AGENTS.md)**（不用人工告诉你怎么装）。

## 安装

远程安装（推荐）：

```bash
pip install git+https://github.com/deviljz/harness-core.git
```

开发模式（本地改 harness-core 源码时用）：

```bash
cd ~/workspace/harness-core
pip install -e .
```

安装后 `harness` 命令在 PATH 里可用。

## 快速开始（Codex 轻量模式，默认）

```powershell
# 1. 在新电脑上同步全局铁律 + 通用工程 Skill 到 ~/.codex/（自动备份旧文件，不碰私人 Skill）
python -m harness sync

# 2. 在具体项目根目录初始化（生成薄 AGENTS.md + .harness/config.yaml + 4 栏换班卡，支持 Agent 自助调用）
cd <your-project>
python -m harness init --agent codex --inspect-json

# 3. 体检、静态红线扫描、换班状态卡
python -m harness doctor
python -m harness check --warn-only
python -m harness handoff
```

> 在本机修改了 `~/.codex/AGENTS.md` 或通用 Skill 后，回 `harness-core` 目录运行 `python -m harness sync --pull` 即可回拉进仓库提交。
> 如需旧版 Claude Code hook 模式：`python -m harness init --agent claude`。

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
