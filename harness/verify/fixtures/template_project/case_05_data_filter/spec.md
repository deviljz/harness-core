# Spec: Items 按 kind 过滤

## 1. Objective
GET /api/items?kind=X 只返回 kind='X' 的数据行，不返回其他 kind 的数据。

## 2. User Flow
不适用（纯后端 API 过滤）

## 3. Commands
- GET /api/items?kind=exercise → 只返回 kind='exercise' 的 items
- SQL: SELECT * FROM items WHERE kind = :kind

## 4. Structure
- backend/main.py — /api/items?kind= 查询参数，加 WHERE kind=:kind 过滤

## 5. Style
- 必须在 SQL 层过滤，不在 Python 层过滤

## 6. Testing
- 测试数据库含 5 行数据，kind 分别为 NULL/NULL/NULL/NULL/NULL
- Integration test: 查询 kind='exercise'，验证返回空列表（无匹配行）
- 数据源 trace: 必须确认测试数据包含 kind='exercise' 的行，否则测试无意义

complexity: simple
