# dart 语言模块（占位）

当前**只有 `__init__.py` 占位**，没有实现。Dart / Flutter 工程暂时只能走 `language: fallback` 模式。

## 状态

`harness/languages/dart/__init__.py` 暴露了 `DartModule` 但实际未实现 4 个核心方法：
- `find_related_tests`
- `run_tests`
- `parse_results`
- `deep_check`

如果在 config.yaml 写 `language: dart`，会回落到 fallback 行为（不一定符合预期）。

## 想贡献完整实现？

参考 `harness/languages/python/` 完整 5 文件结构，或 `harness/languages/unity_csharp/`（外部贡献的范例）：

- `__init__.py` — 模块导出
- `module.py` — 4 方法 dispatcher
- `finder.py` — 文件名约定 + import grep 找相关测试
- `runner.py` — `flutter test <files>` 子进程 + 解析 JSON / TAP 输出
- `assertion_ast.py` — 用 dart `analyzer` 包做 AST 反模式（如自递归 getter）

Dart 工程典型坑（建议先沉淀 anti_patterns）：
- `^\s*\w+(\?|<[^>]+>)?\s+get\s+(\w+)\s*=>\s*\2\s*;` 自递归 getter 必爆栈
- `setState\(\(\) \{\s*\}\)` 空 setState 触发不必要重建
- `Future<.+>` 未 await 漏 lint

PR 欢迎到 https://github.com/deviljz/harness-core/pulls
