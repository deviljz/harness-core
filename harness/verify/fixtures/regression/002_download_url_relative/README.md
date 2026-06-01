# Regression 002: 下载 URL 使用相对路径

## 背景

spec 要求 download_url 必须是绝对 URL，且要有集成测试（真起 backend 真下载）。
实现中 `Uri.parse(downloadUrl)` 直接使用服务端返回的相对路径 `/download/app-1.2.0.apk`，
运行时会因缺少 host 而失败。测试全是 mock，集成测试缺失。

## 预期行为

review 应检测到相对 URL 问题 + 只有 mock 无集成测试，判定 consistent=false。

## 为何重要

mock 测试全绿不等于行为正确——这是"测试只验证了 mock 本身"的典型案例。
