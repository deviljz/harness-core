# anti-patterns + core_modules check

> harness-core 新增两类 check：反模式正则扫描 + 核心模块测试覆盖检查。

**complexity**: complex

---

## 1. Objective（目标）

**做什么**：在 harness-core 加两个 cross-target 检查类型，提升到 `harness check` 流程内置能力：
1. **anti_patterns**：按文件扩展名匹配语言，跑配置的正则反模式（如 dart 自递归 getter、python bare except）
2. **core_modules**：检查 config 列出的核心源码文件是否有对应测试

**为什么做**：
- 现场案例（2026-05-12 喵辅导项目）：用 `replace_all` 工具引入 `int get userId => userId;` 自递归 getter 爆栈，flutter analyze 默认 lint 不抓、无 widget test 触发，运行时崩才发现
- 当前 harness check 只跑测试 + python `assertion_ast`，缺乏跨语言静态反模式检测能力
- 用户有多个项目 + 多电脑，希望防护规则做到 harness-core 而非每个项目复制

**用户是谁**：
- 用 harness 的开发者（所有项目）
- 通过 PostToolUse hook 触发的 AI 代码编辑场景（误改时立即拦截）

**成功标准**（可验证）：
1. `.harness/config.yaml` 加 `anti_patterns:` 和 `core_modules:` 两个顶层段，pydantic schema 校验通过
2. 喵辅导项目把临时 `.harness/post_edit_check.py` 的 yaml 内容平移到 `config.yaml` 后，`harness check --on-edit <带自递归 getter 的 dart 文件>` 报 `fail`
3. core_modules 列出的 path 改动后，缺 must_have_test 文件 → 报 `warn`
4. `harness init` 生成的 config.yaml 模板里含示例 anti_patterns 起手套（注释掉，让用户按需启用）
5. 单测：`tests/test_anti_patterns.py` 三类 case（命中 / 误报 / 跨语言） + `tests/test_core_modules.py` 两类（缺 test → warn / 有 test → pass）全绿
6. 现有 `harness check` 流程对没配 anti_patterns 的老项目**完全向后兼容**（空配置不报错、不变慢）

**非目标**：
- 不引入 AST 分析（保持正则就够；自递归 getter 用正则能抓 95%）
- 不在 harness check 之外加新 CLI 子命令（用户已熟 `harness check`，避免命令爆炸）
- 不实现规则的"自动修复"（只报告，让 AI/人决定怎么改）
- 不写 web UI / IDE 集成
- 不动 plan / execute / review 流程

---

## 2. User Flow（用户动线）

N/A - 工具类项目，无 GUI 交互。

**触发链路**（间接用户：依赖 harness 的开发者）：
1. 开发者用 Claude Code 改一个 `.dart` 文件
2. PostToolUse hook 调 `harness check --on-edit <file>`
3. harness 加载 `.harness/config.yaml` 的 `anti_patterns.dart` 规则
4. 跑正则匹配，命中 `self_recursive_getter` 模式
5. 报告里输出 `check_name=anti_patterns, status=fail, file:line, msg, rule`
6. hook exit 1 → Claude 看到失败提示，自修

**core_modules 触发**：
1. 开发者改 `mobile/lib/screens/main_tab_screen.dart`（core_modules 列表里）
2. harness 检查对应 `must_have_test` 路径
3. 文件不存在 → `check_name=core_modules_coverage, status=warn`

---

## 3. Commands（提供哪些命令/接口）

### 不新增 CLI 命令
- `harness check` 现有命令自动接入新检查（用户感知是"突然多了 2 个检查名"）
- `harness check --on-edit <file>` 一并触发

### 配置 schema 扩展
- `HarnessConfig.anti_patterns: dict[str, list[AntiPatternRule]]`
  - 顶层 key = 语言名（dart / python / typescript / javascript / "all"）
  - value = 规则列表，每条：`name + pattern + msg + severity + multiline?`
- `HarnessConfig.core_modules: list[CoreModule]`
  - 每条：`path + must_have_test + reason?`

### 测试 / 验证
- `pytest tests/test_anti_patterns.py -v`
- `pytest tests/test_core_modules.py -v`
- `pytest tests/` 全跑（确认现有测试不回归）

### 喵辅导回归验证（手工）
- 升级 harness：`pip install -e C:/Users/zhe_jin/workspace/harness-core`
- 把喵辅导 `.harness/anti_patterns.yaml` 内容并入 `.harness/config.yaml` 的 `anti_patterns:` 段
- `cd F:/Project/MiaoStudy && harness check` → 应该报历史 7 处 bare_except + 6 个核心模块缺测试

---

## 4. Structure（目录/模块）

```
harness/
├── config.py                              # 改：HarnessConfig 加 anti_patterns + core_modules 字段
├── validate/
│   ├── anti_patterns.py                   # 新增：反模式检测器
│   ├── core_modules.py                    # 新增：核心模块测试覆盖检查
│   └── runner.py                          # 改：run_checks 顶层接入新检查
├── reporter.py                            # 改（如需）：CheckResult 兼容 file/line/rule 字段
└── adapters/claude_code/
    └── install_hooks.py                   # 改：harness init 生成 config.yaml 时插入 anti_patterns 起手套

tests/
├── test_anti_patterns.py                  # 新增
├── test_core_modules.py                   # 新增
└── fixtures/
    ├── anti_patterns_project/             # 含自递归 getter 的 dart fixture
    └── core_modules_project/              # 含核心模块 + 缺测试的 fixture

docs/tasks/
└── 20260513_anti-patterns_+_core_modules_check.md  # 本 spec
```

---

## 5. Style（代码风格 / 依赖选型）

- 遵循 harness-core 现有风格：pydantic schema、`from __future__ import annotations`、type annotations
- 新增字段一律 `default_factory=list/dict`，保持向后兼容（老 config 没这两段 → 空 → 不跑新检查）
- 正则一律用 `re.MULTILINE`，可选 `re.DOTALL` 由 `multiline: true` 字段控制
- 检查器实现风格参考现有 `harness/languages/python/assertion_ast.py`（返回 `list[Issue]`）
- 不引入新依赖（PyYAML / pydantic 已在）
- 错误处理：单条规则正则编译失败 → 跳过该条 + warn 日志，不影响其他规则

---

## 6. Testing（测试策略）

遵循 `harness-core/tests/` 已有风格：pytest + fixtures + 真实 yaml 加载（不 mock）。

### anti_patterns
- **正常路径**：dart fixture 含自递归 getter → 检测到 1 个 finding，severity=error，line 正确
- **跨语言路径**：fixture 同时含 dart + python 文件，分别命中各自规则
- **边界**：规则 list 为空 → 不报错，返回 0 finding
- **错误路径**：规则正则非法 → warn 日志 + 跳过，其他规则正常跑
- **multiline**：含 `multiline: true` 的规则正确启用 DOTALL

### core_modules
- **正常路径**：路径 in modules list，must_have_test 存在 → pass
- **缺测试**：must_have_test 不存在 → warn
- **不在 list**：随便改个文件 → 不触发 core_modules check
- **changed_file=None（全量）**：扫描所有 modules，缺测试的每个都报 warn

### 集成
- 跑 `run_checks(config_with_anti_patterns)` 验证新检查接入 `ValidationReport.results`

### 不测
- 正则的"健壮性"（用户写的规则，正确性由用户负责，harness 只跑）
- 性能（规则数量 < 50 时，全量扫描 < 1 秒）

---

## 7. Boundaries（边界）

### 绝不做
- 不破坏现有 config schema：老项目空 config → harness check 行为不变
- 不在不知道扩展名的文件上跑规则（避免误扫 .gitignore / .md 之类）
- 不实现规则之间的优先级 / 互斥（先一律全跑）
- 不引入子进程调用（纯 Python 正则，跨平台兼容）
- 不写 windows-specific 代码
- 不动 `validate/runner.py` 的 `_run_target` 现有逻辑（新检查在 `run_checks` 顶层走，与 target 解耦）

### 必须做
- 单条规则失败不能炸全流程（try/except 隔离每条规则）
- 检查结果加入 `ValidationReport.results`，与现有 `assertion_ast` 结果格式兼容
- `harness init` 生成的 config.yaml **以注释形式**插入 anti_patterns 示例（不默认启用，避免老项目升级后报错）
- 写 CHANGELOG（项目根的 `README.md` 或 `CHANGELOG.md`）记录 schema 变化
- 改动后跑 `pytest tests/` 全绿
- 发版 bump pyproject.toml 版本号（0.x.y → 0.x.(y+1)）

---

## 8. Data Migration（数据迁移）

### 现有数据现状
- harness-core 不存储用户数据
- 涉及的"schema"是用户项目的 `.harness/config.yaml`
- 现有 config 没有 `anti_patterns` / `core_modules` 顶层段

### 迁移策略
- [x] **新代码显式兼容缺失字段**：`HarnessConfig.anti_patterns` 和 `core_modules` 用 `Field(default_factory=list/dict)`，老 config 解析后这两个字段是空 → 新检查跑 0 条规则 → 0 finding
- [x] **harness init 行为升级**：`harness init` 生成的新 config.yaml 模板**注释形式**加 anti_patterns 起手套
- [x] **现有项目升级路径**：用户 `pip install --upgrade harness-core` 后，老 config 仍能跑（无新 check）；想启用就手动加 yaml 段或跑 `harness init --reset-config` 重置

### 兼容性测试
- 跑 harness-core 自己 `tests/` 全部测试（其中一些用 fixture config 没有 anti_patterns 段 → 验证向后兼容）

---

## 执行计划

| 阶段 | 交付物 | 估时 |
|---|---|---|
| 1 | config.py schema 扩展 + 兼容老 config 单测 | 30 分钟 |
| 2 | validate/anti_patterns.py + 单测 | 1 小时 |
| 3 | validate/core_modules.py + 单测 | 30 分钟 |
| 4 | validate/runner.py 接入 + 集成测试 | 30 分钟 |
| 5 | install_hooks.py 模板更新 | 15 分钟 |
| 6 | README/CHANGELOG + bump 版本 + push | 15 分钟 |
| 7 | 喵辅导项目升级回归验证 + 回退临时 patch | 30 分钟 |
| **合计** |  | **≈ 3.5 小时** |
