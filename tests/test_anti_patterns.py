"""anti_patterns 检查测试"""
from __future__ import annotations

import textwrap
from pathlib import Path

from harness.config import AntiPatternRule, HarnessConfig
from harness.validate.anti_patterns import run_anti_patterns, scan_file


def _make_config(**anti_patterns) -> HarnessConfig:
    """快速造一个含 anti_patterns 段的 config"""
    raw = {"project": "test", "anti_patterns": anti_patterns}
    return HarnessConfig(**raw)


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return p


# ════════════════════════════════════════════════════════════════════
# scan_file
# ════════════════════════════════════════════════════════════════════


def test_scan_file_catches_self_recursive_getter(tmp_path):
    f = _write(
        tmp_path,
        "main.dart",
        """
        class A {
          int get userId => userId;
        }
        """,
    )
    rule = AntiPatternRule(
        name="self_recursive_getter",
        pattern=r"^\s*\w+(\?|<[^>]+>)?\s+get\s+(\w+)\s*=>\s*\2\s*;",
        msg="自递归 getter 必爆栈",
        severity="error",
    )
    findings = scan_file(f, [rule], tmp_path)
    assert len(findings) == 1
    assert findings[0].rule == "self_recursive_getter"
    assert findings[0].severity == "error"
    assert findings[0].line == 2


def test_scan_file_no_match(tmp_path):
    f = _write(tmp_path, "ok.dart", "int get userId => widget.userId;")
    rule = AntiPatternRule(
        name="self_recursive_getter",
        pattern=r"^\s*\w+\s+get\s+(\w+)\s*=>\s*\1\s*;",
        severity="error",
    )
    assert scan_file(f, [rule], tmp_path) == []


def test_scan_file_bad_regex_skipped(tmp_path, caplog):
    f = _write(tmp_path, "x.dart", "anything\n")
    bad = AntiPatternRule(name="bad", pattern=r"[unclosed", severity="error")
    good = AntiPatternRule(name="good", pattern=r"anything", severity="warn")
    findings = scan_file(f, [bad, good], tmp_path)
    # bad 跳过，good 命中
    assert len(findings) == 1
    assert findings[0].rule == "good"


def test_scan_binary_file_silent(tmp_path):
    f = tmp_path / "img.bin"
    f.write_bytes(b"\x00\x01\x02\x03")
    rule = AntiPatternRule(name="x", pattern=r"x", severity="warn")
    # 不应炸
    assert scan_file(f, [rule], tmp_path) == []


# ════════════════════════════════════════════════════════════════════
# run_anti_patterns
# ════════════════════════════════════════════════════════════════════


def test_run_empty_config_skip(tmp_path):
    cfg = HarnessConfig(project="x")
    r = run_anti_patterns(cfg, tmp_path, None)
    assert r.status == "skip"


def test_run_on_edit_dart_match(tmp_path):
    f = _write(tmp_path, "src/foo.dart", "int get x => x;")
    cfg = _make_config(
        dart=[{"name": "rec", "pattern": r"^\s*\w+\s+get\s+(\w+)\s*=>\s*\1\s*;", "severity": "error", "msg": "rec"}]
    )
    r = run_anti_patterns(cfg, tmp_path, "src/foo.dart")
    assert r.status == "fail"
    assert r.details["total"] == 1
    assert r.details["findings"][0]["file"] == "src/foo.dart"


def test_run_on_edit_no_rules_for_lang(tmp_path):
    f = _write(tmp_path, "x.md", "# heading\n")
    cfg = _make_config(dart=[{"name": "rec", "pattern": r"foo", "severity": "error"}])
    r = run_anti_patterns(cfg, tmp_path, "x.md")
    # .md 不在 EXT_TO_LANG → 0 finding
    assert r.status == "pass"


def test_run_cross_language(tmp_path):
    _write(tmp_path, "a.dart", "int get a => a;")
    _write(
        tmp_path,
        "b.py",
        """
        try:
            x = 1
        except:
            pass
        """,
    )
    cfg = _make_config(
        dart=[{"name": "rec", "pattern": r"^\s*\w+\s+get\s+(\w+)\s*=>\s*\1\s*;", "severity": "error"}],
        python=[{"name": "bare", "pattern": r"^\s*except\s*:\s*$", "severity": "error"}],
    )
    # 全量
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    r = run_anti_patterns(cfg, tmp_path, None)
    assert r.status == "fail"
    assert r.details["total"] == 2


def test_run_warn_severity(tmp_path):
    _write(tmp_path, "x.py", "x = 1")
    cfg = _make_config(python=[{"name": "anything", "pattern": r"x = 1", "severity": "warn"}])
    r = run_anti_patterns(cfg, tmp_path, "x.py")
    assert r.status == "warn"


def test_run_all_section_applies_to_any_ext(tmp_path):
    _write(tmp_path, "x.py", "AIzaSyDummy_TestKey_NotARealKeyJustForFakeMatch12")
    cfg = HarnessConfig(
        project="x",
        anti_patterns={
            "all": [AntiPatternRule(name="key_leak", pattern=r"AIza[0-9A-Za-z_-]{35}", severity="error")]
        },
    )
    r = run_anti_patterns(cfg, tmp_path, "x.py")
    assert r.status == "fail"
