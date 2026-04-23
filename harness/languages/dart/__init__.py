"""Dart / Flutter 语言模块（基础版，无 AST 深检 v2 再加）"""
from __future__ import annotations

import re
from pathlib import Path

from ..base import LanguageModule, TestResult, TestRunResult, run_command


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

        cmd_parts = ["flutter", "test", "--reporter=expanded"]
        if test_files:
            # flutter test 需要相对 cwd 的路径；转一下
            for tf in test_files:
                abs_path = project_root / tf
                try:
                    rel_to_cwd = abs_path.relative_to(cwd)
                    cmd_parts.append(str(rel_to_cwd).replace("\\", "/"))
                except ValueError:
                    cmd_parts.append(tf)

        return run_command(cmd_parts, cwd, timeout=target_config.get("timeout", 600))

    def parse_results(self, raw: TestRunResult) -> TestResult:
        """flutter test 输出解析。

        典型行:
          00:01 +5 -2: ...            # 进度
          00:01 +5 -2: Some test [E]  # 失败的
          All tests passed!
          Some tests failed.
        """
        out = raw.stdout + "\n" + raw.stderr
        # 末尾出现 +N 或 -N
        passed_match = re.search(r"\+(\d+)", out)
        failed_match = re.search(r"-(\d+)\s*:", out)
        skipped_match = re.search(r"~(\d+)", out)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        skipped = int(skipped_match.group(1)) if skipped_match else 0

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
