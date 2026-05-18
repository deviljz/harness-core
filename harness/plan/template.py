"""spec 模板（8 大区 + complexity 字段）"""
from __future__ import annotations

import time

DEFAULT_SPEC_TEMPLATE = """# {task_name}

> 方案层产物。按 8 大区填写，complexity 必填。

**complexity**: simple  <!-- simple | complex -->

---

## 1. Objective（目标）

**做什么**：

**为什么做**：

**用户是谁**：

**成功标准**（可验证）：
1.
2.
3.

**非目标**：
-

---

## 2. User Flow（用户动线）

> UI 类任务必填；纯后端 / 工具类写 "N/A - 无用户交互"。
> 每步格式：用户在 X 页做 Y → 看到 Z。

---

## 3. Commands（提供哪些命令/接口）

-

---

## 4. Structure（目录/模块）

```
项目里涉及的文件/模块清单
```

---

## 5. Style（代码风格 / 依赖选型）

-

---

## 6. Testing（测试策略）

> **边界值覆盖（必须）**：每个用户输入字段、DB nullable 列、外部 API 返回字段，必须有 NULL / 空 / 非法值测试用例。典型坑：`user.grade=NULL` 让 `None < 1` 崩溃 500。在测试矩阵里**每个 nullable 字段单独列一行边界测试**。
>
> **Deploy-time Smoke Test（涉及 CDN / 域名 / 缓存时必须）**：spec 改动经过生产 CDN 分发或 cache 层（如 APK 下载、静态资源、API CDN 缓存）时，必须有发版后跑的脚本：真用 curl 下载生产 URL + 校验文件 hash / version code / Cache-Control header 与预期匹配。本地 TestClient 跳过 CDN，测不出缓存问题。
>
> **TDD 红绿铁律（必须遵守）**：每个测试矩阵条目必须按 RED → GREEN → REFACTOR 严格顺序：
> 1. **RED**：先写测试，跑一次确认失败（NotImplementedError / AssertionError / 404 等）
> 2. **GREEN**：写最小实现让测试通过
> 3. **REFACTOR**：在绿测试保护下重构
>
> execute subagent 必须**先 commit 一次测试代码**（独立 commit `test(scope): RED for <feature>` + 跑测试输出贴证据），再 commit 实现（`feat(scope): implement <feature>`）。
> 实现先写、测试后补 = **违反 TDD**，review 会报偏差。
>
> **测试矩阵（必填）**：对照 §2 User Flow 列出每个分支节点对应的测试用例 + 关键断言点。
> **happy path 端到端覆盖**：必须有一条测试真走完 §2 全部主路径，**禁止用 force_* / skip_* / mock 业务逻辑等参数抄近道绕过分支**。
>
> **三类测试必须各 ≥ 1 条（必须遵守）**：smoke 全绿 ≠ 功能可用。8 个版本攒下来 13 个 chart 都没绑 click handler 但 selector count 测试全过——根因就是只测"存在"不测"连通"。每个 §6 矩阵必须覆盖：
> 1. **存在性 (existence)**：DOM / 函数 / 类 / 数据结构是否被定义。典型断言：`querySelectorAll('#x').length >= 1` / `typeof renderX === 'function'` / `model.columns has 'x'`。
> 2. **交互性 (interaction)**：用户/系统触发事件后**状态真的变了**。典型断言：`dispatchEvent(new MouseEvent('click', ...))` 后 `assert SELECTED_FRAME > 0` / `fireEvent.click(btn)` 后 `expect(state).toBe('updated')` / `await page.click('#x'); await expect(page.locator('#y')).toHaveText('...')`。
> 3. **完整性扫描 (cross-cutting)**：同类元素是否都满足同类约束。典型断言：`for chart in document.querySelectorAll('svg.chart'): assert chart.dataset.hoverAttached === 'true'` / `for route in app.routes: assert route has auth middleware` / grep 全部 `Model.objects.filter(...)` 没有缺索引的。
>
> 三类必须各 ≥ 1 条；只有"存在性"的 §6 = 抓不到"代码没连"类 bug，validate 会报 warning。

> **Push vs Pull 模式自检（必须）**：spec 涉及"新增 N 个同类组件"（多个 chart / 多个表单 / 多个路由）时，必须在 §6 加一条 cross-cutting 测试扫描所有同类元素。如果 §6 测试只挨个验证每个组件，没有"扫描全部同类"的断言 → 说明走的是 push 模式（每处手动注册），下次加新组件必漏。**优先考虑公共 hook 兜底（pull 模式）**：渲染完成后扫所有未注册元素自动处理，而不是要求每处主动调用。

| 分支节点（对应 User Flow 第 N 步） | 测试用例 | 关键断言 |
|---|---|---|
| 例：步骤 3 OCR 拍照判定整篇 vs 片段 | tests/test_xxx.py::test_full_essay_enters_feedback | DB.current_essay_text 非空 + stage='feedback' |
| 例：步骤 5 多轮反馈累积 | tests/test_xxx.py::test_feedback_accumulates | feedback_summary 含 ≥2 轮 |

- 单元测试：
- 集成测试：
- E2E：

> **UI Smoke Test（涉及前端 UI 时必填，不能只靠"手工过目"）**：
> spec 涉及网页 / App UI 渲染时，必须有自动化 UI smoke test：
> - 网页：Playwright 启 dev server + 登录 + 导航到关键页 + assert 关键文字存在（如「第 N 轮反馈」「错误提示」「核心按钮 label」）+ 截图存 `reports/<feature>_<tab>_<ts>.png`
> - App：Flutter widget test 用 `find.byIcon` / `find.text` 验证关键 UI 元素在 widget 树（不依赖真实后端）
> - **review 静态比对 spec↔diff 抓不到 UI/UX bug**（如内部协议字段泄漏到 chat 气泡、JSON.stringify 渲染原始字串、markdown 不渲染显示 raw `**`）—— 必须靠 UI smoke test 实际跑。

---

## 7. Boundaries（边界）

### 绝不做
-

### 必须做
-

---

## 8. Data Migration（数据迁移）

> 涉及数据存储（DB / 文件 / 缓存）变更时必填，否则写 N/A。
> 经验教训：加新字段 + 按字段过滤但不回填，会让"现有数据全部消失"——这是普遍盲区。

### 现有数据现状
- 涉及的表/集合：
- 现有行数 / 关键字段值分布：
- 是否兼容新代码：

### 迁移策略（至少选一项）
- [ ] 回填脚本 / SQL：
- [ ] 写入启动迁移（幂等）：
- [ ] 新代码显式兼容 NULL / missing 值（说明兼容逻辑）：

---

## 执行计划（可选）

| 阶段 | 交付物 | 估时 |
|---|---|---|
|  |  |  |
"""


def render_template(task_name: str) -> str:
    """生成 spec 骨架。task_name 会塞进标题。"""
    return DEFAULT_SPEC_TEMPLATE.format(task_name=task_name)


def spec_filename(task_name: str) -> str:
    """标准命名：<date>_<slug>.md"""
    date = time.strftime("%Y%m%d")
    slug = task_name.strip().replace(" ", "_").replace("/", "-")
    return f"{date}_{slug}.md"
