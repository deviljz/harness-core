// （fixture 精简片段：只验进度数值，未注入慢依赖断言"100%→处理中"中间态）

import 'package:flutter_test/flutter_test.dart';
import 'package:miao_study/utils/pending_uploads.dart';

void main() {
  test('setKeyProgress 更新进度', () {
    final p = PendingUploads();
    p.addPaths('math', ['/a.jpg']);
    p.setKeyProgress('math', 1.0);
    expect(p.forKey('math').single.progress, 1.0);
  });
  // 没有：注入"onProgress 到 1.0 后延迟 resolve"的 fake service，
  // 断言此刻 UI 显示「处理中…」而非「100%」、且「+」按钮不转圈。
}
