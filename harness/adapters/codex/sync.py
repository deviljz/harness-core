"""Codex 全局规则与通用工程 Skill 的双向同步（`harness sync` / `harness sync --pull`）。

安全铁律：
- 推向 `~/.codex/` 时，如果 `AGENTS.md` 内容有变更，先留时间戳备份 `AGENTS.md.before-harness-sync-*.bak`
- 只同步 `harness/codex_home/skills/` 中登记的通用工程 Skill，绝不删除或改动用户本机其他私人 Skill（如 `whalechan-*`、`.system`）
- 内容一致时幂等跳过，不刷无用备份
"""
from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

IGNORED_NAMES: frozenset[str] = frozenset({"__pycache__", ".DS_Store", "Thumbs.db"})
IGNORED_SUFFIXES: frozenset[str] = frozenset({".pyc", ".pyo"})


def resolve_codex_home(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def codex_source_dir() -> Path:
    """返回随包发布的 `harness/codex_home/` 目录。"""
    return (Path(__file__).resolve().parents[2] / "codex_home").resolve()


def list_tracked_skills(source_dir: Path | None = None) -> list[str]:
    src = (source_dir or codex_source_dir()) / "skills"
    if not src.is_dir():
        return []
    return sorted(
        d.name
        for d in src.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").is_file()
    )


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_manifest(directory: Path) -> dict[str, str]:
    """返回目录下所有有效文件的 {posix相对路径: sha256}。"""
    if not directory.is_dir():
        return {}
    manifest: dict[str, str] = {}
    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue
        if any(part in IGNORED_NAMES for part in p.relative_to(directory).parts):
            continue
        if p.suffix.lower() in IGNORED_SUFFIXES:
            continue
        rel = p.relative_to(directory).as_posix()
        manifest[rel] = _file_sha256(p)
    return manifest


def _copy_skill_dir(src_dir: Path, dst_dir: Path) -> None:
    """将单个 skill 目录精确同步到目标（不碰兄弟 skill 目录）。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    src_manifest = _dir_manifest(src_dir)
    dst_manifest = _dir_manifest(dst_dir)

    # 拷贝新增或变化文件
    for rel, src_hash in src_manifest.items():
        if dst_manifest.get(rel) == src_hash:
            continue
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_dir / rel, dst_file)

    # 清理该 skill 内部已废弃的旧文件
    for rel in dst_manifest:
        if rel not in src_manifest:
            old_file = dst_dir / rel
            if old_file.exists():
                old_file.unlink()


def sync_status(
    codex_home: Path | None = None,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    """检查 `~/.codex/` 与 `harness/codex_home/` 是否一致。"""
    home = resolve_codex_home(codex_home)
    src = (source_dir or codex_source_dir()).resolve()

    src_agents = src / "AGENTS.md"
    dst_agents = home / "AGENTS.md"
    if not src_agents.is_file():
        agents_state = "source_missing"
    elif not dst_agents.is_file():
        agents_state = "missing_in_codex_home"
    elif _file_sha256(src_agents) == _file_sha256(dst_agents):
        agents_state = "in_sync"
    else:
        agents_state = "drifted"

    skills_state: dict[str, str] = {}
    for skill in list_tracked_skills(src):
        s_man = _dir_manifest(src / "skills" / skill)
        d_man = _dir_manifest(home / "skills" / skill)
        if not d_man:
            skills_state[skill] = "missing_in_codex_home"
        elif s_man == d_man:
            skills_state[skill] = "in_sync"
        else:
            skills_state[skill] = "drifted"

    in_sync = agents_state == "in_sync" and all(v == "in_sync" for v in skills_state.values())
    return {
        "codex_home": home.as_posix(),
        "source_dir": src.as_posix(),
        "in_sync": in_sync,
        "agents": agents_state,
        "skills": skills_state,
    }


def sync_to_codex_home(
    *,
    codex_home: Path | None = None,
    only: str = "all",
    dry_run: bool = False,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    """把 `harness/codex_home/` 同步到 `~/.codex/`（自动备份改动前的 AGENTS.md）。"""
    home = resolve_codex_home(codex_home)
    src = (source_dir or codex_source_dir()).resolve()

    updated: list[str] = []
    unchanged: list[str] = []
    backups: list[str] = []

    if only in ("all", "agents"):
        src_agents = src / "AGENTS.md"
        dst_agents = home / "AGENTS.md"
        if src_agents.is_file():
            need_update = (not dst_agents.is_file()) or (_file_sha256(src_agents) != _file_sha256(dst_agents))
            if need_update:
                if not dry_run:
                    home.mkdir(parents=True, exist_ok=True)
                    if dst_agents.is_file():
                        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                        bak = home / f"AGENTS.md.before-harness-sync-{ts}.bak"
                        shutil.copy2(dst_agents, bak)
                        backups.append(bak.name)
                    shutil.copy2(src_agents, dst_agents)
                updated.append("AGENTS.md")
            else:
                unchanged.append("AGENTS.md")

    if only in ("all", "skills"):
        for skill in list_tracked_skills(src):
            s_dir = src / "skills" / skill
            d_dir = home / "skills" / skill
            if _dir_manifest(s_dir) == _dir_manifest(d_dir):
                unchanged.append(f"skills/{skill}")
            else:
                if not dry_run:
                    _copy_skill_dir(s_dir, d_dir)
                updated.append(f"skills/{skill}")

    return {
        "direction": "push_to_codex_home",
        "dry_run": dry_run,
        "codex_home": home.as_posix(),
        "source_dir": src.as_posix(),
        "updated": updated,
        "unchanged": unchanged,
        "backups": backups,
    }


def pull_from_codex_home(
    *,
    codex_home: Path | None = None,
    only: str = "all",
    dry_run: bool = False,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    """把本机 `~/.codex/` 中已追踪的 `AGENTS.md` 和工程 Skill 回拉到 `harness/codex_home/` 以便 git 提交。"""
    home = resolve_codex_home(codex_home)
    src = (source_dir or codex_source_dir()).resolve()

    updated: list[str] = []
    unchanged: list[str] = []
    skipped_missing: list[str] = []

    if only in ("all", "agents"):
        home_agents = home / "AGENTS.md"
        repo_agents = src / "AGENTS.md"
        if not home_agents.is_file():
            skipped_missing.append("AGENTS.md")
        elif repo_agents.is_file() and _file_sha256(home_agents) == _file_sha256(repo_agents):
            unchanged.append("AGENTS.md")
        else:
            if not dry_run:
                repo_agents.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(home_agents, repo_agents)
            updated.append("AGENTS.md")

    if only in ("all", "skills"):
        for skill in list_tracked_skills(src):
            h_dir = home / "skills" / skill
            r_dir = src / "skills" / skill
            if not h_dir.is_dir():
                skipped_missing.append(f"skills/{skill}")
                continue
            if _dir_manifest(h_dir) == _dir_manifest(r_dir):
                unchanged.append(f"skills/{skill}")
            else:
                if not dry_run:
                    _copy_skill_dir(h_dir, r_dir)
                updated.append(f"skills/{skill}")

    return {
        "direction": "pull_from_codex_home",
        "dry_run": dry_run,
        "codex_home": home.as_posix(),
        "source_dir": src.as_posix(),
        "updated": updated,
        "unchanged": unchanged,
        "skipped_missing": skipped_missing,
    }
