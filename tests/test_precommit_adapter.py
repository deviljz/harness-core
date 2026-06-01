"""generic adapter: git pre-commit hook（跑 harness check 拦红提交）。

补 Hermes 反馈：无 Claude Code 的 auto-hook 时，纯手动 check 会疲劳/漏检；
git pre-commit 在提交前兜底跑 check，拦住不绿的提交。
"""

from pathlib import Path

from harness.adapters.generic import install_precommit_hook


def _make_git(tmp: Path) -> None:
    (tmp / ".git" / "hooks").mkdir(parents=True)


def test_non_git_returns_none(tmp_path):
    assert install_precommit_hook(tmp_path) is None


def test_installs_hook(tmp_path):
    _make_git(tmp_path)
    p = install_precommit_hook(tmp_path)
    assert p == tmp_path / ".git" / "hooks" / "pre-commit"
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "harness check" in body          # 真跑 check
    assert "harness-core" in body           # 幂等标记
    assert "command -v harness" in body     # 没装 harness 优雅降级


def test_idempotent_overwrites_not_appends(tmp_path):
    _make_git(tmp_path)
    body1 = install_precommit_hook(tmp_path).read_text(encoding="utf-8")
    body2 = install_precommit_hook(tmp_path).read_text(encoding="utf-8")
    assert body1 == body2  # 重复跑覆盖自己的 hook，内容不变（非追加）


def test_existing_non_harness_hook_not_clobbered(tmp_path):
    _make_git(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho custom-hook\n", encoding="utf-8")
    res = install_precommit_hook(tmp_path)
    assert res is None                                   # 不覆盖别人的 hook
    assert "custom-hook" in hook.read_text(encoding="utf-8")
