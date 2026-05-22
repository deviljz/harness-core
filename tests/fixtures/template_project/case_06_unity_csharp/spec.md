# Spec: 异步截图采集（Unity 工程）

## 1. Objective
在 Unity Player 端每 N 帧异步抓屏（不阻塞主线程），写到 sessionDir/screenshots/*.jpg。
要求：截图必须包含**完整屏幕画面**，不能只截左下角一小块。

## 2. User Flow
不适用（无 UI，纯录制工具）

## 3. Commands
- `Periscope.AsyncScreenshotCapture.StartCapturing(outDir, sessionStartMs)` — 启动每帧异步采集
- 内部：`ScreenCapture.CaptureScreenshotIntoRenderTexture(rt)` → `AsyncGPUReadback.Request(rt, ...)`

## 4. Structure
- Packages/com.ut.periscope/Runtime/AsyncScreenshotCapture.cs — 主类 + 反射 ScreenCapture API

## 5. Style
- 主线程 < 0.3ms / 帧（AsyncGPUReadback 异步）
- 不依赖编译期 ScreenCaptureModule（反射找方法）

## 6. Testing
- 真机录制后看 screenshots/*.jpg：必须是**整屏画面**，不是裁切的一小块
- 多种屏幕比例（横屏 + 竖屏）都正确

## 7. Boundaries
### 绝不做
- 不在主线程同步等 GPU readback

### 必须做
- RT 写入前若 RT 比 backbuffer 小，必须先用全屏 RT 接，再 Blit 缩放到小 RT（CaptureScreenshotIntoRenderTexture 在小 RT 上只裁切不缩放）

## 8. Data Migration
N/A
