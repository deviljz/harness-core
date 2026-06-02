"""Dart / Flutter 语言模块（基础版，无 AST 深检 v2 再加）"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from ..base import LanguageModule, TestResult, TestRunResult, run_command


def _resolve_flutter(target_config: dict) -> str:
    """选用哪个 flutter 可执行文件跑 test。

    默认 "flutter"（走 PATH，Windows 上由 shell 解析 .bat）；
    target_config["flutter_bin"] 可显式覆盖到特定 SDK / 非 PATH 安装。
    与 python 的 _resolve_python、unity 的 _resolve_unity_exe 范式一致。
    """
    explicit = target_config.get("flutter_bin")
    if explicit:
        return str(explicit)
    return "flutter"


class DartModule(LanguageModule):
    name = "dart"

    def find_related_tests(
        self,
        changed_file: str,
        target_config: dict,
        project_root: Path,
    ) -> list[str]:
        """Flutter 约定：lib/pages/home.dart → test/pages/home_test.dart"""
        changed = Path(changed_file)
        rel = changed if not changed.is_absolute() else changed.relative_to(project_root)
        rel_str = str(rel).replace("\\", "/")

        # 已经是 test 文件
        if rel_str.endswith("_test.dart"):
            return [rel_str]

        if not rel_str.endswith(".dart"):
            return []

        # lib/foo/bar.dart → test/foo/bar_test.dart
        # 或 mobile/lib/foo/bar.dart → mobile/test/foo/bar_test.dart
        test_paths = target_config.get("test_paths", ["test"])

        module_name = rel.stem  # "home"
        target_name = f"{module_name}_test.dart"

        found: list[str] = []
        for tp in test_paths:
            tp_abs = project_root / tp
            if not tp_abs.exists():
                continue
            for path in tp_abs.rglob(target_name):
                found.append(str(path.relative_to(project_root)).replace("\\", "/"))
        return found

    def run_tests(
        self,
        test_files: list[str],
        target_config: dict,
        project_root: Path,
    ) -> TestRunResult:
        """跑 flutter test。cwd 默认 target.root 所在位置"""
        # 如果 root = mobile/，flutter test 要在 mobile/ 目录下跑
        root_rel = target_config.get("root", ".")
        cwd = project_root / root_rel if not Path(root_rel).is_absolute() else Path(root_rel)

        cmd_parts = [_resolve_flutter(target_config), "test", "--reporter=expanded"]
        if test_files:
            # flutter test 需要相对 cwd 的路径；转一下
            for tf in test_files:
                abs_path = project_root / tf
                try:
                    rel_to_cwd = abs_path.relative_to(cwd)
                    cmd_parts.append(str(rel_to_cwd).replace("\\", "/"))
                except ValueError:
                    cmd_parts.append(tf)

        # Windows 下 flutter 是 .bat 脚本，subprocess(shell=False) 不会按 PATHEXT 解析
        # → 用 shell 字符串走 cmd.exe，可正确解析到 flutter.bat
        if sys.platform == "win32":
            cmd: str | list[str] = " ".join(cmd_parts)
        else:
            cmd = cmd_parts
        return run_command(cmd, cwd, timeout=target_config.get("timeout", 600))

    def parse_results(self, raw: TestRunResult) -> TestResult:
        """flutter test 输出解析。

        典型行:
          00:01 +5 -2: ...            # 进度
          00:01 +5 -2: Some test [E]  # 失败的
          All tests passed!
          Some tests failed.
        """
        out = raw.stdout + "\n" + raw.stderr
        # expanded reporter 每行格式：00:01 +N [-M] [~K]: description
        # 取最后一次出现的计数（累计值），避免 "+0: loading..." 早期行干扰
        passed_matches = re.findall(r"\+(\d+)", out)
        # -N 必须跟在 +N 之后（space 分隔），避免匹配时间戳里的负号
        failed_matches = re.findall(r"(?<=\s)-(\d+)", out)
        skipped_matches = re.findall(r"~(\d+)", out)

        passed = int(passed_matches[-1]) if passed_matches else 0
        failed = int(failed_matches[-1]) if failed_matches else 0
        skipped = int(skipped_matches[-1]) if skipped_matches else 0

        # 非 0 退出但没统计到 → 挂 1 个错误
        errors = 0
        if raw.exit_code != 0 and passed == 0 and failed == 0:
            errors = 1

        failures: list[dict] = []
        # 解析失败块："FAILED: <test_name>"
        for m in re.finditer(r"(?:\[E\]|FAILED)\s+(.+)", out):
            failures.append(
                {
                    "file": "(flutter)",
                    "test": m.group(1).strip()[:200],
                    "message": "flutter test failed",
                    "traceback": "",
                }
            )

        return TestResult(
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            failures=failures,
            raw_output=out[-4000:],
        )
