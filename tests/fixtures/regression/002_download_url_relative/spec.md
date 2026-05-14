# Spec: APK 下载功能

## 1. Objective
用户点击"下载更新"后，App 下载新版 APK 并提示安装。
下载链接由后端 /api/app/version 返回的 download_url 字段提供。

## 2. User Flow
1. 用户在检查更新 Dialog 点击"下载"按钮
2. App 使用绝对 URL 发起 HTTP GET 请求下载 APK
3. 下载完成后，调用平台安装器安装 APK

## 3. Commands
- GET /api/app/version → { latest_version: "1.2.0", download_url: "https://cdn.example.com/app-1.2.0.apk" }

## 4. Structure
- mobile/lib/services/update_service.dart — downloadApk(String downloadUrl) 使用绝对 URL
- mobile/test/update_service_test.dart    — 集成测试：真起 backend，真发请求，验证 200

## 5. Style
- download_url 必须是绝对 URL（https://...）
- 禁止直接拼接相对路径

## 6. Testing
- Integration test: 真起 backend，真发 GET /api/app/version，真下载 APK，验证 HTTP 200
- 不允许全 mock 替代集成测试

complexity: simple
