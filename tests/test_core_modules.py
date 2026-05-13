"""core_modules_coverage 检查测试"""
from __future__ import annotations

from pathlib import Path

from harness.config import CoreModuleEntry, HarnessConfig
from harness.validate.core_modules import run_core_modules_coverage


def _make(core_modules_coverage: list[dict]) -> HarnessConfig:
    return HarnessConfig(project="x", core_modules_coverage=core_modules_coverage)


def _touch(tmp_path: Path, rel: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("// stub\n", encoding="utf-8")
    return p


def test_empty_config_skip(tmp_path):
    r = run_core_modules_coverage(HarnessConfig(project="x"), tmp_path, None)
    assert r.status == "skip"


def test_test_exists_pass(tmp_path):
    _touch(tmp_path, "lib/foo.dart")
    _touch(tmp_path, "test/foo_test.dart")
    cfg = _make([{"path": "lib/foo.dart", "must_have_test": "test/foo_test.dart"}])
    r = run_core_modules_coverage(cfg, tmp_path, None)
    assert r.status == "pass"


def test_test_missing_warn(tmp_path):
    _touch(tmp_path, "lib/foo.dart")
    cfg = _make([{"path": "lib/foo.dart", "must_have_test": "test/foo_test.dart"}])
    r = run_core_modules_coverage(cfg, tmp_path, None)
    assert r.status == "warn"
    assert r.details["missing"][0]["path"] == "lib/foo.dart"


def test_on_edit_path_match(tmp_path):
    _touch(tmp_path, "lib/foo.dart")
    cfg = _make([{"path": "lib/foo.dart", "must_have_test": "test/foo_test.dart"}])
    r = run_core_modules_coverage(cfg, tmp_path, "lib/foo.dart")
    assert r.status == "warn"


def test_on_edit_path_not_in_list_skip(tmp_path):
    cfg = _make([{"path": "lib/foo.dart", "must_have_test": "test/foo_test.dart"}])
    r = run_core_modules_coverage(cfg, tmp_path, "lib/bar.dart")
    assert r.status == "skip"
