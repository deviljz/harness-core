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

> **测试矩阵（必填）**：对照 §2 User Flow 列出每个分支节点对应的测试用例 + 关键断言点。
> **happy path 端到端覆盖**：必须有一条测试真走完 §2 全部主路径，**禁止用 force_* / skip_* / mock 业务逻辑等参数抄近道绕过分支**。

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
