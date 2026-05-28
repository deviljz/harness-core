---
description: 按 harness spec 逐项执行实现
argument-hint: <spec-path>
---

按 spec `$ARGUMENTS` 执行实现。

## 执行步骤

1. 读 `$ARGUMENTS`，确认 complexity 字段：
   - **simple** → 直接在当前会话实现
   - **complex** → 为每个执行项起 subagent（通过 Agent 工具，**必须显式 `model="sonnet"`**——写代码任务 sonnet 足够，默认 Opus 烧钱 5x）
2. 运行 `harness execute "$ARGUMENTS"` 解析执行表（若存在）。
3. 按 Structure 区列出的文件逐项改动。每改完一个文件：
   - 自动有 PostToolUse hook 跑 `harness check --on-edit` 验证
   - 若 hook 报 fail → 先修再继续下一项
4. 全部实现后让用户跑 `/harness-review $ARGUMENTS` 审查。

## 硬约束

- 不允许偏离 spec 的 Boundaries（非目标）
- 每个执行项必须映射到 spec 的某一段
- complex 任务必须用 subagent 隔离，避免污染主上下文
- **TDD 红绿铁律**：每个执行项按 spec §6「RED → GREEN → REFACTOR」严格顺序：
  1. subagent 先按 §6 测试矩阵写测试代码
  2. **跑测试确认 FAIL（RED）** — 报告中必须贴 pytest/flutter test 错误输出作为证据
  3. **独立 commit**：`test(scope): RED for <feature>`
  4. 再写实现代码
  5. 跑测试确认 PASS（GREEN）— 贴证据
  6. **独立 commit**：`feat(scope): implement <feature>`
  7. 若需要重构，在测试全绿下做（REFACTOR），独立 commit `refactor:`
- subagent 报告若缺 RED 失败证据 = 跳了 RED step，主 AI 必须 push-back 重做
- **Cross-cutting 历史风险扫描（必须）**：subagent 实现新组件前，必须先扫描工程历史是否有"加同类组件就该做 X"的成文规则：
  1. 若本次新增 N 个同类组件（chart / table / tab / form / route），grep 工程里已有的同类组件代码，看它们是怎么处理 click/hover/submit/auth 等共性约束的
  2. 在本次新组件代码里照搬同样模式，**禁止只加 DOM 不绑 handler / 只声明 model 不注册 admin / 只加 route 不挂 middleware**
  3. 遇到 push 模式（每处手动绑、每处手动注册）且新增组件 ≥ 3 个时，**主动询问主 AI 是否改 pull 模式**（公共 hook / decorator / mixin 兜底）。理由：push 模式下次加新组件必漏，已经发生过 13 chart 漏绑 click handler 8 个版本没抓到的事故
- **连通性自检（必须）**：subagent 完成实现 + 测试 GREEN 后，提交前必须自查：
  1. spec 提到的每个 helper / handler / hook，是否被 spec 列出的每个新组件**实际调用**？grep helper 名字看调用点（不是定义点）
  2. 若 spec 写"X + Y helper"但 X 的代码上下文里找不到 `Y(` 调用 → 视为"代码没连"，必须补上调用再 commit
  3. 报告里必须**显式列出**："新组件列表 [A, B, C] × helper [Y]，连通性已逐一验证，调用点：A.js:42 / B.js:78 / C.js:103"
- **修复完整性扫描（race / 鉴权 / 按钮 disable 类修复必须扫同模块同类入口）**：subagent 修 race condition / button disable / 鉴权类 bug 时，**禁止只修被现场触发的那一处**，必须扫描同模块所有同类入口：
  1. 修 race 时：grep 同模块（如 `screens/*.dart` / `pages/*.jsx`）所有 `async` / `await` / `Future<` 异步入口，逐个验证按钮 disable 是否一致
  2. 修后端鉴权（加 verify_token）时：grep 前端 api service 调用方，验证对应端点都能拿到 token（推荐 axios.interceptors / fetch wrapper 等 pull 模式而非每处手动加）
  3. 修 URL path 参数提取 bug 时：grep 工程所有 `/api/*` 路由，找出含数字的 path，逐个验证语义对应正确（user_id / wish_id / task_id 不能混）
  4. 报告中必须**显式列出"修了 N 处 + 扫描了 M 处同类入口、其中 P 处也补了同类保护"**。仅修 1 处而不报告同模块扫描结果 = 修复不彻底，已发生过 d5e5000 修 add-media race 但漏 first-create-draft race 的事故
