# 贡献语言专属反模式（anti_patterns）

> 让 harness 自动抓住「这次踩过、下次不想再踩」的 case。

## 原理

`harness check` 默认跑 `anti_patterns` 扫描，**纯正则、跨语言通用**，不需要 AST。配在每个项目的 `.harness/config.yaml` 即可，**不需要改 harness-core 主仓**。

文件扩展名 → 语言段映射在 `harness/validate/anti_patterns.py` 的 `EXT_TO_LANG`：

| 扩展名 | 语言段 |
|---|---|
| `.py` | `python` |
| `.dart` | `dart` |
| `.ts` `.tsx` | `typescript` |
| `.js` `.jsx` | `javascript` |
| `.go` | `go` |
| `.rs` | `rust` |
| `.java` | `java` |
| `.kt` | `kotlin` |
| `.swift` | `swift` |
| `.cs` | `csharp`（含 Unity） |

`all` 段对**所有**扩展名都跑。

## 反模式规则格式

在 `.harness/config.yaml`：

```yaml
anti_patterns:
  csharp:
    - name: <唯一规则名>          # 必填，报告里显示
      pattern: '<正则>'           # 必填，Python re 语法
      msg: "<报警信息>"            # 必填，说清楚为啥不让这么写
      severity: error | warn      # 必填
      multiline: true             # 可选，默认 false，多行匹配开启
      case: "YYYY-MM-DD <事件名>"  # 可选但强推荐：标注沉淀来源
      include: ["**/*.cs"]        # 可选，限定扫描文件
      exclude: ["**/Tests/**"]    # 可选，排除路径
```

## 写好规则的 5 条经验

### 1. 必须有 `case` 字段标注沉淀来源

```yaml
- name: systeminfo_battery_cached
  pattern: 'SystemInfo\.batteryLevel'
  msg: "Unity Android SystemInfo.batteryLevel 进程级缓存 5 分钟不更新"
  severity: warn
  case: "2026-05-22 Periscope BatteryTracker bug"  # ← 强制写
```

理由：3 个月后看到规则的人能 git 历史里找到当时为什么加这条。**没 case 的规则会变成"反正历史上有人加了我也不敢删"的死代码**。

### 2. severity 优先 `warn` 不优先 `error`

新加规则**必从 warn 开始**。`error` 会让 `harness check` 红灯阻断；规则误报率没经过验证就上 error，会逼用户把规则关掉。

规则跑稳 2 周 + 误报率 < 5% 后再升级 error。

### 3. 正则要尽量精确，宁愿漏报不要误报

```yaml
# ❌ 太宽：catch 任何东西都报
pattern: 'catch'

# ✅ 精确：只抓"空 catch 块"
pattern: '^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$'
```

误报会让 reviewer 忽略整条规则，比漏报危害大。

### 4. 多行模式用 `multiline: true`

需要跨行匹配（如「函数 A 调用 B 但 B 内部又调用 A」这类）才开。**默认关**——单行正则跑得更快。

```yaml
- name: capture_screenshot_linear_rt
  pattern: 'CaptureScreenshotIntoRenderTexture[\s\S]{0,200}?RenderTextureReadWrite\.Linear'
  multiline: true
  msg: "Linear RT 会让 JPG 黑屏"
```

### 5. exclude 测试目录

```yaml
- name: hardcoded_localhost
  pattern: 'localhost:\d+'
  severity: error
  exclude:
    - "**/tests/**"
    - "**/Tests/**"
    - "**/*Test.cs"
    - "**/*_test.py"
```

测试里用 `localhost` 是合理的。

## 沉淀流程

**触发条件**：每次踩到 bug 修完后，自问：
1. 这个 bug 的形态能用一个正则匹配出来吗？
2. 同样的写法在工程其他地方还有几处？

如果都是 yes，写一条规则：

```bash
# 1. 在 .harness/config.yaml 加规则（severity 先用 warn）
# 2. 跑一次扫描看 hits
harness check --rules anti_patterns
# 3. 检查 hits 是否合理：误报多 → 改正则；漏报真 bug → 修代码
# 4. 跑稳 2 周后升级 severity 到 error
```

## 示例：从 Periscope 5 个 bug 沉淀的 C# 反模式

```yaml
anti_patterns:
  csharp:
    - name: systeminfo_battery_cached
      pattern: 'SystemInfo\.batteryLevel'
      msg: "Unity Android SystemInfo.batteryLevel 进程级缓存 5 分钟不更新，改用 BatteryManager.getIntProperty(BATTERY_PROPERTY_CAPACITY)"
      severity: warn
      case: "2026-05-22 Periscope BatteryTracker bug"

    - name: capture_screenshot_linear_rt
      pattern: 'CaptureScreenshotIntoRenderTexture[\s\S]{0,200}?RenderTextureReadWrite\.Linear'
      multiline: true
      msg: "Linear RT 致 JPG 黑屏。CaptureScreenshotIntoRenderTexture 必须配 RenderTextureReadWrite.Default(sRGB)"
      severity: error
      case: "2026-05-22 Periscope 截图黑屏 bug"

    - name: empty_catch
      pattern: '^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$'
      msg: "禁止裸 catch 空块，会吞掉所有异常"
      severity: error

    - name: debug_log_no_module_prefix
      pattern: 'Debug\.Log\("(?!\[)'
      msg: "Debug.Log 必须以 [Module] 前缀，便于运行时过滤"
      severity: warn
      include: ["Assets/Scripts/**/*.cs"]
      exclude: ["Assets/Scripts/Editor/**", "**/Tests/**"]
```

## 上游回馈

如果某条规则对 5+ 个项目都通用，**给 harness-core 主仓发 PR**——加到 `harness/validate/default_anti_patterns.py`（待创建）让所有项目默认启用。

PR 模板：
- 规则 yaml（含 case 字段）
- 至少 3 个工程的复现示例
- 误报率统计（跑过 2 周 + < 5% 误报）
