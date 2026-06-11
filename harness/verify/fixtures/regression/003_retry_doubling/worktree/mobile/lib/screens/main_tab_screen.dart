// （fixture 精简片段：只保留与失败重试编排相关的代码）

  final PendingUploads _pending = PendingUploads();

  /// 选图/重试共用的乐观上传。
  Future<void> _uploadPaths(
      BuildContext ctx, String taskKey, int? existingTaskId, List<String> paths) async {
    setState(() => _pending.addPaths(taskKey, paths)); // 缩略图即时出现
    if (existingTaskId == null) {
      try {
        await svc.submitTask(userId, taskKey, mediaPaths: paths, onProgress: (p) {
          if (mounted) setState(() => _pending.setKeyProgress(taskKey, p));
        });
        if (ctx.mounted) await _refresh();
        if (mounted) setState(() => _pending.clearSucceeded(taskKey));
      } catch (e) {
        if (mounted) setState(() => _pending.markAllFailed(taskKey));
      }
      return;
    }
    // ... add-media 逐文件路径略 ...
  }

  /// 重试该任务所有上传失败的本地图（点红色重试角标触发）。
  Future<void> _retryFailed(BuildContext ctx, String taskKey, int? existingTaskId) async {
    final paths = _pending.failedPaths(taskKey);
    if (paths.isEmpty) return;
    setState(() => _pending.resetFailed(taskKey)); // 清红、进度归零
    // 注意：_uploadPaths 开头还会再 addPaths(paths) 一次
    await _uploadPaths(ctx, taskKey, existingTaskId, paths);
  }
