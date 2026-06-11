// （fixture 精简片段：进度遮罩 + 上传编排，缺少"处理中"中间态）

  /// 本地待上传缩略图：进度遮罩直接显示百分比。
  Widget _pendingThumb(BuildContext ctx, String taskKey, int? taskId, PendingMedia m) {
    return Stack(children: [
      Image.file(File(m.localPath), width: 56, height: 56, fit: BoxFit.cover),
      if (m.failed)
        const Icon(Icons.refresh)
      else
        // 上传中：直接显示百分比。进度到 100% 后这里就一直显示「100%」，
        // 直到 _refresh 完成才消失（服务器响应+刷新的空窗里停在 100%）。
        Center(child: Text('${(m.progress * 100).round()}%')),
    ]);
  }

  Future<void> _uploadPaths(
      BuildContext ctx, String taskKey, int? id, List<String> paths) async {
    setState(() => _pending.addPaths(taskKey, paths));
    await svc.submitTask(userId, taskKey, mediaPaths: paths, onProgress: (p) {
      if (mounted) setState(() => _pending.setKeyProgress(taskKey, p));
    });
    // 字节发完(p=1.0)到这里还要 await _refresh()，期间缩略图停在 100%，无"处理中"提示
    if (ctx.mounted) await _refresh();
    if (mounted) setState(() => _pending.clearSucceeded(taskKey));
  }

  // 「+」按钮：busy 期间渲染为转圈 loading（排在缩略图右侧，易被误读为"另一张图在传"）
  Widget _addButton(bool busy, VoidCallback? onTap) => GestureDetector(
        onTap: busy ? null : onTap,
        child: busy ? const SizedBox(width: 20, height: 20, child: MiaoLoading())
                    : const Icon(Icons.add_photo_alternate_outlined),
      );
