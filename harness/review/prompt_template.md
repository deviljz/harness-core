# Review Task

You are a senior engineer reviewing a code change against its specification.

## Specification (the source of truth)

{spec_content}

## Code Change (diff)

```diff
{diff_content}
```

## Your Task

Check whether the code change:
1. Implements what the spec says
2. Doesn't violate the spec's boundaries (绝不做 section)
3. Matches the spec's testing and style requirements
4. **Data compatibility**: 改动是否引入新字段 / 新枚举值 / 新过滤条件？如有，是否配套了回填策略或对老数据的显式兼容？典型盲区例子：
   - 加 `kind` 列 + API 按 `WHERE kind='X'` 过滤 → 老数据 kind=NULL 全部被排除掉
   - 新增 enum 值 → 老数据用旧值，反序列化时可能崩
   - schema 加 NOT NULL 字段 → 老行没填会失败
   若 spec 有 Data Migration 段，校验迁移策略是否真在 diff 中体现（grep migration SQL / startup hook / 回填脚本）；若无 Data Migration 段或写 N/A，但 diff 实际涉及上述场景 → 报偏差。

## 严格核对步骤（必做，先做这一步再下结论）

### Step 1: Structure 文件存在性核对
1. 列出 spec "## 4. Structure（目录/模块）" 段所有提到的文件路径
2. 对每个文件：
   - 用 Bash + `git ls-files <path>` 验证文件**在工作树存在**（不是只看 diff）
   - 如果文件存在 + diff 没显示 = 可能 diff 截断了，**不要直接报"未实现"**
   - 用 Read 工具看文件实际内容，检查是否实现了 spec 要求的功能
3. 只有文件**真的不存在** 或 内容**真的与 spec 不符** 才作为 issue
4. diff_content 是参考，**工作树状态是真相**

### Step 2: User Flow 步骤逐条 trace
1. 如果 spec "## 2. User Flow" 段非 "N/A"，**逐条**列出每个用户动线步骤
2. 对每一步：
   - 找代码里的实际入口（grep widget 名 / API 路径 / 按钮文案 / icon name）
   - 用 Read 看入口附近的 guard / 条件渲染 / 路由跳转
   - 验证**实际可达**：用户按 spec 描述的路径操作，能不能真的看到/触发那个功能
3. 偷工模式硬禁：subagent 实现报告里如出现 "**先跳过 UI 入口**" / "**留 service API 可调**" / "**主动触发暂时不做**" 这类妥协措辞，对应 spec User Flow 段如要求 UI 触发，**必须报 issue**
4. spec Testing 段如要求"模拟器/真机手工 E2E 验收"，diff 里**必须**有 reports/ 截图记录或 commit message 提及实测；没有的话报 issue：「Spec 要求手工 E2E 验收但 diff 无任何实测痕迹」
5. HTTP / 数据库 / 外部依赖类改动如只有 mock 单测，没有任何"真实链路"集成测试，spec Testing 段又要求"集成测试"的，报 issue：「<file> 只有 mock 单测，spec 要求集成测试，未见真实 HTTP/DB 链路验证」
6. **数据源 trace（关键）**：若 flow 步骤是"看到列表/历史/X 的集合"这类**数据展示**类，必须 trace 到数据源（DB query / API 调用 / 缓存 / 文件）：
   - 找到查询的过滤条件（WHERE 子句、参数）
   - **用项目对应的 DB 工具（sqlite3 / psql / mysql / mongosh / redis-cli 等）抽查至少 5 行真实数据**，确认能匹配过滤条件
   - 若新增了过滤字段（如 WHERE kind='X'）但老数据该字段为 NULL/缺失 → 报"数据源 file:line 按 X 过滤但现有数据全部不匹配"
7. 若 spec 说"上传后立即看到 X"但代码在 `if (已答完 Y)` 里才渲染入口 → 报 `文件:行号 - 门槛 A，spec 要求 B`
8. **测试覆盖率检查（关键）**：对照 spec "## 2. User Flow" 段列出的**每个分支节点**，到测试代码（单元 / 集成 / E2E）grep 对应断言：
   - User Flow 第 N 步的关键 symbol / 数据状态（如"OCR 整篇" / "多轮反馈" / "stage=done" / "award_reward 触发"），测试里必须有对应 assert
   - **抄近道反模式**：E2E 脚本如果用 `force_*=true` / `skip_*=true` / `mock 业务逻辑参数` 绕过本该走真实路径的分支节点 → 报 "测试用 force_xxx 抄近道绕过 User Flow 步骤 N，未真实覆盖该分支"
   - **断言强度**：测试只检查"API 返回非空 + status_code=200"算弱断言。spec 涉及的 DB 字段（essay_text/feedback_summary/stage 等）测试中必须有 assert，否则报"测试断言过弱，未验证 spec 要求的最终数据状态"
   - 覆盖率门槛：spec User Flow 列出 N 个分支节点，测试覆盖 < N/2 → 报"测试覆盖率不足，missing branches: X, Y, Z"
9. **持久化字段真实性 trace（schema-as-truth 反陷阱）**：spec / model 里出现 `image_url` / `file_path` / `*_url` / binary blob 字段时，**字段存在 ≠ 功能就绪**，必须验证真实写盘 + 可访问：
   - 找到写字段的代码（grep `<field_name> = `）。若赋值是 **占位字符串**（如 `f"[xxx_{{id}}]"`、`"placeholder"`、`f"/dummy/..."`） → 报 "<file:line> 字段 X 只赋占位字符串，binary 从未真实写入存储"
   - 找上传/接收端：是否 `open(path, 'wb').write(binary)` 或调用对象存储 SDK？若没有 binary 落盘代码 → 报 "<file> 接收 binary 后未 persist，仅做了 OCR/parse 即丢弃"
   - 找静态服务：spec 涉及 url 字段的，工程是否 `app.mount('/uploads', StaticFiles(...))` 或等价路由？若 mount 不存在或 mount 路径与字段值前缀不匹配 → 报 "静态服务未挂载或路径不一致，URL 字段无法被 client 访问"
   - 复合字段（JSON 数组）：spec 说"feedback_items 是建议列表"，测试断言**每个 element 是独立短句**（< N 字 + 不含 \n\n），不能只断言数量。整段塞为单条 → 报 "复合字段子结构未验证"
10. **ORM / 框架级"自动覆盖"反误报**（防止把声明式实现误报为缺失）：spec 要求"启动跑迁移"/"schema drift 检查加表字段"等持久化类约束时，下结论前**必须 grep 工程**确认是否已通过框架自动覆盖：
   - 报"startup 没跑 migration"前：`grep -rn 'create_all\|Base.metadata' app/ src/`，若 startup 有调用 `init_db()` / `Base.metadata.create_all()` 且新 model 已声明 → SQLAlchemy 等 ORM 会自动建新表，迁移已覆盖，**不报**
   - 报"drift 检查没加表字段断言"前：读 `check_schema_drift.py` / 同类脚本，若用 `Base.metadata.tables.values()` / `inspect(engine)` 动态遍历 → 新 model 自动覆盖，**不报**
   - 报"未注册路由"前：grep `include_router` / `app.add_url_rule` / `@app.route`，若新 router 已注册 → **不报**
   - 通用原则：先确认"框架级声明能否在运行时自动生效"，再判定 spec 要求是否真未实现。**spec 字面找不到对应代码 ≠ 未实现**。

### Step 3: 综合判断
- 任意 Step 1/2 命中 issue → consistent: false
- diff_content 是参考，**工作树状态是真相**

允许工具：Bash、Grep、Read、Glob

Respond **only** in this format:

```json
{{"consistent": true|false, "issues": ["issue1", "issue2"]}}
```

- `consistent: true` means the change fully implements what spec asks without violating boundaries.
- `consistent: false` means there's at least one deviation. List each in `issues`.
- Keep `issues` short and specific (one sentence each, point to file:line when possible).
- **Issue 措辞优先用中文术语**：「集成测试」「测试数据」「mock 替代真实业务」「UI 入口缺失」「数据源」「空列表」「迁移策略」等。spec 是中文时尤其要保持术语一致，避免 "Integration test" 这类英文混入导致下游匹配失败。

Focus: {focus}
