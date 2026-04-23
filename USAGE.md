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

## 4. 4 层流程（完整闭环）

想跑完整"方案 → 执行 → 审查 → 验证"：

```bash
# 方案层：写 spec（6 段 + complexity 字段）
harness plan new my-task
# 编辑 docs/tasks/my-task.md 填 6 段
harness plan validate docs/tasks/my-task.md

# 执行层：按 spec 执行表逐项实现
harness execute docs/tasks/my-task.md

# 审查层：对比 diff 与 spec
harness review --spec docs/tasks/my-task.md

# 验证层：跑测试 + gate
harness check --gate
```

> 日常小改（bug fix / 改 UI）只跑 `harness check` 就够，不用强制 4 层。

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
