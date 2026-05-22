#if PERISCOPE_ENABLED
using System;
using System.IO;
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;

namespace Periscope
{
    /// <summary>
    /// 异步截图采集（注：本实现故意有 bug — 用于 case_06 review fixture）
    ///
    /// BUG：直接把 backbuffer 抓到 256x... 的小 RT，CaptureScreenshotIntoRenderTexture
    /// 在 RT 比 backbuffer 小时只裁切左下角不缩放（spec §7 必须做 + boundary 已明示）。
    /// Review 应该指出此偏差。
    /// </summary>
    public class AsyncScreenshotCapture : MonoBehaviour
    {
        public int Width = 256;
        public int Height = 144;
        public int JpegQuality = 70;

        RenderTexture _rt;
        string _outDir;
        long _sessionStartMs;
        bool _running;

        static MethodInfo _captureMethod;

        void EnsureRT()
        {
            if (_rt != null) return;
            // 偏差点：RT 比 Screen 小，CaptureScreenshotIntoRenderTexture 只截左下角
            _rt = new RenderTexture(Width, Height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Default);
            _rt.Create();
        }

        public void StartCapturing(string outDir, long sessionStartMs)
        {
            _outDir = outDir;
            _sessionStartMs = sessionStartMs;
            _running = true;
            EnsureRT();
            ResolveCaptureMethod();
        }

        void LateUpdate()
        {
            if (!_running || _captureMethod == null) return;
            // 直接抓到小 RT — 偏差：spec §7 要求先抓全屏 RT 再 Blit 缩放
            _captureMethod.Invoke(null, new object[] { _rt });
            AsyncGPUReadback.Request(_rt, 0, req =>
            {
                if (req.hasError) return;
                var bytes = req.GetData<byte>().ToArray();
                var jpg = ImageConversion.EncodeArrayToJPG(
                    bytes, _rt.graphicsFormat, (uint)Width, (uint)Height, 0, JpegQuality);
                File.WriteAllBytes(Path.Combine(_outDir, $"{Time.frameCount:D8}.jpg"), jpg);
            });
        }

        static void ResolveCaptureMethod()
        {
            if (_captureMethod != null) return;
            try
            {
                var t = Type.GetType("UnityEngine.ScreenCapture, UnityEngine.ScreenCaptureModule");
                if (t != null)
                    _captureMethod = t.GetMethod("CaptureScreenshotIntoRenderTexture", new[] { typeof(RenderTexture) });
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Periscope] resolve failed: " + e.Message);
            }
        }
    }
}
#endif
