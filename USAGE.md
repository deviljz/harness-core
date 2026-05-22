# harness-core 使用手册

## 1. 安装

```bash
pip install -e C:/Users/zhe_jin/workspace/harness-core/
# 验证
harness --help
```

换机器 / 新项目成员协作：见"多人协作"一节。

---

## 2. 新项目接入（5 分钟）

进入项目根目录：

```bash
cd F:/Project/YourProject
harness init                    # 生成 .harness/config.yaml + .claude hooks
```

编辑 `.harness/config.yaml`，按你项目结构填 `targets`：

```yaml
project: your-project
llm:
  provider: claude_agent

ignore_paths_global:
  - .git/**
  - "**/__pycache__/**"
  - "**/node_modules/**"
  - uploads/**

targets:
  - name: backend
    root: app/
    language: python           # python | dart | fallback
    test_paths: [tests/]

  - name: mobile
    root: mobile/
    language: dart
    test_paths: [mobile/test/]
    ignore_paths: [mobile/**/*.g.dart, mobile/build/**]

  - name: web
    root: frontend/web/
    language: fallback
    checks:
      vitest_cmd: { cmd: "npm test --if-present", cwd: "frontend/web/" }
```

验证配置：

```bash
harness doctor
```

---

## 3. 日常用法（只需记 2 条命令）

### 3.1 手动跑检查

```bash
# 单文件（改完立刻跑相关测试）
harness check --on-edit app/routers/stats.py

# 全量
harness check

# 只看会跑哪些，不真执行
harness check --on-edit app/xxx.py --dry-run

# 跑完允许不 block（CI 不想 fail）
harness check --warn-only
```

### 3.2 Gate（确认报告绿了才能 ship）

```bash
harness check --gate
# 0 = 最近一份 check 全绿 → 放行
# 非 0 = 有 fail，拒绝放行

# 逃生舱（需明确理由）
harness check --skip-gate --reason "紧急修复，测试环境挂了"
```

---

## 4. 4 层流程（Claude Code 里用 slash command）

**推荐方式**：在 Claude Code 里直接敲 `/harness-*` 命令，AI 必须按 skill 定义执行，比自然语言更明确。

| 命令 | 用途 |
|------|------|
| `/harness-plan <任务名>` | 起草 spec 骨架 → 引导填 6 段 → 自动 validate |
| `/harness-execute <spec路径>` | 按 spec 逐项实现（simple 直接做 / complex 起 subagent）|
| `/harness-review <spec路径>` | 起独立 subagent 对比 diff 与 spec，找偏差 |
| `/harness-check [args]` | 跑验证，支持 `--gate` / `--on-edit path` / `--warn-only` |

### 典型流程

```
你：/harness-plan 打卡记录支持重新提交
AI：[调 harness plan new，引导你填 Objective/Commands/Structure/...]
    [填完跑 harness plan validate，通过]

你：/harness-execute docs/tasks/20260423_xxx.md
AI：[读 spec 的 complexity]
    [按 Structure 列出的文件逐个改]
    [每改完 hook 自动 harness check --on-edit 验证]

你：/harness-review docs/tasks/20260423_xxx.md
AI：[跑 harness review-data 拿 diff+spec+template]
    [用 Agent 工具起 subagent 审查]
    [输出 consistent: true/false + issues]

你：/harness-check --gate
AI：✅ gate passed
```

### 日常小改不用走 4 层

单文件 bug fix / 改 UI → PostToolUse hook 会自动跑 `harness check --on-edit`，不用手动。

### CLI 直接调用（不在 Claude Code 里）

```bash
harness plan new my-task
harness plan validate docs/tasks/my-task.md
harness execute docs/tasks/my-task.md
harness review --spec docs/tasks/my-task.md
harness check --gate
```

---

## 5. 查状态

```bash
harness status       # 当前有没有暂停中的流程
harness reports      # 最近 N 份检查报告（✓/✗ 一目了然）
harness resume       # 恢复被熔断中断的流程
```

---

## 6. Claude Code 集成（自动触发）

`harness init` 默认把 hook 装到 `.claude/settings.json`：

- **PostToolUse（Edit/Write 后）** → 自动跑 `harness check --on-edit <path> --warn-only`
- **Stop（Claude 回合结束）** → 自动跑 `harness check --gate`

效果：Claude 改完文件 → 自动验证 → 报告挂了直接提醒 Claude 修复。

**协作者没装 harness？** hook 会静默跳过，不影响他们干活。

---

## 7. 多人协作 / 多机使用

- `.harness/config.yaml` 入库（共享）
- `.harness/run_hook.py` 入库（wrapper，没装 harness 时静默 exit 0）
- `.claude/commands/harness-*.md` 入库（4 个 slash command 模板）
- `.claude/settings.json` 入库（hook 配置）
- `.harness/check_cache.json` **不入库**（本地缓存）
- `reports/` **不入库**（测试产物）

其他人拉代码后：
```bash
pip install -e <harness-core 路径>/
# 就能用 hook 了
```

---

## 8. 常见问题

**Q: pytest 显示 0 passed 但实际有测试？**
A: 如果项目 `pytest.ini` 里有 `-p no:capture` 等会抑制 summary 行的配置，harness 用 per-test 标记兜底。若仍不对，看 `reports/check_*.json` 的 raw_output。

**Q: flutter / npm 没装，会 crash 吗？**
A: 不会。缺工具时 target 自动 skip（exit_code=127），其他 target 正常跑。

**Q: 改了一个 `.g.dart` 自动生成文件，harness 却跑了全量？**
A: 在 `.harness/config.yaml` 的 target.ignore_paths 加 `mobile/**/*.g.dart`。

**Q: Windows 路径 `app\routers\stats.py` 能识别吗？**
A: 能。router 内部统一规范化为 POSIX 风格 + 大小写不敏感。

**Q: cache 导致没重跑？**
A: 删 `.harness/check_cache.json` 或等 30s 去抖过期。内容 hash 变了会自动重跑。

---

## 8b. 非 python / dart 工程接入（Unity / Unreal / Go / C# / Rust 等）

harness-core 的完整能力（语言模块 + 增量测试 + AST 反模式）只在 `language: python` 和 `language: dart` 下生效，其他语言走 `language: fallback`，能力**大量退化**——详见 AGENTS.md「fallback 模式退化清单」。

### 推荐接入流程

**1. 装包但只用 spec + review 层**

```bash
pip install git+https://github.com/deviljz/harness-core.git
harness init
```

config.yaml 简化成只配 review，**不配 check**（check 在 fallback 下意义不大）：

```yaml
project: my-unity-game
llm:
  provider: claude_agent

review:
  # 二进制资源 / 临时文件 review 时跳过
  ignore_diff_patterns:
    - "**/*.meta"           # Unity meta 文件
    - "**/*.prefab"         # 暂不语义化 review prefab
    - "**/*.unity"          # 同上 scene
    - "**/*.asset"          # ScriptableObject
    - "**/Library/**"
    - "**/Temp/**"
    - "**/obj/**"
    - "**/bin/**"

targets:
  - name: client
    root: Assets/Scripts/   # 只 review C# 代码
    language: fallback
    test_paths: []          # 不跑测试，留人工
```

**2. 关掉 PostToolUse 自动 check**

Unity / Unreal 这类**编译型 + 长启动**工程，PostToolUse 自动 check 会让每次文件编辑卡 30-60 秒。在 `.claude/settings.json` 里删 harness 相关 hook。

**3. 工作流退化为"手动 plan + 手动 review"**

```
/harness-plan <task>        # 写 8 段 spec（语言无关，照样可用）
（自己写代码 + 自己跑测试）
/harness-review <spec>      # 跑独立 subagent 审 diff vs spec
```

跳过：`/harness-check`、`/harness-full`、`/harness-execute`（除非你愿意手写 PostToolUse 校验脚本）

### 在 .harness/config.yaml 沉淀语言专属反模式

虽然没有 language 模块，**anti_patterns 是语言无关的正则扫描**，可以单独用：

```yaml
anti_patterns:
  csharp:                              # 文件扩展名 .cs 自动匹配
    - name: empty_catch
      pattern: '^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$'
      msg: "禁止裸 catch 空块，会吞掉所有异常"
      severity: error
    - name: debug_log_no_prefix
      pattern: 'Debug\.Log\("(?!\[)'
      msg: "Debug.Log 必须以 [Module] 前缀"
      severity: warn
```

跑 `harness check --rules anti_patterns` 即可触发扫描（不需要 language 模块）。

详细的反模式贡献指引见 [docs/contributing-anti-patterns.md](./docs/contributing-anti-patterns.md)。

### 长期：贡献语言模块

如果想要完整的「增量测试 + 结构化结果解析 + AST 检查」，给 harness-core 贡献 `harness/languages/<lang>/` 模块。参考 `harness/languages/python/` 实现 4 个核心方法：

- `find_related_tests(changed_file, target_config, project_root) -> list[Path]`
- `run_tests(test_files, target_config, project_root) -> RunResult`
- `parse_results(raw) -> ParseResult`
- `deep_check(test_file, target_config) -> list[DeepCheckIssue]`

完成后在 `EXT_TO_LANG`（`harness/validate/anti_patterns.py`）注册扩展名映射。

---

## 9. 命令速查

| 命令 | 用途 |
|------|------|
| `harness init` | 初始化项目（生成 config + hooks） |
| `harness doctor` | 检查配置合法性 |
| `harness check [--on-edit PATH] [--gate] [--dry-run]` | 跑验证 |
| `harness plan new/validate` | 写 / 校验 spec |
| `harness execute SPEC` | 按 spec 执行 |
| `harness review --spec SPEC` | LLM 审查 diff |
| `harness status` | 查看暂停流程 |
| `harness resume` | 恢复流程 |
| `harness reports` | 查历史报告 |
