# Spec: 用户登录 API

## 1. Objective
后端提供 POST /api/login 端点，验证用户凭据，返回 JWT token。

## 2. User Flow
1. 用户输入邮箱 + 密码
2. App 调用 POST /api/login
3. 成功返回 { token: "..." }；失败返回 401

## 3. Commands
- POST /api/login { email, password } → { token } | 401

## 4. Structure
- backend/main.py — /api/login route
- tests/test_login.py — 集成测试（真请求，不 mock）

## 5. Style
- 使用 FastAPI + JWT
- 密码哈希用 bcrypt

## 6. Testing
- Integration test: 用 TestClient 真调 POST /api/login，验证 200 + token 非空
- Integration test: 错误密码验证 401
- 禁止用 mock 替代真实 DB/业务逻辑

complexity: simple
