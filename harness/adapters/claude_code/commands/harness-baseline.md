---
description: 对标参考实现，扫覆盖度差距写入 spec（mirror/parity 工具开发）
argument-hint: <reference-url-or-html-path>
---

对标参考实现 `$ARGUMENTS`，审计当前实现的功能覆盖度差距，把差距表写进 spec。

## 何时用

开发"对标类"工具（镜像/对齐某个已有产品）时：工程师视角"已实现 X 模块"，但用户视角"功能只有一半"——因为没把"对照参考实现列功能点"放进 plan。本命令把这步自动化。

触发词：对标 / 对齐 / 对照 / parity with / vs UWA / vs GraphyPro 等，且 Objective 含 URL 或本地 HTML 路径。

## 执行流程

1. **确定 source 与 target**：
   - `source` = 参考实现：`$ARGUMENTS`（URL 或本地 HTML 路径）
   - `target` = 当前实现的 HTML / 入口文件（在工程里找，找不到就问用户）
   - `spec` = 要写入差距小节的 spec.md（通常是当前 plan 阶段那份；没有就先 `/harness-plan` 建）

2. **跑扫描**（skill 自带 CLI，主 `harness` CLI 未注册 baseline 子命令，用 `python -m`）：
   ```bash
   python -m harness.skills.harness_baseline.cli scan \
     --source "$ARGUMENTS" \
     --target <当前实现 HTML 路径> \
     --spec <spec.md 路径>
   ```
   可选参数：`--sidebar-selector <css>`（自定义侧边栏选择器）、`--fuzzy-threshold 0.6`（partial 匹配阈值）、`--top-level-only`。
   - 本地 HTML 直接可跑；URL 模式需 `playwright`（`pip install harness-core[playwright]`）。

3. **读结果**：scan 输出三态分类
   - ✓ aligned（同名同位置）
   - 🟡 partial（同名但缺 sub-metric / 列）
   - ❌ missing（参考有、当前没有）
   并把"## 覆盖度差距"小节追加进 spec.md。

4. **衔接 Boundaries（关键）**：scan 列出的每个 missing / partial 项，必须在 spec §7 Boundaries「绝不做」里**显式声明不做（带理由）**，或排进后续 milestone。避免"漏了"被混淆成"不做"。

## 硬约束

- source / target 必须都给到（缺一不可），target 找不到就问用户，别瞎猜
- 差距表必须真写进 spec（不是只打印到屏幕）
- missing 项不允许静默忽略——要么进 Boundaries 要么进 milestone
