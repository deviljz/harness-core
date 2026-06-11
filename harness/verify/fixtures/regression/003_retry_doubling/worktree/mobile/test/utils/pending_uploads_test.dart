// （fixture 精简片段：只覆盖 PendingUploads 单元行为，未覆盖 _retryFailed→_uploadPaths 编排）

import 'package:flutter_test/flutter_test.dart';
import 'package:miao_study/utils/pending_uploads.dart';

void main() {
  test('addPaths 立即出现待上传项', () {
    final p = PendingUploads();
    p.addPaths('math', ['/a.jpg']);
    expect(p.forKey('math').single.localPath, '/a.jpg');
  });

  test('markAllFailed + resetFailed 清红', () {
    final p = PendingUploads();
    p.addPaths('math', ['/a.jpg']);
    p.markAllFailed('math');
    expect(p.failedPaths('math'), ['/a.jpg']);
    p.resetFailed('math');
    expect(p.failedPaths('math'), isEmpty);
  });

  test('clearSucceeded 移除未失败项', () {
    final p = PendingUploads();
    p.addPaths('math', ['/a.jpg']);
    p.clearSucceeded('math');
    expect(p.hasAny('math'), isFalse);
  });
  // 没有测试覆盖：失败 → _retryFailed → 再失败 → 再重试，断言列表数量不累积
}
