# AGENTS.md — harness-core 接入指引（AI 自助）

> 给自动化代理（Claude Code / Cursor / Aider 等）读的初始化指南。
> 人类读 README.md / USAGE.md。

## 一句话定位

harness-core 是 AI 编码纪律工具：把「写 spec → 执行 → 跑测试 → 审查 diff」固化成 4 个 slash command，让 AI 写代码时**自动**遵守 TDD 红绿铁律 + 5 类盲区检查（边界值 / 路径语义 / 真实文件 / 时序竞态 / 鉴权契约 / 修复完整性）。

## 你（AI 代理）的任务

把 harness-core 装到当前工程，让用户可以在 Claude Code 里输入 `/harness-plan` / `/harness-execute` / `/harness-check` / `/harness-review` / `/harness-full`。

## 初始化步骤

### 1. 安装 Python 包

激活当前工程的 venv / conda 环境（如有），然后：

```
pip install git+https://github.com/deviljz/harness-core.git
```

验证：`harness --help` 能列出子命令（plan / execute / check / review / verify / doctor / init）。

如果走不了 git+https（公司内网），克隆到本地再 `pip install -e <path>`。

### 2. 初始化当前工程

在工程根目录跑：

```
harness init
```

会生成：
- `.harness/config.yaml` — 配置文件（要按工程实际结构填 `targets`）
- `.claude/commands/harness-*.md` — 5 个 slash command
- `.claude/skills/harness-*` — 5 个 skill 描述（让 Claude Code 知道何时触发）

### 3. 配置 targets（必做）

打开 `.harness/config.yaml`，按工程实际结构填 `targets`。常见模板：

```yaml
project: <工程名>
llm:
  provider: claude_agent          # 推荐：复用 Claude Code 本身的能力，不另起 API
ignore_paths_global:
  - .git/**
  - "**/__pycache__/**"
  - "**/node_modules/**"

targets:
  - name: backend
    root: app/                    # 或 src/、server/，按实际改
    language: python              # python | dart | fallback
    test_paths: [tests/]

  - name: mobile                  # 没有移动端就删这块
    root: mobile/
    language: dart
    test_paths: [mobile/test/]

  - name: web                     # 没有 web 就删这块
    root: frontend/
    language: fallback
    checks:
      vitest_cmd: { cmd: "npm test --if-present", cwd: "frontend/" }
```

### 4. 验证接入

```
harness doctor
```

应当全绿。任意红色项必须先修好。

```
harness check
```

会跑一次基础检查（lint + 单测），出报告。

### 5. 在 Claude Code 里试一次

让用户输入：`/harness-plan <随便一个小任务>`

如果 skill 触发并要求填 8 段 spec → 接入成功。

## 不要做的事

- **不要硬编码 API key** 到 config.yaml；用 `${ENV_VAR}` 引用环境变量
- **不要把 `.harness/check_cache.json` / `.harness/review_data*.json` 提交到 git**（运行时产物）
- **不要改 harness-core 包本身**；要扩展就在 `.harness/config.yaml` 加 hook
- **不要跳过 `harness doctor`**：诊断不绿强行用会触发误判

## 完成后报告

完成后告知用户：
- `harness --version`
- `.claude/commands/` 下生成的文件名
- `.harness/config.yaml` 的 `targets` 段
- `harness doctor` 结果
- 第一次 `/harness-plan` 是否触发成功

## 更多文档

- USAGE.md — 完整使用手册（每个子命令的参数 + 示例）
- README.md — 设计架构 + 项目维护信息
