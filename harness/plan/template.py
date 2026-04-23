"""spec 模板（6 大区 + complexity 字段）"""
from __future__ import annotations

import time

DEFAULT_SPEC_TEMPLATE = """# {task_name}

> 方案层产物。按 6 大区填写，complexity 必填。

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

## 2. Commands（提供哪些命令/接口）

-

---

## 3. Structure（目录/模块）

```
项目里涉及的文件/模块清单
```

---

## 4. Style（代码风格 / 依赖选型）

-

---

## 5. Testing（测试策略）

-

---

## 6. Boundaries（边界）

### 绝不做
-

### 必须做
-

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
