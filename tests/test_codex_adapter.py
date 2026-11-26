"""Codex 适配层测试：scanner / init / sync / handoff / anti_patterns include-exclude。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from harness.adapters.codex import (
    TaskValidationError,
    add_task,
    build_subagent_brief,
    clear_tasks,
    codex_source_dir,
    ensure_handoff,
    evaluate_diff_entries,
    init_codex_project,
    inspect_project,
    list_tracked_skills,
    parse_numstat,
    pull_from_codex_home,
    sync_status,
    sync_to_codex_home,
    sync_to_opencode,
    tasks_md_path,
    update_task,
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
        assert "bug-fix-verify" in skills
        assert "codex-project-init" in skills
        assert "thin-orchestrator" in skills
        assert "existing-flow-review" in skills
        assert "long-task-handoff" in skills
        # 不应包含 18MB 私人画图技能
        assert "whalechan-image-comic" not in skills
        assert "whalechan-image-character" not in skills
        # OH 单项目 Sentry 规则应已从全局移除
        global_text = (src / "AGENTS.md").read_text(encoding="utf-8")
        assert "OH-TEST-BUILD-NO-SENTRY-SYMBOL-UPLOAD" not in global_text
        assert "收益/复杂度红线" in global_text
        assert "AUTONOMY-GATE-v1" in global_text

    def test_sync_to_opencode_preserves_existing_skills(self, tmp_path: Path):
        fake_oc = tmp_path / "opencode_cfg"
        fake_skills = tmp_path / "agent_skills"
        (fake_skills / "cua-driver").mkdir(parents=True)
        (fake_skills / "cua-driver" / "SKILL.md").write_text("keep", encoding="utf-8")

        res = sync_to_opencode(opencode_config_dir=fake_oc, shared_skills_dir=fake_skills)
        assert "opencode/AGENTS.md" in res["updated"]
        assert ".agents/skills/bug-investigation" in res["updated"]
        assert (fake_skills / "cua-driver" / "SKILL.md").read_text(encoding="utf-8") == "keep"


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


class TestTaskBoard:
    def test_need_fix_enforces_files_verify_fact_and_blocks_file_collision(self, tmp_path: Path):
        import pytest

        add_task(tmp_path, "QA72", "英语环境出现中文提示", kind="bug")
        add_task(tmp_path, "QA74", "回网不触发下载", kind="bug")

        # need_fix 缺 files/verify/fact 必须拒收
        with pytest.raises(TaskValidationError, match="--files"):
            update_task(tmp_path, "QA72", verdict="need_fix")

        # blocked_external 缺 note 必须拒收
        with pytest.raises(TaskValidationError, match="blocked_external"):
            update_task(tmp_path, "QA74", verdict="blocked_external")

        # fixed_pending_qa 缺 fact 必须拒收，补全后正常落盘并渲染“代码已修，待复测”
        add_task(tmp_path, "QA54", "离线剧情奖励动画", kind="bug")
        with pytest.raises(TaskValidationError, match="fixed_pending_qa"):
            update_task(tmp_path, "QA54", verdict="fixed_pending_qa")
        update_task(
            tmp_path,
            "QA54",
            verdict="fixed_pending_qa",
            fact="LocalPlayBridge.cs:670-675 抑制重复建造同步逻辑仍在当前代码中",
        )

        # fact 超长必须拒收（防 30KB 流水账）
        with pytest.raises(TaskValidationError, match="过长"):
            update_task(tmp_path, "QA72", fact="x" * 450)

        # 合法录入 QA72 并进入 fixing
        update_task(
            tmp_path,
            "QA72",
            verdict="need_fix",
            status="fixing",
            fact="SilentDownloadVM.cs:794 硬编码中文",
            files="client/Assets/SilentDownloadVM.cs",
            verify="切英语触发未初始化提示",
            owner="subagent",
        )

        # QA74 想并行修改同一个文件 → 必须被防撞车硬拦截
        with pytest.raises(TaskValidationError, match="并行文件冲突"):
            update_task(
                tmp_path,
                "QA74",
                verdict="need_fix",
                status="fixing",
                fact="SilentDownloadVM.cs:787 未初始化直接返回",
                files="client/Assets/SilentDownloadVM.cs",
                verify="断网过关回网触发真实 GET",
            )

        # QA72 完成后，QA74 才能进入 fixing
        update_task(tmp_path, "QA72", status="done", verdict="done")
        update_task(
            tmp_path,
            "QA74",
            verdict="need_fix",
            status="fixing",
            fact="SilentDownloadVM.cs:787 未初始化直接返回",
            files="client/Assets/SilentDownloadVM.cs",
            verify="断网过关回网触发真实 GET",
        )

        # 自动渲染紧凑总表：fixing / need_fix 置顶，done / fixed_pending_qa 靠后
        md = tasks_md_path(tmp_path).read_text(encoding="utf-8")
        assert "QA72" in md and "QA74" in md and "QA54" in md
        assert md.index("| `QA74` |") < md.index("| `QA54` |") < md.index("| `QA72` |")
        assert md.index("## 优先处理") < md.index("| 编号 | 类型 |")
        brief = build_subagent_brief(tmp_path, "QA74")
        assert "SilentDownloadVM.cs" in brief
        assert "严禁越界修改范围外文件" in brief
        assert "diff-guard" in brief
        assert "改动预算硬闸门" in brief

        removed = clear_tasks(tmp_path, only_done=True)
        assert removed == 1

    def test_cli_task_workflow(self, tmp_path: Path):
        runner = CliRunner()
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            r1 = runner.invoke(main, ["task", "add", "UI-01", "优化商店入场动效", "--kind", "ui"])
            assert r1.exit_code == 0, r1.output

            # 缺字段应返回非 0 退出码
            r_bad = runner.invoke(main, ["task", "update", "UI-01", "--verdict", "need_fix"])
            assert r_bad.exit_code == 2

            r2 = runner.invoke(
                main,
                [
                    "task",
                    "update",
                    "UI-01",
                    "--verdict",
                    "need_fix",
                    "--fact",
                    "ShopPanel.cs:88 缺少 200ms 展开缓动",
                    "--files",
                    "game/client/Assets/Camp/Runtime/UI/ShopPanel.cs",
                    "--verify",
                    "跑 verify-camp-runtime.ps1 + 实拍帧对比",
                ],
            )
            assert r2.exit_code == 0, r2.output

            r_list = runner.invoke(main, ["task", "list", "--json"])
            assert r_list.exit_code == 0
            data = json.loads(r_list.output)
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == "UI-01"

            r_brief = runner.invoke(main, ["task", "brief", "UI-01"])
            assert r_brief.exit_code == 0
            assert "ShopPanel.cs" in r_brief.output

            # 长任务 done-check：仍有未完成必做单时必须返回 exit 2 挡住提前收尾
            runner.invoke(main, ["task", "add", "MUMU-SIGN", "签到模拟器验收", "--kind", "feat"])
            runner.invoke(main, ["task", "add", "MUMU-JAR", "打罐模拟器验收", "--kind", "feat"])
            runner.invoke(main, ["task", "update", "MUMU-SIGN", "--status", "done", "--verdict", "done", "--fact", "280金币通过"])
            r_dc_red = runner.invoke(main, ["task", "done-check", "--prefix", "MUMU-"])
            assert r_dc_red.exit_code == 2
            assert "MUMU-JAR" in r_dc_red.output

            # 全部完成或真实外部阻塞后，done-check 变绿 (exit 0)
            runner.invoke(main, ["task", "update", "MUMU-JAR", "--status", "done", "--verdict", "done", "--fact", "打罐同步通过"])
            r_dc_green = runner.invoke(main, ["task", "done-check", "--prefix", "MUMU-"])
            assert r_dc_green.exit_code == 0
        finally:
            os.chdir(cwd)


class TestDiffGuard:
    def test_green_for_small_fix_and_subtraction_refactor(self):
        # 类似 QA81：1 个运行文件 +29/-17（净增 +12）+ 1 个测试文件 +200 → 绿灯
        entries = parse_numstat(
            "29\t17\tclient/Packages/ImGamePkg/Runtime/Game/Business/Activity/StarCollection/StarCollectionVM.cs\n"
            "200\t0\tclient/Packages/ImGamePkg/Editor/LocalPlaySnapshotCheck.StarQa.cs\n"
            "50\t0\tdoc/report.md\n"
        )
        res = evaluate_diff_entries(entries, hub_files=["LocalPlayBridge.cs", "LoginMgr.cs"])
        assert res["status"] == "green"
        assert res["runtime"]["files_count"] == 1
        assert res["runtime"]["net"] == 12
        assert res["non_runtime"]["files_count"] == 2

        # 减法修 bug：加 30 行删 90 行（净增 -60）→ 绿灯
        entries_sub = parse_numstat("30\t90\tsrc/foo.cs\n")
        res_sub = evaluate_diff_entries(entries_sub, max_net_added_lines=80)
        assert res_sub["status"] == "green"
        assert res_sub["runtime"]["net"] == -60

    def test_red_when_exceeding_files_lines_or_touching_hub_file(self):
        entries = parse_numstat(
            "50\t0\tclient/Packages/ImGamePkg/Runtime/Game/Core/LocalPlayBridge.cs\n"
            "30\t0\tclient/Packages/ImGamePkg/Runtime/A.cs\n"
            "20\t0\tclient/Packages/ImGamePkg/Runtime/B.cs\n"
            "10\t0\tclient/Packages/ImGamePkg/Runtime/C.cs\n"
        )
        res = evaluate_diff_entries(
            entries,
            max_runtime_files=3,
            max_net_added_lines=80,
            hub_files=["LocalPlayBridge.cs"],
        )
        assert res["status"] == "red"
        assert len(res["triggers"]) == 3
        assert "client/Packages/ImGamePkg/Runtime/Game/Core/LocalPlayBridge.cs" in res["touched_hubs"]

    def test_cli_diff_guard_in_git_repo(self, tmp_path: Path):
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Hub.cs").write_text("class Hub {}\n", encoding="utf-8")
        (tmp_path / ".harness").mkdir()
        (tmp_path / ".harness" / "config.yaml").write_text(
            "project: demo\nagent: codex\ndiff_budget:\n  max_runtime_files: 3\n  max_net_added_lines: 80\n  hub_files:\n    - Hub.cs\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

        # 未改前应 GREEN (exit 0)
        runner = CliRunner()
        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            r0 = runner.invoke(main, ["diff-guard"])
            assert r0.exit_code == 0, r0.output

            # 改到核心枢纽文件 Hub.cs → 应 RED (exit 2)
            (tmp_path / "src" / "Hub.cs").write_text("class Hub { int x = 1; }\n", encoding="utf-8")
            r1 = runner.invoke(main, ["diff-guard", "--json"])
            assert r1.exit_code == 2
            data = json.loads(r1.output)
            assert data["status"] == "red"
            assert "src/Hub.cs" in data["touched_hubs"]
        finally:
            os.chdir(cwd)

