"""Python 语言模块测试"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from harness.languages import get_language_module
from harness.languages.python import PythonModule
from harness.languages.python.assertion_ast import check_test_file
from harness.languages.python.finder import find_related_test_files, is_test_file


# ════════════════════════════════════════════════════════════════════
# 注册 + finder
# ════════════════════════════════════════════════════════════════════


def test_python_registered():
    assert isinstance(get_language_module("python"), PythonModule)


class TestIsTestFile:
    def test_starts_with_test(self):
        assert is_test_file("tests/test_foo.py")

    def test_ends_with_test(self):
        assert is_test_file("tests/foo_test.py")

    def test_regular_module(self):
        assert not is_test_file("app/foo.py")

    def test_not_py(self):
        assert not is_test_file("tests/test_foo.js")


class TestFinder:
    def test_changed_file_itself_is_test(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").touch()
        found = find_related_test_files("tests/test_foo.py", {}, tmp_path)
        assert found == ["tests/test_foo.py"]

    def test_find_by_module_name(self, tmp_path):
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "prompt_builder.py").touch()
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_prompt_builder.py").touch()
        found = find_related_test_files("app/prompt_builder.py", {"test_paths": ["tests"]}, tmp_path)
        assert "tests/test_prompt_builder.py" in found

    def test_no_test_found(self, tmp_path):
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "lonely.py").touch()
        (tmp_path / "tests").mkdir()
        found = find_related_test_files("app/lonely.py", {}, tmp_path)
        assert found == []


# ════════════════════════════════════════════════════════════════════
# assertion_ast 深度检查
# ════════════════════════════════════════════════════════════════════


def _write(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(src).lstrip(), encoding="utf-8")
    return p


class TestAssertionAST:
    def test_legit_test_clean(self, tmp_path):
        f = _write(
            tmp_path,
            "test_ok.py",
            """
            def test_ok():
                x = 1 + 1
                assert x == 2
            """,
        )
        assert check_test_file(f) == []

    def test_assert_true_flagged(self, tmp_path):
        f = _write(
            tmp_path,
            "test_fake.py",
            """
            def test_fake():
                assert True
            """,
        )
        issues = check_test_file(f)
        assert any(i.rule == "forbid_tautology" for i in issues)

    def test_assert_1_eq_1_flagged(self, tmp_path):
        f = _write(
            tmp_path,
            "test_fake.py",
            """
            def test_fake():
                assert 1 == 1
            """,
        )
        issues = check_test_file(f)
        assert any(i.rule == "forbid_tautology" for i in issues)

    def test_assert_literal_int_flagged(self, tmp_path):
        f = _write(
            tmp_path,
            "test_fake.py",
            """
            def test_fake():
                assert 1
            """,
        )
        issues = check_test_file(f)
        assert any(i.rule == "forbid_tautology" for i in issues)

    def test_no_assertion_flagged(self, tmp_path):
        f = _write(
            tmp_path,
            "test_empty.py",
            """
            def test_empty():
                x = 1 + 1
            """,
        )
        issues = check_test_file(f)
        assert any(i.rule == "no_assertion" for i in issues)

    def test_pytest_raises_without_assert_ok(self, tmp_path):
        f = _write(
            tmp_path,
            "test_raises.py",
            """
            import pytest
            def test_raises():
                with pytest.raises(ValueError):
                    int("abc")
            """,
        )
        issues = check_test_file(f)
        assert [i for i in issues if i.rule == "no_assertion"] == []

    def test_single_assert_ok_not_flagged(self, tmp_path):
        # 确认去掉了 min_asserts_per_test，单 assert 不报
        f = _write(
            tmp_path,
            "test_single.py",
            """
            def test_single():
                result = some_func()  # noqa
                assert result == 42
            """,
        )
        issues = check_test_file(f)
        assert issues == []

    def test_non_test_function_ignored(self, tmp_path):
        # 非 test_ 开头的函数不管
        f = _write(
            tmp_path,
            "helpers.py",
            """
            def helper():
                pass
            """,
        )
        assert check_test_file(f) == []

    def test_syntax_error_reported(self, tmp_path):
        f = _write(
            tmp_path,
            "test_bad.py",
            """
            def test_bad(
            """,
        )
        issues = check_test_file(f)
        assert any(i.rule == "parse_error" for i in issues)


# ════════════════════════════════════════════════════════════════════
# runner 集成测试
# ════════════════════════════════════════════════════════════════════


class TestRunner:
    def test_pytest_pass(self, tmp_path):
        (tmp_path / "test_ok.py").write_text(
            textwrap.dedent(
                """
                def test_one():
                    assert 1 + 1 == 2

                def test_two():
                    assert "a" + "b" == "ab"
                """
            ).lstrip()
        )
        mod = PythonModule()
        raw = mod.run_tests(["test_ok.py"], {}, tmp_path)
        result = mod.parse_results(raw)
        assert result.passed == 2
        assert result.failed == 0
        assert result.all_green

    def test_pytest_fail_parsed(self, tmp_path):
        (tmp_path / "test_bad.py").write_text(
            textwrap.dedent(
                """
                def test_good():
                    assert 1 == 1

                def test_fail():
                    x = 5
                    assert x == 99
                """
            ).lstrip()
        )
        mod = PythonModule()
        raw = mod.run_tests(["test_bad.py"], {}, tmp_path)
        result = mod.parse_results(raw)
        assert result.passed >= 1
        assert result.failed >= 1
        assert len(result.failures) >= 1
        assert any("test_fail" in f["test"] for f in result.failures)

    def test_pytest_collection_error(self, tmp_path):
        (tmp_path / "test_syntax.py").write_text("def broken(:\n")
        mod = PythonModule()
        raw = mod.run_tests(["test_syntax.py"], {}, tmp_path)
        result = mod.parse_results(raw)
        # 退出码非 0，应当有 error 或 failed 登记
        assert result.errors + result.failed >= 1
