"""回归守卫：verify fixtures 必须在 harness 包内，否则 pip wheel 不打包。

Hermes 反馈：pip 装完 `harness verify run` 报 "No fixtures found"——根因是 fixtures 在
repo/tests/fixtures（被 pyproject exclude=["tests*"]），没进 wheel。搬进包内后此测试守住。
"""

from pathlib import Path

import harness
from harness.verify.cli import _FIXTURES_ROOT


def test_verify_fixtures_exist():
    assert _FIXTURES_ROOT.exists(), f"fixtures root 缺失: {_FIXTURES_ROOT}"
    assert (_FIXTURES_ROOT / "regression").exists()
    assert (_FIXTURES_ROOT / "template_project").exists()


def test_verify_fixtures_inside_harness_package():
    """fixtures 必须在 harness 包目录下，否则 wheel 装完找不到。"""
    pkg_root = Path(harness.__file__).resolve().parent
    assert pkg_root in _FIXTURES_ROOT.resolve().parents, (
        f"fixtures 在包外 ({_FIXTURES_ROOT}) → pip 装完会 'No fixtures found'"
    )
