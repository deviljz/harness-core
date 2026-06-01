# Spec: Health 端点

## 1. Objective
后端提供 /api/health 端点，返回 {"status": "ok"}，并有集成测试验证。

## 2. User Flow
不适用（纯后端健康检查端点）

## 3. Commands
- GET /api/health → {"status": "ok"}

## 4. Structure
- backend/main.py — FastAPI app with /api/health route
- tests/test_health.py — pytest integration test

## 5. Style
- 使用 FastAPI
- 测试用 TestClient

## 6. Testing
- Integration test: 用 TestClient 调 GET /api/health，验证 status=200 且 body.status=="ok"

complexity: simple
