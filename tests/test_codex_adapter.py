"""Codex 适配层测试：scanner / init / sync / handoff / anti_patterns include-exclude。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from harness.adapters.codex import (
    codex_source_dir,
    ensure_handoff,
    init_codex_project,
    inspect_project,
    list_tracked_skills,
    pull_from_codex_home,
    sync_status,
    sync_to_codex_home,
)
from harness.cli import main
from harness.config import AntiPatternRule, HarnessConfig
from harness.validate.anti_patterns import run_anti_patterns


class TestScanner:
    def test_detects_unity_scripts_and_skips_heavy_dirs(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
        (tmp_path / "game" / "client" / "Assets").mkdir(parents=True)
        (tmp_path / "game" / "client" / "ProjectSettings").mkdir(parents=True)
        (tmp_path / "game" / "client" / "Library").mkdir(parents=True)
        (tmp_path / "game" / "client" / "Library" / "verify-fake.ps1").write_text("", encoding="utf-8")
        (tmp_path / "game" / "tools").mkdir(parents=True)
        (tmp_path / "game" / "tools" / "verify-runtime.ps1").write_text("", encoding="utf-8")
        (tmp_path / "game" / "tools" / "build-client.ps1").write_text("", encoding="utf-8")

        scan = inspect_project(tmp_path)
        assert "unity" in scan["types"]
        assert scan["unity_roots"] == ["game/client"]
        assert "game/tools/verify-runtime.ps1" in scan["scripts"]["verify"]
        assert "game/tools/build-client.ps1" in scan["scripts"]["build"]
        # Library 目录必须被跳过
        assert not any("Library" in s for s in scan["scripts"]["verify"])
        assert "README.md" in scan["docs"]


class TestCodexInit:
    def test_fresh_codex_init_creates_thin_files_without_claude_hooks(self, tmp_path: Path):
        (tmp_path / "game" / "tools").mkdir(parents=True)
        (tmp_path / "game" / "tools" / "verify-demo.ps1").write_text("", encoding="utf-8")

        res = init_codex_project(tmp_path)
        assert ".harness/config.yaml" in res["created"]
        assert ".harness/.gitignore" in res["created"]
        assert "AGENTS.md" in res["created"]
        assert ".harness/handoff.md" in res["created"]
        assert not (tmp_path / ".claude").exists()

        agents_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert len(agents_text.splitlines()) <= 40
        assert "verify-demo.ps1" in agents_text

        handoff_text = (tmp_path / ".harness" / "handoff.md").read_text(encoding="utf-8")
        for heading in ("## 1. 已验证事实", "## 2. 试过确认不行的路", "## 3. 未决项", "## 4. 下一步最小动作"):
            assert heading in handoff_text

    def test_preserves_existing_agents_and_config(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text("# Custom OH2 Rules\nkeep me\n", encoding="utf-8")
        res = init_codex_project(tmp_path)
        assert "AGENTS.md" in res["preserved"]
        assert "keep me" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    def test_cli_inspect_json_outputs_parseable_json(self, tmp_path: Path):
        runner = CliRunner()
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            r = runner.invoke(main, ["init", "--agent", "codex", "--inspect-json"])
        finally:
            os.chdir(cwd)
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["scan"]["project"] == tmp_path.name
        assert ".harness/config.yaml" in data["created"]


class TestCodexSync:
    def test_push_backup_idempotent_and_preserves_untracked_skills(self, tmp_path: Path):
        fake_src = tmp_path / "src_codex"
        fake_home = tmp_path / "home_codex"

        (fake_src / "skills" / "bug-investigation").mkdir(parents=True)
        (fake_src / "AGENTS.md").write_text("# Global v2\n", encoding="utf-8")
        (fake_src / "skills" / "bug-investigation" / "SKILL.md").write_text("---\nname: bug-investigation\n---\n", encoding="utf-8")

        # 模拟用户原有 AGENTS.md 与私人画图技能 whalechan-image-comic
        (fake_home / "skills" / "whalechan-image-comic").mkdir(parents=True)
        (fake_home / "AGENTS.md").write_text("# Old Global v1\n", encoding="utf-8")
        (fake_home / "skills" / "whalechan-image-comic" / "keep.txt").write_text("do not delete", encoding="utf-8")

        # Dry-run 不改文件
        dr = sync_to_codex_home(codex_home=fake_home, source_dir=fake_src, dry_run=True)
        assert "AGENTS.md" in dr["updated"]
        assert (fake_home / "AGENTS.md").read_text(encoding="utf-8") == "# Old Global v1\n"

        # 首次真实同步：应备份旧 AGENTS.md 并保留 whalechan 私人技能
        r1 = sync_to_codex_home(codex_home=fake_home, source_dir=fake_src)
        assert "AGENTS.md" in r1["updated"]
        assert "skills/bug-investigation" in r1["updated"]
        assert len(r1["backups"]) == 1
        assert (fake_home / r1["backups"][0]).read_text(encoding="utf-8") == "# Old Global v1\n"
        assert (fake_home / "skills" / "whalechan-image-comic" / "keep.txt").read_text(encoding="utf-8") == "do not delete"

        # 状态应为 in_sync
        st = sync_status(codex_home=fake_home, source_dir=fake_src)
        assert st["in_sync"] is True

        # 二次同步应完全幂等，不生成新备份
        r2 = sync_to_codex_home(codex_home=fake_home, source_dir=fake_src)
        assert r2["updated"] == []
        assert r2["backups"] == []

        # 本地修改后 --pull 应能回拉到源目录
        (fake_home / "AGENTS.md").write_text("# Global v3 edited on PC2\n", encoding="utf-8")
        rp = pull_from_codex_home(codex_home=fake_home, source_dir=fake_src)
        assert "AGENTS.md" in rp["updated"]
        assert (fake_src / "AGENTS.md").read_text(encoding="utf-8") == "# Global v3 edited on PC2\n"

    def test_bundled_codex_home_has_core_skills(self):
        src = codex_source_dir()
        assert (src / "AGENTS.md").is_file()
        skills = list_tracked_skills(src)
        assert "bug-investigation" in skills
        assert "codex-project-init" in skills
        assert "existing-flow-review" in skills
        assert "long-task-handoff" in skills
        # 不应包含 18MB 私人画图技能
        assert "whalechan-image-comic" not in skills
        assert "whalechan-image-character" not in skills
        # OH 单项目 Sentry 规则应已从全局移除
        global_text = (src / "AGENTS.md").read_text(encoding="utf-8")
        assert "OH-TEST-BUILD-NO-SENTRY-SYMBOL-UPLOAD" not in global_text


class TestHandoff:
    def test_handoff_local_and_global(self, tmp_path: Path):
        p_local, created1 = ensure_handoff(tmp_path, use_global=False)
        assert created1 is True
        assert p_local == (tmp_path / ".harness" / "handoff.md").resolve()

        p_local2, created2 = ensure_handoff(tmp_path, use_global=False)
        assert created2 is False
        assert p_local2 == p_local

        fake_home = tmp_path / "codex_home"
        p_global, created_g = ensure_handoff(tmp_path, use_global=True, codex_home=fake_home)
        assert created_g is True
        assert p_global.parent.parent == (fake_home / "handoffs").resolve()


class TestAntiPatternIncludeExcludeAndNewLangs:
    def test_rule_include_exclude_and_lua_powershell(self, tmp_path: Path):
        (tmp_path / "game" / "Runtime").mkdir(parents=True)
        (tmp_path / "game" / "Editor").mkdir(parents=True)
        (tmp_path / "server" / "lua").mkdir(parents=True)

        (tmp_path / "game" / "Runtime" / "Foo.cs").write_text("using UnityEditor;\n", encoding="utf-8")
        (tmp_path / "game" / "Editor" / "Bar.cs").write_text("using UnityEditor;\n", encoding="utf-8")
        (tmp_path / "server" / "lua" / "offline.lua").write_text("print('DEBUG_TODO')\n", encoding="utf-8")

        cfg = HarnessConfig(
            project="demo",
            anti_patterns={
                "csharp": [
                    AntiPatternRule(
                        name="no_editor_in_runtime",
                        pattern=r"^using UnityEditor\b",
                        msg="Runtime 代码禁止裸 using UnityEditor",
                        severity="error",
                        include=["game/Runtime/**/*.cs"],
                        exclude=["**/Editor/**"],
                    )
                ],
                "lua": [
                    AntiPatternRule(
                        name="no_debug_todo",
                        pattern=r"DEBUG_TODO",
                        msg="禁止遗留 DEBUG_TODO",
                        severity="warn",
                    )
                ],
            },
        )
        res = run_anti_patterns(cfg, tmp_path, None)
        assert res.status == "fail"
        findings = res.details["findings"]
        files = {f["file"] for f in findings}
        assert "game/Runtime/Foo.cs" in files
        assert "game/Editor/Bar.cs" not in files
        assert "server/lua/offline.lua" in files
