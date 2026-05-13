"""active_tasks Stop hook 测试

覆盖场景：
1. active_tasks.json 含 pending → check_active_tasks.py exit 2
2. active_tasks.json 不存在 → exit 0
3. active_tasks.json pending 为空 → exit 0
4. active_tasks.json 格式错误 → exit 0（静默放行）
5. harness init 后：settings.json 含 Stop hook + check_active_tasks.py 文件存在
6. active_tasks_helper 的 write/mark_completed/clear/read 函数
7. 不破坏现有 Stop hook（已有 Stop 不被覆盖）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.adapters.claude_code import install_hooks
from harness.adapters.claude_code.active_tasks_helper import (
    clear_active_tasks,
    mark_completed,
    read_active_tasks,
    write_active_tasks,
)
from harness.adapters.claude_code.install_hooks import ACTIVE_TASKS_MARKER, CHECK_ACTIVE_TASKS_SCRIPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tasks(tmp_path: Path, data: dict) -> Path:
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir(exist_ok=True)
    p = harness_dir / "active_tasks.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _run_check_script(tmp_path: Path) -> int:
    """把 CHECK_ACTIVE_TASKS_SCRIPT 写到 tmp_path/.harness/，然后运行，返回 exit code。"""
    script = tmp_path / ".harness" / "check_active_tasks.py"
    script.parent.mkdir(exist_ok=True)
    script.write_text(CHECK_ACTIVE_TASKS_SCRIPT, encoding="utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
    )
    return result.returncode


# ---------------------------------------------------------------------------
# check_active_tasks.py 行为
# ---------------------------------------------------------------------------

class TestCheckActiveTasksScript:
    def test_pending_tasks_exit_2(self, tmp_path):
        _write_tasks(tmp_path, {"pending": ["check", "review"], "completed": ["execute"]})
        assert _run_check_script(tmp_path) == 2

    def test_no_file_exit_0(self, tmp_path):
        # 不写任何文件
        assert _run_check_script(tmp_path) == 0

    def test_empty_pending_exit_0(self, tmp_path):
        _write_tasks(tmp_path, {"pending": [], "completed": ["execute", "check", "review", "commit"]})
        assert _run_check_script(tmp_path) == 0

    def test_corrupt_json_exit_0(self, tmp_path):
        harness_dir = tmp_path / ".harness"
        harness_dir.mkdir(exist_ok=True)
        (harness_dir / "active_tasks.json").write_text("not valid json!!!", encoding="utf-8")
        assert _run_check_script(tmp_path) == 0

    def test_exit_2_prints_reason(self, tmp_path):
        _write_tasks(tmp_path, {"pending": ["review"], "completed": []})
        script = tmp_path / ".harness" / "check_active_tasks.py"
        script.parent.mkdir(exist_ok=True)
        script.write_text(CHECK_ACTIVE_TASKS_SCRIPT, encoding="utf-8")
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, str(script)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "review" in result.stdout


# ---------------------------------------------------------------------------
# install_hooks → settings.json + check_active_tasks.py 文件
# ---------------------------------------------------------------------------

class TestInstallHooksActiveTasks:
    def test_default_installs_active_tasks_stop_hook(self, tmp_path):
        install_hooks(tmp_path)
        data = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        assert "Stop" in data["hooks"]
        stop_cmds = [h.get("command", "") for entry in data["hooks"]["Stop"] for h in entry.get("hooks", [])]
        assert any(ACTIVE_TASKS_MARKER in c for c in stop_cmds)

    def test_default_generates_check_script(self, tmp_path):
        install_hooks(tmp_path)
        script = tmp_path / ".harness" / "check_active_tasks.py"
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "active_tasks.json" in content
        assert "exit 2" in content or "return 2" in content

    def test_no_active_tasks_skips_hook(self, tmp_path):
        install_hooks(tmp_path, with_active_tasks=False)
        data = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        stop_entries = data.get("hooks", {}).get("Stop", [])
        stop_cmds = [h.get("command", "") for entry in stop_entries for h in entry.get("hooks", [])]
        assert not any(ACTIVE_TASKS_MARKER in c for c in stop_cmds)
        assert not (tmp_path / ".harness" / "check_active_tasks.py").exists()

    def test_preserves_existing_stop_hook(self, tmp_path):
        """已有 Stop hook 不被覆盖，active-tasks hook 追加。"""
        (tmp_path / ".claude").mkdir()
        settings = tmp_path / ".claude" / "settings.json"
        existing = {
            "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "echo my-own-stop-hook"}]}]
            }
        }
        settings.write_text(json.dumps(existing), encoding="utf-8")

        install_hooks(tmp_path)
        data = json.loads(settings.read_text(encoding="utf-8"))
        stop_entries = data["hooks"]["Stop"]
        # 原有 hook 依然存在
        all_cmds = [h.get("command", "") for e in stop_entries for h in e.get("hooks", [])]
        assert any("my-own-stop-hook" in c for c in all_cmds)
        # harness active-tasks hook 也追加了
        assert any(ACTIVE_TASKS_MARKER in c for c in all_cmds)

    def test_idempotent_active_tasks(self, tmp_path):
        install_hooks(tmp_path)
        install_hooks(tmp_path)
        data = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        stop_entries = data["hooks"]["Stop"]
        all_cmds = [h.get("command", "") for e in stop_entries for h in e.get("hooks", [])]
        # 不重复安装
        assert len([c for c in all_cmds if ACTIVE_TASKS_MARKER in c]) == 1


# ---------------------------------------------------------------------------
# active_tasks_helper 函数
# ---------------------------------------------------------------------------

class TestActiveTasksHelper:
    def test_write_and_read(self, tmp_path):
        write_active_tasks(tmp_path, pending=["execute", "check"], completed=["setup"])
        data = read_active_tasks(tmp_path)
        assert data["pending"] == ["execute", "check"]
        assert data["completed"] == ["setup"]

    def test_read_missing_file(self, tmp_path):
        data = read_active_tasks(tmp_path)
        assert data == {"pending": [], "completed": []}

    def test_mark_completed_moves_task(self, tmp_path):
        write_active_tasks(tmp_path, pending=["execute", "check"])
        mark_completed(tmp_path, "execute")
        data = read_active_tasks(tmp_path)
        assert "execute" not in data["pending"]
        assert "execute" in data["completed"]
        assert "check" in data["pending"]

    def test_mark_completed_no_file_silent(self, tmp_path):
        # 文件不存在时不报错
        mark_completed(tmp_path, "execute")

    def test_mark_completed_idempotent(self, tmp_path):
        write_active_tasks(tmp_path, pending=["execute"])
        mark_completed(tmp_path, "execute")
        mark_completed(tmp_path, "execute")  # 第二次不重复添加
        data = read_active_tasks(tmp_path)
        assert data["completed"].count("execute") == 1

    def test_clear_active_tasks(self, tmp_path):
        write_active_tasks(tmp_path, pending=["check", "review"])
        clear_active_tasks(tmp_path)
        data = read_active_tasks(tmp_path)
        assert data["pending"] == []
        assert data["completed"] == []

    def test_clear_no_file_silent(self, tmp_path):
        # 文件不存在时不报错
        clear_active_tasks(tmp_path)

    def test_write_creates_harness_dir(self, tmp_path):
        assert not (tmp_path / ".harness").exists()
        write_active_tasks(tmp_path, pending=["execute"])
        assert (tmp_path / ".harness" / "active_tasks.json").exists()
