"""Score v9 (边界值 + deploy-time smoke test 检查)."""
import json
from pathlib import Path
from harness.verify.matchers import match as kw_match

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / "tmp_verify_prompts" / "manifest.json").read_text(encoding="utf-8"))

actuals = {
    "001_settings_check_update_missing": {
        "consistent": False,
        "issues": [
            "mobile/lib/screens/settings_screen.dart 文件不存在，spec §4 要求该文件实现 SettingsScreen with check_update_tile，UI 入口缺失",
            "User Flow 步骤 2-3 未实现：设置页「检查更新」列表项（check_update_tile）及点击触发 UpdateService.checkUpdate() 的 UI 入口均缺失，subagent 报告明确写「先跳过 UI 入口」，属于偷工模式硬禁场景",
            "User Flow 步骤 4-5 未实现：有新版本时弹出 Dialog 提示版本号 + 下载按钮、已最新时 Toast 提示「已是最新版本」均未在任何文件中实现",
            "main_tab_screen.dart initState 冷启动检查结果处理为空 TODO，spec §4 要求冷启动静默检查实际展示逻辑，当前 TODO 注释不算实现",
            "spec §6 要求 Widget test（点击「检查更新」按钮 → mock UpdateService → 验证 Dialog 出现）和集成测试（真起 backend 调 /api/app/version），工作树中无任何测试文件",
            "未走 RED-first TDD 铁律：git log 无任何 test(...) commit，所有改动只有 feat commit，spec §6 要求 test commit 先于 feat commit 入库",
        ],
    },
    "002_download_url_relative": {
        "consistent": False,
        "issues": [
            "update_service.dart:14-19 downloadApk() 未验证 downloadUrl 是绝对 URL，代码注释明确标注 BUG：相对路径会在运行时失败，违反 spec §5 禁止相对路径规则",
            "update_service_test.dart 全部使用 MockClient，无任何真实 HTTP 请求，spec §6 明确要求集成测试：真起 backend、真发请求、真下载 APK、验证 HTTP 200，不允许全 mock 替代集成测试",
            "update_service_test.dart:21 mock 返回 download_url 为相对路径 '/download/app-1.2.0.apk'，与 spec §3 要求返回绝对 URL（https://cdn.example.com/...）不符",
            "update_service_test.dart:28-31 downloadApk 测试断言过弱，只断言 isA<bool>() 未验证 HTTP 200，且入参使用相对路径绕过了 spec §5 规定的绝对 URL 校验",
        ],
    },
    "case_01_happy_path": {"consistent": True, "issues": []},
    "case_02_ui_skipped": {
        "consistent": False,
        "issues": [
            "settings_screen.dart AppBar 缺少 close_button（Icons.close IconButton），spec §2 User Flow 第2步要求右上角 X 按钮，代码注释明确标注'intentionally omitted'",
            "spec §6 要求 widget test 验证点击 X 按钮触发页面 pop，worktree 内无任何测试文件",
            "未走 RED-first，TDD 红绿铁律违反，spec §6 要求 test commit 先入库，但无任何 test commit",
        ],
    },
    "case_03_url_relative": {
        "consistent": False,
        "issues": [
            "backend/main.py 不存在，spec §4 要求后端实现 /api/items 端点",
            "mobile/lib/services/item_service.dart:19 buildImageUrl fallback 赋值相对路径 '/images/default.png'，违反 spec §5 禁止返回相对路径规则",
            "缺少单元测试，spec §6 要求验证 image_url 以 'https://' 开头的测试，worktree 中无任何测试文件",
            "未走 RED-first，TDD 红绿铁律违反，spec §6 要求 test commit 先入库",
        ],
    },
    "case_04_only_mock": {
        "consistent": False,
        "issues": [
            "backend/main.py 不存在，spec §4 要求的 /api/login 路由未实现",
            "tests/test_login.py 全部用 mock 替代真实业务逻辑，从未调用 TestClient 真实请求，违反 spec §6「禁止用 mock 替代真实 DB/业务逻辑」和「用 TestClient 真调 POST /api/login」要求",
            "测试对 MagicMock() 对象断言（result.status_code == 200），未真实验证任何业务逻辑，属于无效集成测试",
        ],
    },
    "case_05_data_filter": {
        "consistent": False,
        "issues": [
            "spec §4 要求 backend/main.py 实现 /api/items?kind= 查询参数及 WHERE kind=:kind 过滤，但工作树中该文件不存在，核心 API 未实现",
            "spec §6 数据源 trace 要求测试数据必须包含 kind='exercise' 的行，否则测试无意义；但 tests/test_items.py 中 5 行测试数据全部为 kind=NULL，查询 kind='exercise' 返回空列表是因为无匹配数据而非过滤逻辑正确，测试系空洞通过（vacuously true）",
            "spec §5 要求必须在 SQL 层过滤（不在 Python 层），但 backend/main.py 根本不存在，SQL 层过滤逻辑未实现",
        ],
    },
}

print("=" * 86)
print(f"{'Fixture':<42} {'Result':<6} {'Detail'}")
print("=" * 86)
total = passed = 0
for entry in manifest:
    name = entry["name"]
    actual = actuals[name]
    res = kw_match(actual_consistent=actual["consistent"], issues=actual["issues"], expected=entry["expected"])
    total += 1
    if res.passed: passed += 1
    print(f"{name:<42} {'PASS' if res.passed else 'FAIL':<6} {res.detail}")
print("=" * 86)
print(f"Total: {passed}/{total} PASS  Recall: {passed/total:.0%}")
