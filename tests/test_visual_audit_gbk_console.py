"""GBK 控制台下 visual-audit 输出 ✓ ✗ 不崩.

中文 Windows 控制台默认 GBK；harness/cli.py 顶部已做 win32 UTF-8 reconfigure，
但 visual_audit/cli.py 单独入口（python -m harness.skills.harness_visual_audit.cli）
漏了同样处理 → print_console_summary 打 ✓/✗ 时 UnicodeEncodeError。
RichMan 迁移时真实踩到（需 PYTHONUTF8=1 绕开）。
"""

import os
import subprocess
import sys

import pytest

_VISUAL_AUDIT_SNIPPET = (
    "from harness.skills.harness_visual_audit import cli\n"  # 入口 import 应触发编码兜底
    "from harness.skills.harness_visual_audit.runner import AuditResult\n"
    "from harness.skills.harness_visual_audit.assertions import AssertionResult\n"
    "from harness.skills.harness_visual_audit.report import print_console_summary\n"
    "r = AuditResult(target='t', results=[\n"
    "    AssertionResult('OK', True),\n"
    "    AssertionResult('BAD', False, actual='x', expected='y'),\n"
    "])\n"
    "print_console_summary(r)\n"
)

# baseline cli 同样打 ✓ ❌ →；import 入口模块应触发 reconfigure 兜底
_BASELINE_SNIPPET = (
    "from harness.skills.harness_baseline import cli\n"
    "print('\\u2713 \\u274c \\u2192')\n"
)


@pytest.mark.parametrize(
    "snippet", [_VISUAL_AUDIT_SNIPPET, _BASELINE_SNIPPET], ids=["visual_audit", "baseline"]
)
def test_cli_unicode_output_survives_gbk_stdout(snippet):
    env = {**os.environ, "PYTHONIOENCODING": "gbk", "PYTHONUTF8": "0"}
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"GBK 控制台下输出崩了:\n{proc.stderr.decode('utf-8', 'replace')}"
    )
