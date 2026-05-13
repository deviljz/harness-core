"""
review-data 命令输出 JSON 格式验证。

覆盖：
1. 输出能被 json.loads 解析（无 CRLF / 编码问题）
2. diff_content 中的 newline / backslash / quote 都正确转义
3. 输出为纯 ASCII（非 ASCII 均转义），在 GBK/cp936 等 locale 下也能解析
4. 输出不含 CRLF
5. 所有必要字段存在
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _setup_git_repo(tmp_path: Path) -> None:
    """在 tmp_path 建立隔离的 git repo + harness config，确保 find_config 不会向上逃逸到真实项目。"""
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@test.com")
    git("config", "user.name", "test")

    # .harness/config.yaml — find_config 找的就是这个，必须在 tmp_path 里创建
    # 这样 find_config(start=tmp_path) 会停在 tmp_path，不会走到真实项目目录
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir()
    (harness_dir / "config.yaml").write_text("llm:\n  provider: manual\n", encoding="utf-8")

    # 初始提交：文件内容包含会产生各种特殊字符的内容（确保 diff 有这些字符）
    (tmp_path / "app.py").write_text(
        'def greet(name: str) -> str:\n'
        '    return f"Hello, {name}!\\n"\n'
        '\n'
        '# 中文注释：用于测试 Unicode\n'
        'BACKSLASH_EXAMPLE = "a\\\\b"\n',  # 反斜杠：写入文件为 a\b
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-q", "-m", "init")

    # 工作区改动：diff 会包含 newline / backslash / quote / Unicode
    (tmp_path / "app.py").write_text(
        'def greet(name: str) -> str:\n'
        '    msg = f"\\u4f60\\u597d, {name}!\\n"  # Unicode: 你好\n'  # Unicode via escape
        '    return msg\n'
        '\n'
        'BACKSLASH_EXAMPLE = "a\\\\b\\\\c"\n'   # 反斜杠：a\b\c
        'QUOTE_EXAMPLE = \'"double" and single\'\n',  # 双引号
        encoding="utf-8",
    )


def _run_review_data(tmp_path: Path, extra_args: list[str] | None = None) -> bytes:
    """在 tmp_path 目录运行 harness review-data，返回原始 stdout bytes。"""
    _setup_git_repo(tmp_path)

    cmd = [sys.executable, "-m", "harness.cli", "review-data"]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        cwd=tmp_path,
        capture_output=True,
        # 不做文本解码 — 我们要原始 bytes 测试编码
    )
    assert result.returncode == 0, (
        f"review-data exited {result.returncode}:\n{result.stderr.decode('utf-8', errors='replace')}"
    )
    return result.stdout


class TestReviewDataJsonValidity:
    """核心：输出必须是合法 JSON，在任何平台都能解析。"""

    def test_json_loads_does_not_raise(self, tmp_path: Path):
        """json.loads 不应抛异常。"""
        raw = _run_review_data(tmp_path)
        # 不应抛 JSONDecodeError
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_no_crlf_in_output(self, tmp_path: Path):
        """输出不含 \\r\\n（Windows 文本模式 CRLF）。"""
        raw = _run_review_data(tmp_path)
        assert b"\r\n" not in raw, "输出含 CRLF，会导致管道解析失败"

    def test_output_is_pure_ascii(self, tmp_path: Path):
        """输出为纯 ASCII（非 ASCII 均已 \\uXXXX 转义），在 GBK/cp936 locale 下也能解析。"""
        raw = _run_review_data(tmp_path)
        assert all(b < 128 for b in raw), (
            "输出含非 ASCII 字节，在 GBK 等 locale 下 json.tool 会解析失败"
        )

    def test_required_fields_present(self, tmp_path: Path):
        """输出包含 spec_content / diff_content / diff_base / spec_path / template 字段。"""
        raw = _run_review_data(tmp_path)
        data = json.loads(raw)
        for field in ("spec_content", "diff_content", "diff_base", "spec_path", "template"):
            assert field in data, f"缺少字段：{field}"


class TestDiffContentEscaping:
    """diff_content 字段中的特殊字符必须正确转义，round-trip 还原后内容一致。"""

    def test_newlines_round_trip(self, tmp_path: Path):
        """diff_content 中的换行符经 json.loads 还原后仍是真正的 \\n。"""
        raw = _run_review_data(tmp_path)
        data = json.loads(raw)
        diff = data["diff_content"]
        assert "\n" in diff, "diff_content 中应有换行符"

    def test_backslash_round_trip(self, tmp_path: Path):
        """diff_content 中的反斜杠经 json.loads 还原后仍是真正的 \\\\。"""
        raw = _run_review_data(tmp_path)
        data = json.loads(raw)
        diff = data["diff_content"]
        assert "\\" in diff, "diff_content 中应有反斜杠"

    def test_double_quotes_round_trip(self, tmp_path: Path):
        """diff_content 中的双引号经 json.loads 还原后仍是真正的 \"。"""
        raw = _run_review_data(tmp_path)
        data = json.loads(raw)
        diff = data["diff_content"]
        assert '"' in diff, "diff_content 中应有双引号"

    def test_unicode_content_round_trip(self, tmp_path: Path):
        """diff_content 中出现 Unicode 字符时，json.loads 能正确还原（不管是直接 UTF-8 还是 \\uXXXX）。"""
        raw = _run_review_data(tmp_path)
        data = json.loads(raw)
        diff = data["diff_content"]
        # 我们写入了 你好（你好），diff 里应包含这些字符或其 \uXXXX 转义
        assert "你好" in diff or "\\u4f60" in diff, (
            "Unicode 内容应存在于 diff_content（直接字符或转义形式）"
        )

    def test_spec_content_unicode_round_trip(self, tmp_path: Path):
        """spec_content 中的 Unicode 经 json.loads 还原后内容正确。"""
        # 先建 git repo（spec 文件必须在 tmp_path 目录下）
        _setup_git_repo(tmp_path)
        spec = tmp_path / "spec.md"
        spec.write_text("# 规格说明\n内容：用户「登录」流程\n", encoding="utf-8")
        cmd = [sys.executable, "-m", "harness.cli", "review-data", "--spec", str(spec)]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True)
        assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        data = json.loads(result.stdout)
        # 规格说明 = 规格说明
        assert "规格说明" in data["spec_content"]
