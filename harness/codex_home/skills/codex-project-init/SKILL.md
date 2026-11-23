---
name: codex-project-init
description: 让 Agent 自主为新项目或老项目完成 Codex harness 初始化（扫描目录结构、生成或精简 <=40 行的薄 AGENTS.md、生成轻量 .harness/config.yaml 与 4 栏换班卡模板、跑 harness doctor 验证）。适合“帮这个项目接入 harness / 初始化项目入口 / 补 AGENTS.md”。
---

# Codex 项目自助初始化

当用户要求把一个仓库接入 `harness-core`（或补齐薄 `AGENTS.md` 与项目红线检查）时，按下面 4 步自主完成，尽量一次做到位，不向用户抛一堆配置填空题。

## 第 1 步：一键扫描 + 生成基础骨架

在项目根目录运行：

```powershell
python -m harness init --agent codex --inspect-json
```

该命令只读扫描仓库并生成最小骨架，**不会覆盖已有 `AGENTS.md` 或已有 `.harness/config.yaml`**，同时会输出结构化 JSON，包含：
- 检测到的语言与工程形态（如 Unity / Python / Node / Lua / C++）
- 现有入口文档（`README.md`、`AGENTS.md`、`doc/`、`01_Docs/` 等）
- 检测到的构建 / 验证 / 导出脚本（`build*`、`verify*`、`test*`、`export*`）
- 已有 `AGENTS.md` 的行数与路径

## 第 2 步：核对关键文档（只读必要入口，不全仓乱扫）

- 读 `README.md`（优先前 120 行）和已有的 `AGENTS.md`（如有），只确认 3 件事：
  1. **构建与验证命令**（确切可执行的命令行，来自仓库真实脚本，不编造）
  2. **主文档指针**（查规则/方案/验收报告时该先看哪 1～3 份文档）
  3. **本项目专属的 3～5 条硬红线**（客观踩坑边界，如固定构建路径、禁自动传符号、特定资源规范）

## 第 3 步：整理薄 `AGENTS.md` 与轻量 `.harness/config.yaml`

- **薄 `AGENTS.md` 铁律**：
  - 总长度严格控制在 **≤ 40 行**（入口地图，不是百科全书）。
  - 只写：仓库结构速览、构建/验证命令、主文档指针、本项目 3～5 条红线。
  - **禁止**把 `~/.codex/AGENTS.md` 里的全局铁律（如说人话、单 MuMu、先复用再重写）重复抄进项目。
  - 如果项目已有且写得很好的 `AGENTS.md`（如 ≤40 行），只按需小幅补充缺失入口，不重写、不删用户原有约束。
- **轻量 `.harness/config.yaml`**：
  - 保留 `agent: codex`，**不安装 `.claude/` 自动 hook**，Unity / 大型工程不把重型编译挂进默认 `targets`（避免误触发全量卡死）。
  - 只把**客观可正则判定的本项目红线**写进 `anti_patterns`（优先用 `include`/`exclude` 精准限定目录，零误报、毫秒级跑完）。
  - 不要把单项目业务细节倒灌回 `harness-core` 公共包。

## 第 4 步：自检闭环并简短汇报

依次运行验证：

```powershell
python -m harness doctor
python -m harness check --warn-only
```

确认 `doctor` 无报错、`check` 能在秒级跑完且无误报后，用 5 行以内向用户汇报：
1. 生成/更新了哪些文件
2. `AGENTS.md` 行数与包含的核心入口
3. 配置了哪些 `anti_patterns` 检查及首跑结果
4. 如有需要用户拍板的 1～2 条项目专属红线，简明列出
