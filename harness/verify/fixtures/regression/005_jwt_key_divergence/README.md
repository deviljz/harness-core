# Regression 005: 签发 / 验签 JWT 密钥不同源 → 上传 401

## 背景

2026-06 给移动端打卡新增多文件上传链。移动端登录 `mobile_auth.py` 用硬编码
`SECRET_KEY = "miaofudao-secret-key-change-in-production"` 签 token，
而上传接口 `auth.verify_token` 用 `get_settings().SECRET_KEY`（读 .env）验签。
测试环境两者恰好相同所以没踩到；生产 .env 改了密钥后，App 登录拿到的 token
被上传接口判无效 → 一律 401，但首页只读接口不校验 token 照常加载，用户误以为已登录。
(commit d1072cc 修复：三处密钥统一 settings.SECRET_KEY + test_jwt_keys.py 守卫)

## 预期行为

review 应发现：新增上传链时，token 签发处(mobile_auth)与验签处(auth.verify_token)
的 SECRET_KEY 来源不一致（一处硬编码、一处读 settings），生产换密钥必 401。
判定 consistent=false。

## 为何重要

鉴权链路"密钥同源"盲区：新增/改动上传或调用链时，必须核对 token 签发处 vs 验签处
密钥同源。多处硬编码密钥在发版换密钥时必漏一处。测试环境密钥恰好相同会掩盖问题。
