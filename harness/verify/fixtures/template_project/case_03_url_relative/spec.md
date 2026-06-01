# Spec: 图片资源加载

## 1. Objective
后端 /api/items 返回每个 item 的图片 URL，客户端直接用该 URL 加载图片。
URL 必须是绝对路径（https://...），不能是相对路径。

## 2. User Flow
1. App 调用 GET /api/items，获取 items 列表
2. 每个 item 包含 image_url（绝对 URL）
3. Flutter Image.network(item.image_url) 加载图片

## 3. Commands
- GET /api/items → [{ id, name, image_url: "https://cdn.example.com/..." }]

## 4. Structure
- backend/main.py — /api/items 返回带绝对 image_url 的列表
- mobile/lib/services/item_service.dart — 调用 /api/items

## 5. Style
- image_url 必须含完整 scheme（https://）
- 禁止返回相对路径如 /images/foo.png

## 6. Testing
- Unit test: 验证 image_url 以 "https://" 开头

complexity: simple
