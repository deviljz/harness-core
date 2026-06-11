# Spec: 选图打卡上传进度可视化

## 1. Objective
打卡选图后立即显示本地缩略图与真实上传进度，让用户对上传状态有即时、准确的反馈。

## 2. User Flow
1. 用户点「+」选图
2. 本地缩略图立即出现，叠加上传进度（百分比）
3. 上传过程中用户能清楚区分「正在传」与「已传完正在处理」两个阶段
4. 传完：服务器图接管，可点「确认打卡」
5. 上传期间「+」按钮不得与缩略图进度产生视觉混淆

## 3. Commands
- POST /api/tasks/submit（onProgress 上报字节进度）

## 4. Structure
- mobile/lib/screens/main_tab_screen.dart — _pendingThumb 缩略图进度遮罩 / _uploadPaths
- mobile/lib/utils/pending_uploads.dart — PendingMedia 进度态

## 5. Style
- Flutter Material 风格

## 6. Testing
- 注入"慢依赖"fake service（onProgress 喂到 1.0 后 Future 故意延迟 resolve），
  断言：字节发完(100%)→服务器响应前，显示「处理中…」而非停在「100%」；
  且「+」按钮在上传期间不显示转圈 loading（避免被误读为另一张图在传）。
- 禁止仅用小文件/秒传验证（空窗会被压成 0ms，掩盖中间态缺失）。

## 7. Boundaries
- 不改上传协议

## 8. Data Migration
N/A

complexity: complex
