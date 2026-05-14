"""Score actual subagent results (round 2, new template) vs expected.json."""
import json
from pathlib import Path
from harness.verify.matchers import match as kw_match

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / "tmp_verify_prompts" / "manifest.json").read_text(encoding="utf-8"))

actuals = {
    "001_settings_check_update_missing": {
        "consistent": False,
        "issues": [
            "mobile/lib/screens/settings_screen.dart 不存在于工作树，spec Section 4 要求该文件实现含 check_update_tile 的 SettingsScreen",
            "UI 入口缺失：main_tab_screen.dart 中齿轮图标点击为 TODO 占位，settings_screen.dart 完全未实现，用户无法通过 spec 描述的路径手动触发检查更新",
            "main_tab_screen.dart initState 冷启动检查的 checkUpdate() 回调为空 TODO，新版本时不弹 Dialog，不满足 User Flow 步骤 4",
            "spec 要求 Toast 提示'已是最新版本'（User Flow 步骤 5），diff 中无任何 Toast 实现",
            "spec 要求 Widget test 验证点击按钮后 Dialog 出现，diff 中无任何测试文件",
            "spec 要求集成测试真调 /api/app/version 验证 Dialog 内容，diff 中无集成测试，仅有 service 实现",
        ],
    },
    "002_download_url_relative": {
        "consistent": False,
        "issues": [
            "mobile/lib/services/update_service.dart:57 — downloadApk() 直接 Uri.parse(downloadUrl) 未校验是否为绝对 URL，注释已明确指出可能传入相对路径，违反 spec §5「download_url 必须是绝对 URL，禁止拼接相对路径」",
            "mobile/test/update_service_test.dart — 全部使用 MockClient，无任何真实 HTTP 链路，违反 spec §6「不允许全 mock 替代集成测试，须真起 backend 真发请求验证 HTTP 200」",
        ],
    },
    "case_01_happy_path": {"consistent": True, "issues": []},
    "case_02_ui_skipped": {
        "consistent": False,
        "issues": [
            "mobile/lib/screens/settings_screen.dart — AppBar 未添加 Icons.close 按钮（close_button），代码注释明确标注「intentionally omitted」，与 spec § 4/5 要求不符",
            "spec § 6 要求 widget test 验证点击 X 按钮触发页面 pop，diff 中无任何测试文件",
        ],
    },
    "case_03_url_relative": {
        "consistent": False,
        "issues": [
            "backend/main.py 未在 diff 中实现，spec 要求后端 /api/items 返回带绝对 image_url 的列表",
            "buildImageUrl 方法在 image_url 为 null 时回退到相对路径 /images/default.png，违反 spec「禁止返回相对路径」规定（item_service.dart:58）",
            "buildImageUrl 使用 Uri.parse 未校验 scheme，相对路径可直接通过，未强制 https:// 开头（item_service.dart:60）",
            "spec 要求单元测试验证 image_url 以 https:// 开头，diff 中无任何测试文件",
            "Flutter Image.network(item.image_url) 调用未在 diff 中实现，User Flow 第 3 步缺失",
        ],
    },
    "case_04_only_mock": {
        "consistent": False,
        "issues": [
            "tests/test_login.py 只有 mock 单测，spec 要求集成测试（用 TestClient 真调 POST /api/login），未见真实 HTTP/DB 链路验证",
            "测试中 mock 了 verify_password 和 create_token 等业务逻辑，违反 spec 明确禁止「用 mock 替代真实 DB/业务逻辑」的要求",
            "backend/main.py（/api/login 路由）在 diff 中完全缺失，spec Structure 要求此文件存在",
        ],
    },
    "case_05_data_filter": {
        "consistent": False,
        "issues": [
            "backend/main.py 未在 diff 中出现，spec Structure 要求实现 /api/items?kind= 端点并在 SQL 层加 WHERE kind=:kind 过滤",
            "测试数据 5 行全部 kind=NULL，spec Testing 明确要求测试数据必须包含 kind='exercise' 的行，否则测试无意义（数据源 trace 失败）",
            "test_items_filter_by_kind 断言 results==[] 属于空列表空过滤的假阳性，过滤逻辑从未被真实数据验证，集成测试无效",
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
