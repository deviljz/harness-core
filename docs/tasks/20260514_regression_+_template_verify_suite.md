# regression + template verify suite

> 给 harness-core 加自我验证能力 — Bug Fixture Regression（A）+ 合成模板项目（C）双轨。

**complexity**: complex

---

## 1. Objective（目标）

**做什么**：给 harness-core 新增 `harness verify` 子命令，跑两类自我验证：
1. **Regression**（方案 A）：历史真实漏过的 bug，每个一个 fixture，验证当前版本 harness review 仍能 catch
2. **Template-test**（方案 C）：合成最小项目 + 5 个 case（happy / UI 偷工 / URL 相对路径 / 只 mock 单测 / 数据过滤破老数据），验证 review 对每类已知 bug 模式的 catch 率

**为什么做**：
- 之前每次升级 harness 只跑 unit test（225+），无法验证"真实 review 在场景上能 catch 多少 bug"
- v1.2 实战暴露 2 个真实 bug（settings 缺按钮 / download_url 相对路径），但当时 review 模板没抓到 → 现在 0.3.2 改完后**没数据证明能 catch**
- 需要可重复跑的"recall 指标"作为 0.x → 0.y 升级 gate

**用户是谁**：harness-core 维护者（升级前跑 verify 看 catch 率）

**成功标准**（可验证）：
1. `harness verify regression` 跑 `tests/fixtures/regression/` 下所有 fixture，输出 PASS/FAIL 报告 + recall 指标
2. `harness verify template-test` 跑 `tests/fixtures/template_project/` 下 5 case，输出 PASS/FAIL
3. `harness verify run`（默认）= regression + template-test 全跑
4. v1.2 漏过的 2 个 bug 作为初始 regression fixture，跑 0.3.2 至少**catch 到主要 issue 关键词**（如"设置页"/"checkUpdate"/"相对路径"/"baseUrl"/"mock 单测"）
5. 5 个 template case 跑 0.3.2：
   - case_01 happy path → `consistent=true`
   - case_02-05 → `consistent=false` + 含特定 keyword
6. recall < 1.0 时 CLI exit 1（可作为 CI gate）

**非目标**：
- 不替代现有 pytest 单测（unit / 配置/ parser 类继续跑 pytest）
- 不要求 100% recall（LLM 非确定，定义"硬要求"keyword + 软 issue 数量）
- 不引入 LLM mock（必须真调 gemini/claude_agent，跟真实 review 行为一致）
- 不写 web UI / dashboard

---

## 2. User Flow（用户动线）

N/A - CLI 工具，无 GUI。

间接用户动线：
1. 维护者改 harness（如改 review template）→ 跑 `harness verify run` → 看 recall 报告
2. 任一 fixture 回归（之前 caught 现在 missed）→ exit 1 → CI 拦截 commit
3. 真实生产新出 bug → 维护者沉淀到 `fixtures/regression/00X/` → 下次自动跑

---

## 3. Commands（提供哪些命令/接口）

### 新增 CLI

```bash
harness verify run                    # 跑全套（regression + template-test）
harness verify regression             # 只跑 regression fixtures
harness verify regression --fixture=001  # 单跑某个 fixture
harness verify template-test          # 只跑 template-test cases
harness verify template-test --case=02
harness verify --json                 # 输出 JSON 报告
```

### 输出格式

```
=== Regression Fixtures ===
001_settings_check_update_missing   PASS  caught 2/2 expected keywords
002_download_url_relative           PASS  caught 2/2 expected keywords

=== Template-test Cases ===
case_01_happy_path                  PASS  consistent=true (expected true)
case_02_ui_skipped                  PASS  consistent=false, matched "设置页"
case_03_url_relative                FAIL  expected "baseUrl" keyword, not in issues
case_04_only_mock                   PASS
case_05_data_filter                 PASS

Total: 6 PASS, 1 FAIL
Recall: 6/7 = 85.7%
```

### 测试 / 验证
- `pytest tests/test_verify_cli.py -v` 单测 CLI 框架（assert keyword 匹配、report 格式）
- `harness verify run` 实跑（调真实 LLM，耗时 ~1-2 分钟）→ 0.3.2 应该至少 5/7 PASS

---

## 4. Structure（目录/模块）

```
harness/
├── verify/                       # 新模块
│   ├── __init__.py
│   ├── cli.py                    # harness verify 子命令实现
│   ├── runner.py                 # 跑单个 fixture 的核心逻辑（拼 prompt 起 subagent 比对 keywords）
│   ├── report.py                 # PASS/FAIL 报告格式化
│   └── matchers.py               # 关键词匹配 / soft assertion（容忍 LLM 措辞差异）
└── cli.py                        # 加 verify 子命令组（routes to verify.cli）

tests/
├── fixtures/
│   ├── regression/
│   │   ├── 001_settings_check_update_missing/
│   │   │   ├── spec.md                # 当时的 spec（含 User Flow "设置页点检查更新"）
│   │   │   ├── worktree/              # 模拟工作树（只含相关文件）
│   │   │   │   └── mobile/lib/services/update_service.dart
│   │   │   ├── subagent_report.txt    # 含"先跳过 UI 入口"措辞
│   │   │   └── expected.json          # {"consistent": false, "keywords": ["设置页", "check.*update", "mock"]}
│   │   └── 002_download_url_relative/
│   │       └── ...
│   └── template_project/
│       ├── case_01_happy_path/
│       ├── case_02_ui_skipped/
│       ├── case_03_url_relative/
│       ├── case_04_only_mock/
│       ├── case_05_data_filter/
│       └── shared/                    # 共享的最小项目骨架
│           ├── backend/main.py
│           ├── mobile/lib/main.dart
│           └── pubspec.yaml
└── test_verify_cli.py            # 单测 verify 框架本身（不调真 LLM，mock subagent 返回）
```

---

## 5. Style（代码风格 / 依赖选型）

- 不引入新依赖
- 遵循 harness-core 现有风格（pydantic + type annotations）
- LLM 调用走 `harness.llm.providers` 现有 manager（claude_agent / manual）
- Keyword 匹配用 Python `re` 模块，case-insensitive；支持简单 OR `keyword1|keyword2`
- 报告输出用 rich console（已是依赖）

### Keyword matcher 容忍度

每个 fixture 的 `expected.json` 含：
```json
{
  "consistent": false,
  "required_keywords": ["设置页", "(check.?update|检查更新)"],
  "soft_keywords": ["mock", "集成测试"],
  "min_issues_count": 2
}
```

判定：
- `consistent` 必须严格匹配
- `required_keywords` 全部必须命中（所有 issues 文本拼接后 grep）
- `soft_keywords` 至少命中 50%
- `min_issues_count` 软门槛

---

## 6. Testing（测试策略）

### 单测（tests/test_verify_cli.py）
- mock subagent 返回固定 JSON，测 keyword matcher 逻辑（命中 / 漏掉 / 模糊匹配）
- 测 report 格式化（PASS/FAIL 输出对齐 / JSON 输出 schema）
- 测 fixture 加载（缺 expected.json / 缺 worktree 报错）

### 集成测试（跑真 LLM）
- 不写成 pytest（CI 跑会耗时 + 不稳定）
- `harness verify run` 本身就是集成测试，由维护者手工跑
- 提供 dry-run 模式：`harness verify run --dry-run` 只组装 prompt 不调 LLM，给 prompt 长度审查用

### Fixture 内容（初始 v1.2 的 2 个真实 bug）
1. `001_settings_check_update_missing` — User Flow 写"设置页齿轮按钮 → 检查更新"，工作树缺 settings_screen，subagent_report 含"先跳过 UI 入口"
2. `002_download_url_relative` — Testing 段要求"真起 backend 真发请求"，update_service.dart 用 Uri.parse(downloadUrl) 没拼 baseUrl，tests 全 mock

### Template-test 5 case
- case_01_happy_path：spec + impl 都到位，review 应 `consistent=true`
- case_02_ui_skipped：spec User Flow 要 UI 入口，worktree 缺该 UI，subagent_report 含偷工措辞
- case_03_url_relative：API 返回相对 URL，client 直接 parse 失败
- case_04_only_mock：spec 要求集成测试，只有 mock
- case_05_data_filter：spec 加 WHERE kind='X'，worktree 含 1 张表 5 行测试数据全 kind=NULL，命中数据源 trace 报错

---

## 7. Boundaries（边界）

### 绝不做
- 不在 verify run 时改任何用户工作树（fixture 跑在 tmp dir，cp 出去）
- 不缓存 LLM 结果（每次跑真请求，反映当前 LLM 实际表现）
- 不让 verify pass 强依赖某个 LLM provider（claude_agent / manual 都能跑）
- 不删 harness-core 现有 unit test 流程（pytest 还是日常跑）
- 不要求模板项目能真 build（spec 跟代码骨架够 review 看就行）
- 不 git commit（顶层流程统一）

### 必须做
- v1.2 的 2 个真实 bug 作为初始 regression fixture（这是验证 0.3.2 改动的关键凭证）
- CLI 兼容 `--dry-run`（不调真 LLM 也能 sanity check fixture 完整性）
- 每个 fixture 自带 README.md 说明 bug 上下文
- 测试 LLM 非确定性：同一 fixture 跑 3 次，至少 2 次 PASS 才算稳定（在文档里说明，不强制实现）

---

## 8. Data Migration（数据迁移）

N/A - 不动用户数据。`tests/fixtures/` 是 harness-core 内部 fixture，跟用户项目无关。

---

## 执行计划

| 阶段 | 交付物 | 估时 |
|---|---|---|
| 1 | `harness/verify/` 模块骨架 + CLI + matcher 单测 | 1 小时 |
| 2 | regression fixtures（v1.2 的 2 个真实 bug） + expected.json | 30 分钟 |
| 3 | template_project 共享骨架 + 5 case spec + 5 case worktree | 1 小时 |
| 4 | `harness verify run` 跑通 + 跑 0.3.2 看实际 catch 率 | 30 分钟 |
| 5 | 总结：哪些 case PASS，哪些 FAIL，写 reports/ + memory | 30 分钟 |

**预计总时间 3.5 小时**（含并行 + 实跑 LLM 验证）。
