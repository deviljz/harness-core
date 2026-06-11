# Spec: 移动端打卡多文件上传

## 1. Objective
移动端用户登录后，可在打卡时上传多张图片/视频，上传接口校验登录 token。

## 2. User Flow
1. 用户在 App 登录（POST /api/mobile/auth/login），拿到 JWT token
2. 用户选图打卡，App 带 Authorization: Bearer <token> 调上传接口
3. 上传接口校验 token，通过后保存媒体
4. 不变量：移动端登录签发的 token，上传接口必须认（同一套密钥签发与验签）

## 3. Commands
- POST /api/mobile/auth/login — 签发 JWT
- POST /api/tasks/submit — 校验 JWT 后上传

## 4. Structure
- app/routers/mobile_auth.py — 移动端登录，签发 token
- app/routers/auth.py — verify_token，上传接口依赖它验签

## 5. Style
- FastAPI 依赖注入；密钥来自配置

## 6. Testing
- 走真实 /api/mobile/auth/login 取 token，断言该 token 被 /api/tasks/submit 接受（非 401）
- 断言所有签发/验签处 SECRET_KEY 同源

## 7. Boundaries
- 不改前端 Web 登录

## 8. Data Migration
N/A

complexity: complex
