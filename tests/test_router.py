"""router 测试：路径规范化、ignore 匹配、target 路由"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness.config import HarnessConfig, TargetConfig
from harness.router import (
    RouteResult,
    match_glob,
    normalize_path,
    relative_to_project,
    route_file,
)


# ════════════════════════════════════════════════════════════════════
# normalize_path
# ════════════════════════════════════════════════════════════════════


class TestNormalizePath:
    def test_windows_backslash_to_slash(self):
        assert normalize_path("app\\foo\\bar.py") == "app/foo/bar.py"

    def test_leading_dot_slash_stripped(self):
        assert normalize_path("./app/foo.py") == "app/foo.py"

    def test_already_posix(self):
        assert normalize_path("app/foo.py") == "app/foo.py"

    def test_mixed_separators(self):
        assert normalize_path("app/foo\\bar/baz.py") == "app/foo/bar/baz.py"


# ════════════════════════════════════════════════════════════════════
# match_glob
# ════════════════════════════════════════════════════════════════════


class TestMatchGlob:
    def test_exact_file(self):
        assert match_glob("app/foo.py", "app/foo.py")

    def test_single_star_in_filename(self):
        assert match_glob("app/foo.py", "app/*.py")
        assert not match_glob("app/sub/foo.py", "app/*.py")

    def test_double_star_recursive(self):
        assert match_glob("app/sub/foo.py", "app/**/foo.py")
        assert match_glob("app/foo.py", "app/**/foo.py")
        assert match_glob("build/a/b/c.js", "build/**")

    def test_node_modules_deep(self):
        assert match_glob("frontend/web/node_modules/react/index.js", "**/node_modules/**")

    def test_not_match(self):
        assert not match_glob("app/foo.py", "tests/*.py")

    def test_pycache(self):
        assert match_glob("app/__pycache__/foo.cpython.pyc", "**/__pycache__/**")


# ════════════════════════════════════════════════════════════════════
# relative_to_project
# ════════════════════════════════════════════════════════════════════


def test_relative_to_project_absolute(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "app").mkdir()
    (proj / "app" / "x.py").touch()
    assert relative_to_project(proj / "app" / "x.py", proj) == "app/x.py"


def test_relative_to_project_already_relative(tmp_path):
    proj = tmp_path / "myproj"
    assert relative_to_project("app/x.py", proj) == "app/x.py"


# ════════════════════════════════════════════════════════════════════
# route_file
# ════════════════════════════════════════════════════════════════════


def _make_config() -> HarnessConfig:
    return HarnessConfig(
        project="test",
        ignore_paths_global=[".git/**", "**/__pycache__/**", "**/*.log"],
        targets=[
            TargetConfig(
                name="backend",
                root="app/",
                language="python",
                ignore_paths=["app/migrations/**", "**/*.pyc"],
            ),
            TargetConfig(
                name="mobile",
                root="mobile/",
                language="dart",
                ignore_paths=["mobile/**/*.g.dart", "mobile/build/**"],
            ),
            TargetConfig(
                name="web",
                root="frontend/web/",
                language="fallback",
                ignore_paths=["frontend/web/node_modules/**"],
            ),
        ],
    )


class TestRouteFile:
    def test_backend_file_routes_to_backend(self, tmp_path):
        cfg = _make_config()
        r = route_file("app/prompt_builder.py", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ("backend",)

    def test_mobile_dart_routes_to_mobile(self, tmp_path):
        cfg = _make_config()
        r = route_file("mobile/lib/pages/home.dart", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ("mobile",)

    def test_web_jsx_routes_to_web(self, tmp_path):
        cfg = _make_config()
        r = route_file("frontend/web/src/App.jsx", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ("web",)

    def test_global_ignored_git(self, tmp_path):
        cfg = _make_config()
        r = route_file(".git/config", cfg, tmp_path)
        assert r.ignored
        assert "global:" in r.ignore_reason

    def test_global_ignored_pycache(self, tmp_path):
        cfg = _make_config()
        r = route_file("app/__pycache__/foo.pyc", cfg, tmp_path)
        assert r.ignored
        assert "global:" in r.ignore_reason

    def test_target_ignored_migrations(self, tmp_path):
        cfg = _make_config()
        # 文件路径在 backend target 下，但被 backend.ignore_paths 匹配
        r = route_file("app/migrations/0001_init.py", cfg, tmp_path)
        # 不匹配 backend（被 target ignore）
        assert "backend" not in r.matched_targets

    def test_dart_generated_file_ignored(self, tmp_path):
        cfg = _make_config()
        r = route_file("mobile/lib/api.g.dart", cfg, tmp_path)
        assert "mobile" not in r.matched_targets

    def test_unmatched_file(self, tmp_path):
        cfg = _make_config()
        r = route_file("random_readme.md", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ()

    def test_windows_path_with_backslash(self, tmp_path):
        cfg = _make_config()
        r = route_file("app\\prompt_builder.py", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ("backend",)

    def test_absolute_path_under_project(self, tmp_path):
        cfg = _make_config()
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "x.py").touch()
        r = route_file(tmp_path / "app" / "x.py", cfg, tmp_path)
        assert not r.ignored
        assert r.matched_targets == ("backend",)
