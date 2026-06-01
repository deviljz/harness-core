# Spec: 设置页 X 按钮

## 1. Objective
用户可以在设置页点击 X 按钮关闭设置页，返回主界面。

## 2. User Flow
1. 用户进入设置页（SettingsPage）
2. 用户点击右上角 X 按钮（close_button）
3. 页面关闭，返回主界面

## 3. Commands
不适用（纯 UI 操作）

## 4. Structure
- mobile/lib/screens/settings_screen.dart — SettingsPage with close_button (X icon)

## 5. Style
- Material IconButton with Icons.close

## 6. Testing
- Widget test: 点击 X 按钮验证页面 pop

complexity: simple
