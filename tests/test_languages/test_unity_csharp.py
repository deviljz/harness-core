"""Unity C# 语言模块测试（mock subprocess，不真启 Unity.exe）"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from harness.languages import get_language_module
from harness.languages.unity_csharp import UnityCSharpModule
from harness.languages.unity_csharp.assertion_ast import check_test_file
from harness.languages.unity_csharp.finder import find_related_test_files, is_test_file
from harness.languages.unity_csharp.runner import (
    UnityEditorLockedError,
    parse_nunit3_xml,
    run_unity_tests,
)


# ════════════════════════════════════════════════════════════════════
# 注册
# ════════════════════════════════════════════════════════════════════


def test_unity_csharp_registered():
    assert isinstance(get_language_module("unity_csharp"), UnityCSharpModule)


# ════════════════════════════════════════════════════════════════════
# is_test_file
# ════════════════════════════════════════════════════════════════════


class TestIsTestFile:
    def test_ends_with_tests(self):
        assert is_test_file("Assets/Tests/FooTests.cs")

    def test_ends_with_test_singular(self):
        assert is_test_file("Tests/FooTest.cs")

    def test_underscore_test(self):
        assert is_test_file("Tests/Foo_Test.cs")

    def test_regular_runtime(self):
        assert not is_test_file("Assets/Scripts/Foo.cs")

    def test_not_cs(self):
        assert not is_test_file("Assets/Tests/FooTests.js")


# ════════════════════════════════════════════════════════════════════
# Finder
# ════════════════════════════════════════════════════════════════════


class TestFinder:
    def test_changed_file_itself_is_test(self, tmp_path):
        (tmp_path / "Assets" / "Tests").mkdir(parents=True)
        (tmp_path / "Assets" / "Tests" / "FooTests.cs").touch()
        found = find_related_test_files("Assets/Tests/FooTests.cs", {}, tmp_path)
        assert found == ["Assets/Tests/FooTests.cs"]

    def test_find_by_module_name_assets(self, tmp_path):
        (tmp_path / "Assets" / "Scripts").mkdir(parents=True)
        (tmp_path / "Assets" / "Scripts" / "Foo.cs").touch()
        (tmp_path / "Assets" / "Tests").mkdir()
        (tmp_path / "Assets" / "Tests" / "FooTests.cs").touch()
        found = find_related_test_files(
            "Assets/Scripts/Foo.cs",
            {"test_paths": ["Assets/Tests"]},
            tmp_path,
        )
        assert "Assets/Tests/FooTests.cs" in found

    def test_find_by_module_name_package_glob(self, tmp_path):
        # Packages/com.foo/Runtime/Bar.cs → Packages/com.foo/Tests/BarTests.cs
        pkg = tmp_path / "Packages" / "com.foo"
        (pkg / "Runtime").mkdir(parents=True)
        (pkg / "Runtime" / "Bar.cs").touch()
        (pkg / "Tests" / "Editor").mkdir(parents=True)
        (pkg / "Tests" / "Editor" / "BarTests.cs").touch()
        found = find_related_test_files(
            "Packages/com.foo/Runtime/Bar.cs",
            {"test_paths": ["Packages/*/Tests"]},
            tmp_path,
        )
        assert "Packages/com.foo/Tests/Editor/BarTests.cs" in found

    def test_no_test_found(self, tmp_path):
        (tmp_path / "Assets" / "Scripts").mkdir(parents=True)
        (tmp_path / "Assets" / "Scripts" / "Lonely.cs").touch()
        found = find_related_test_files("Assets/Scripts/Lonely.cs", {}, tmp_path)
        assert found == []

    def test_non_cs_ignored(self, tmp_path):
        # 改 .png / .prefab 这种二进制 → 找不到测试，返回 []
        found = find_related_test_files("Assets/Art/foo.prefab", {}, tmp_path)
        assert found == []

    def test_reverse_grep_class_decl(self, tmp_path):
        # 命名约定外：测试文件叫 SmokeBundle.cs 但里面 class FooTests 测 Foo
        (tmp_path / "Assets" / "Scripts").mkdir(parents=True)
        (tmp_path / "Assets" / "Scripts" / "Foo.cs").touch()
        (tmp_path / "Assets" / "Tests").mkdir()
        (tmp_path / "Assets" / "Tests" / "SmokeBundle.cs").write_text(
            "using NUnit.Framework;\npublic class FooTests {}\n",
            encoding="utf-8",
        )
        found = find_related_test_files(
            "Assets/Scripts/Foo.cs",
            {"test_paths": ["Assets/Tests"]},
            tmp_path,
        )
        assert "Assets/Tests/SmokeBundle.cs" in found


# ════════════════════════════════════════════════════════════════════
# assertion_ast 占位（C# AST 当前不实现）
# ════════════════════════════════════════════════════════════════════


class TestAssertionAST:
    def test_returns_empty(self, tmp_path):
        f = tmp_path / "FooTests.cs"
        f.write_text("public class FooTests {}\n", encoding="utf-8")
        assert check_test_file(f) == []


# ════════════════════════════════════════════════════════════════════
# Runner: pre-flight Editor 锁
# ════════════════════════════════════════════════════════════════════


class TestEditorLockedPreflight:
    def test_locked_raises(self, tmp_path, monkeypatch):
        # mock _is_unity_editor_holding 返回 (True, "12345")
        import harness.languages.unity_csharp.runner as runner_mod
        monkeypatch.setattr(
            runner_mod, "_is_unity_editor_holding",
            lambda p: (True, "12345"),
        )
        with pytest.raises(UnityEditorLockedError) as ei:
            run_unity_tests([], {"unity_exe": "fake"}, tmp_path)
        assert "12345" in str(ei.value)
        assert "exit 21" in str(ei.value)

    def test_unlocked_does_not_raise(self, tmp_path, monkeypatch):
        import harness.languages.unity_csharp.runner as runner_mod
        monkeypatch.setattr(
            runner_mod, "_is_unity_editor_holding",
            lambda p: (False, None),
        )
        # mock subprocess.run 让 batchmode 假装成功（不真启 Unity）
        def fake_run(cmd, **kw):
            # 模拟 Unity 写 results XML
            xml_path = Path(cmd[cmd.index("-testResults") + 1])
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            xml_path.write_text(
                """<?xml version="1.0"?>
<test-run id="2" total="1" passed="1" failed="0" skipped="0" inconclusive="0">
  <test-suite type="Assembly" name="EditModeTests" result="Passed">
    <test-case name="Foo" fullname="Ns.FooTests.Foo" result="Passed" duration="0.001"/>
  </test-suite>
</test-run>""",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        monkeypatch.setattr(subprocess, "run", fake_run)
        raw = run_unity_tests([], {"unity_exe": "fake-unity.exe"}, tmp_path)
        assert raw.exit_code == 0
        assert "__HARNESS_UNITY_RESULTS_XML__" in raw.stdout


# ════════════════════════════════════════════════════════════════════
# Runner: parse NUnit3 XML
# ════════════════════════════════════════════════════════════════════


class TestParseNunit3:
    def _make_raw(self, xml_path: Path, stdout_extra: str = "", exit_code: int = 0):
        from harness.languages.base import TestRunResult
        return TestRunResult(
            cmd="fake",
            cwd=".",
            exit_code=exit_code,
            stdout=stdout_extra + f"\n__HARNESS_UNITY_RESULTS_XML__={xml_path}\n",
            stderr="",
            duration_ms=100,
        )

    def test_all_pass(self, tmp_path):
        xml = tmp_path / "r.xml"
        xml.write_text(textwrap.dedent("""
            <?xml version="1.0"?>
            <test-run id="2" total="2" passed="2" failed="0" skipped="0" inconclusive="0">
              <test-suite type="Assembly" name="EditModeTests" result="Passed">
                <test-case name="One" fullname="Ns.FooTests.One" result="Passed" duration="0.001"/>
                <test-case name="Two" fullname="Ns.FooTests.Two" result="Passed" duration="0.002"/>
              </test-suite>
            </test-run>
        """).strip(), encoding="utf-8")
        result = parse_nunit3_xml(self._make_raw(xml))
        assert result.passed == 2
        assert result.failed == 0
        assert result.all_green

    def test_one_fail_with_stack(self, tmp_path):
        xml = tmp_path / "r.xml"
        xml.write_text(textwrap.dedent("""
            <?xml version="1.0"?>
            <test-run id="2" total="2" passed="1" failed="1" skipped="0" inconclusive="0">
              <test-suite type="Assembly" name="EditModeTests" result="Failed">
                <test-case name="Pass" fullname="Ns.FooTests.Pass" result="Passed" duration="0.001"/>
                <test-case name="Fail" fullname="Ns.FooTests.Fail" result="Failed" duration="0.002">
                  <failure>
                    <message>Expected 1 but was 2</message>
                    <stack-trace>at Ns.FooTests.Fail () [0x00000] in D:/proj/Assets/Tests/FooTests.cs:42</stack-trace>
                  </failure>
                </test-case>
              </test-suite>
            </test-run>
        """).strip(), encoding="utf-8")
        result = parse_nunit3_xml(self._make_raw(xml, exit_code=2))
        assert result.passed == 1
        assert result.failed == 1
        assert len(result.failures) == 1
        f = result.failures[0]
        assert f["test"] == "Ns.FooTests.Fail"
        assert "Expected 1 but was 2" in f["message"]
        # file:line 从 stack 提取
        assert f["file"].endswith("FooTests.cs")
        assert f["line"] == 42

    def test_xml_missing_fallback(self, tmp_path):
        # xml 路径在 stdout 但文件不存在 → fallback by exit_code
        xml = tmp_path / "not_exists.xml"
        result = parse_nunit3_xml(self._make_raw(xml, exit_code=21))
        # exit 21 = license/locked，应当 failed=1 + fallback message 含 hint
        assert result.failed == 1
        assert "21" in result.failures[0]["message"]
        # exit_code hint 含 "license" or "locked"
        assert "license" in result.failures[0]["message"].lower() or "locked" in result.failures[0]["message"].lower()

    def test_empty_test_list_passes(self, tmp_path):
        # NUnit3 testcasecount=0 仍 valid
        xml = tmp_path / "r.xml"
        xml.write_text(textwrap.dedent("""
            <?xml version="1.0"?>
            <test-run id="2" total="0" passed="0" failed="0" skipped="0" inconclusive="0">
              <test-suite type="Assembly" name="EditModeTests" result="Passed"/>
            </test-run>
        """).strip(), encoding="utf-8")
        result = parse_nunit3_xml(self._make_raw(xml, exit_code=0))
        assert result.passed == 0
        assert result.failed == 0
        # all_green 要求 passed > 0；empty 视为 "not green"
        assert not result.all_green


# ════════════════════════════════════════════════════════════════════
# Module dispatch
# ════════════════════════════════════════════════════════════════════


class TestModuleDispatch:
    def test_module_methods_route(self, tmp_path):
        mod = UnityCSharpModule()
        assert mod.name == "unity_csharp"
        # deep_check 当前空实现
        assert mod.deep_check("Tests/FooTests.cs", tmp_path) == []
