# Spec: 选图打卡乐观渲染 + 失败重试

## 1. Objective
打卡选图后立即显示本地缩略图与上传进度；上传失败时缩略图标红并可点击重试，
重试成功后由服务器图接管。失败重试不得产生重复缩略图。

## 2. User Flow
1. 用户在打卡卡片点「+」选图
2. 选完图：本地缩略图立即出现，叠加上传进度
3. 上传失败：该缩略图标红，角上显示重试图标
4. 用户点红色缩略图 → 重新上传该任务所有失败的图
5. 重试成功：红色缩略图变回正常（服务器图接管）
6. **不变量：无论重试多少次，同一张图在列表中始终只有一份**

## 3. Commands
- POST /api/tasks/submit — 首次打卡上传
- POST /api/tasks/{id}/add-media — 补图上传

## 4. Structure
- mobile/lib/utils/pending_uploads.dart — PendingUploads 乐观上传态状态机
- mobile/lib/screens/main_tab_screen.dart — _handleAddMedia / _uploadPaths / _retryFailed

## 5. Style
- 遵循现有 Flutter Material 风格

## 6. Testing
- 单元：PendingUploads 各方法（addPaths / setProgress / markFailed / resetFailed / clearSucceeded）
- 编排：失败 → 重试 → 再失败 → 再重试，断言同一张图始终只有 1 份（连续 N 轮不累积）

## 7. Boundaries
- 不改后端上传协议

## 8. Data Migration
N/A

complexity: complex
