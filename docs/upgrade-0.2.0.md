# harness-core 0.2.0 升级指南（给项目 AI）

> 这份文档是给项目内 AI 看的。读完按下面顺序做，**全程不要询问**，做完汇报。

## 0.2.0 带来什么

- `harness check` 内置两个 cross-target check：
  - `anti_patterns`：按文件扩展名匹配语言，跑配置的正则反模式
  - `core_modules_coverage`：配置列出的核心源文件必须有对应测试
- 新 skill `/harness-full`：execute → check → review → commit 一条龙
- 老 config 100% 向后兼容（缺新段 = 不跑新检查）

## 步骤

### 1. 升级 harness-core 二进制

```bash
pip install -e C:/Users/zhe_jin/workspace/harness-core --force-reinstall --no-deps
```

确认：
```bash
python -c "from harness.validate.anti_patterns import run_anti_patterns; print('ok')"
```

### 2. 重跑 harness init 同步新 skill

```bash
harness init
```

确认 `.claude/commands/harness-full.md` 已存在。

### 3. 在 `.harness/config.yaml` 顶层加 anti_patterns 段

根据本项目主要语言，从下面 yaml 抄过去，**只保留本项目实际用到的语言段**：

```yaml
anti_patterns:
  dart:
    - name: self_recursive_getter
      pattern: '^\s*\w+(\?|<[^>]+>)?\s+get\s+(\w+)\s*=>\s*\2\s*;'
      msg: "自递归 getter 必爆栈 (StackOverflowError)"
      severity: error
    - name: self_recursive_arrow_method
      pattern: '^\s*\w+\s+(\w+)\([^)]*\)\s*=>\s*\1\([^)]*\);'
      msg: "自递归 arrow 方法（无参数变化）必爆栈"
      severity: error
  python:
    - name: bare_except
      pattern: '^\s*except\s*:\s*$'
      msg: "禁止裸 except"
      severity: error
    - name: mutable_default_arg
      pattern: 'def \w+\([^)]*=\s*(\[\]|\{\})\s*[,)]'
      msg: "可变默认参数跨调用共享状态"
      severity: error
  typescript:
    - name: self_recursive_arrow
      pattern: 'const (\w+)\s*=\s*\([^)]*\)\s*=>\s*\1\([^)]*\)'
      severity: error
  all:
    - name: api_key_leak
      pattern: '(AIza[0-9A-Za-z_-]{35}|sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36})'
      msg: "疑似 API Key 硬编码，必须移到 .env"
      severity: error
```

支持语言扩展名：dart / python / typescript(.ts/.tsx) / javascript(.js/.jsx) / go / rust / java / kotlin / swift / "all"（所有扩展名）。

### 4. 加 core_modules_coverage 段

自己分析本项目，列 3-8 个核心模块（崩了用户最痛苦的那些）：

```yaml
core_modules_coverage:
  - path: src/foo/bar.py
    must_have_test: tests/test_bar.py
    reason: "为什么这是核心"
```

缺测试只 warn 不 fail，渐进补即可。

### 5. End-to-end 验证

在 `tmp/` 临时建一个含反模式的文件（按本项目语言选）：

```dart
// tmp/bug.dart
class A {
  int get x => x;
}
```

跑：
```bash
harness check --on-edit tmp/bug.dart
```

应输出含 `<check name="anti_patterns" status="fail">` 和具体 line 号。验证完删 tmp/ 文件。

### 6. Commit 到 dev 分支

```
refactor(harness): 升级到 0.2.0 内置反模式检查 + 配置核心模块清单
```

## 硬约束

- **不要**在项目内再写 post_edit_check.py 这类脚本，反模式检查已经是 harness-core 内置能力
- **不要**改 harness-core 源码（除非要加新语言支持，那种走 PR）
- **全程不要询问用户**，按上面顺序做完，最后汇报「升级完成，已抓到 N 处历史问题 / 配了 M 个核心模块」
- 如果某条规则对本项目误报 → 改 `.harness/config.yaml` 那一条的正则，**不要禁用整条规则**

## 参考

- spec 文档：`C:/Users/zhe_jin/workspace/harness-core/docs/tasks/20260513_anti-patterns_+_core_modules_check.md`
- 喵辅导项目落地范例：`F:/Project/MiaoStudy/.harness/config.yaml`（看 `anti_patterns` 和 `core_modules_coverage` 段）
