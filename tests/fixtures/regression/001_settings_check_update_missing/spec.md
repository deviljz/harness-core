# Spec: App 检查更新功能

## 1. Objective
用户可以在设置页手动触发"检查更新"，若有新版本则提示下载。

## 2. User Flow
1. 用户在主界面点击右上角齿轮图标，进入设置页（SettingsScreen）
2. 设置页展示"检查更新"列表项（check_update_tile）
3. 用户点击"检查更新"，调用 UpdateService.checkUpdate()
4. 若有新版本：弹出 Dialog 提示版本号 + 下载按钮
5. 若已最新：Toast 提示"已是最新版本"

## 3. Commands
- GET /api/app/version — 返回 { latest_version, download_url }

## 4. Structure
- mobile/lib/services/update_service.dart — UpdateService.checkUpdate()
- mobile/lib/screens/settings_screen.dart  — SettingsScreen with check_update_tile
- mobile/lib/screens/main_tab_screen.dart  — 冷启动静默检查

## 5. Style
- 遵循现有 Material Design 3 风格
- 使用 package:http 发 HTTP 请求

## 6. Testing
- Widget test: 点击"检查更新"按钮 → mock UpdateService → 验证 Dialog 出现
- Integration test: 真起 backend，真调 /api/app/version，验证 Dialog 内容

complexity: simple
