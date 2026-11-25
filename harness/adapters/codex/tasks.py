"""轻量本地任务板（`python -m harness task`）：给“主对话薄总控 + 子 Agent 按单干活”提供硬校验与防撞车。

设计铁律：
- 存放在 `<project>/.harness/tasks.json`（不污染共享 git），同步渲染 ≤1 页的 `.harness/tasks.md`
- 程序硬校验，不靠模型自觉：
  1. `verdict=need_fix` 必须写清 `--files`（改哪些文件）和 `--verify`（怎么验收）
  2. `verdict=blocked_external` 必须写清 `--note`（具体缺哪项外部条件）
  3. 同一文件已被其他 `status=fixing` 的任务占用时拦截冲突，防并行子 Agent 互相踩文件
  4. 单字段长度设上限，杜绝再滚成 30 KB 流水账
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

VALID_KINDS = ("bug", "ui", "feat", "other")
VALID_STATUSES = ("open", "fixing", "done", "skipped")
VALID_VERDICTS = ("pending", "no_fix", "need_fix", "fixed_pending_qa", "blocked_external", "done")

VERDICT_LABELS = {
    "pending": "待查",
    "no_fix": "无需改代码",
    "need_fix": "确认需改代码",
    "fixed_pending_qa": "代码已修，待复测",
    "blocked_external": "真缺线索/卡外部",
    "done": "已完成",
}

MAX_FACT_CHARS = 400
MAX_NOTE_CHARS = 300


class TaskValidationError(ValueError):
    """任务板硬校验失败（缺必填字段、超长或并行文件冲突）。"""


def tasks_json_path(root: Path) -> Path:
    return root.resolve() / ".harness" / "tasks.json"


def tasks_md_path(root: Path) -> Path:
    return root.resolve() / ".harness" / "tasks.md"


def load_tasks(root: Path) -> dict[str, Any]:
    path = tasks_json_path(root)
    if not path.is_file():
        return {"project": root.resolve().name, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except Exception:
        pass
    return {"project": root.resolve().name, "items": []}


def _normalize_files(files: list[str] | str | None) -> list[str]:
    if not files:
        return []
    raw_list = files.split(",") if isinstance(files, str) else list(files)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_list:
        norm = item.strip().replace("\\", "/")
        if norm and norm not in seen:
            seen.add(norm)
            cleaned.append(norm)
    return cleaned


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _find_item(data: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    key = task_id.strip().lower()
    for it in data["items"]:
        if str(it.get("id", "")).strip().lower() == key:
            return it
    return None


def _check_file_collisions(
    data: dict[str, Any],
    task_id: str,
    files: list[str],
    new_status: str,
) -> list[tuple[str, str]]:
    """当某任务进入 `fixing` 时，检查其涉及文件是否已被其他 `fixing` 任务占用。"""
    if new_status != "fixing" or not files:
        return []
    target_set = {f.lower() for f in files}
    conflicts: list[tuple[str, str]] = []
    for it in data["items"]:
        other_id = str(it.get("id", ""))
        if other_id.strip().lower() == task_id.strip().lower():
            continue
        if it.get("status") != "fixing":
            continue
        for f in it.get("files") or []:
            if f.lower() in target_set:
                conflicts.append((other_id, f))
    return conflicts


def _item_sort_key(it: dict[str, Any]) -> tuple[int, str]:
    """按紧急度排序：正在修 > 确认需改代码 > 待查 > 卡外部 > 代码已修待复测 > 无需改 > 已完成/跳过。"""
    status = it.get("status", "open")
    verdict = it.get("verdict", "pending")
    tid = str(it.get("id", ""))
    if status == "fixing":
        rank = 0
    elif status in ("done", "skipped"):
        rank = 6
    elif verdict == "need_fix":
        rank = 1
    elif verdict == "pending":
        rank = 2
    elif verdict == "blocked_external":
        rank = 3
    elif verdict == "fixed_pending_qa":
        rank = 4
    else:
        rank = 5
    return (rank, tid)


def render_tasks_markdown(data: dict[str, Any]) -> str:
    """渲染按紧急度置顶的紧凑总表，每次覆盖写入，绝不无限追加。"""
    project = data.get("project", "project")
    items: list[dict[str, Any]] = sorted(data.get("items", []), key=_item_sort_key)

    n_fixing = sum(1 for it in items if it.get("status") == "fixing")
    n_need_fix = sum(1 for it in items if it.get("status") == "open" and it.get("verdict") == "need_fix")
    n_pending = sum(1 for it in items if it.get("status") == "open" and it.get("verdict") == "pending")
    n_retest = sum(1 for it in items if it.get("status") == "open" and it.get("verdict") == "fixed_pending_qa")
    n_closed = sum(1 for it in items if it.get("status") in ("done", "skipped"))

    lines = [
        f"# {project} 任务总板（自动生成，按紧急度置顶）",
        "",
        (
            f"> 更新时间：{_now_str()} | 共 {len(items)} 条"
            f"（正在修 {n_fixing} / 需改代码 {n_need_fix} / 待查 {n_pending} / 待复测 {n_retest} / 已完成或跳过 {n_closed}）"
        ),
    ]

    need_fix_items = [
        it for it in items if (it.get("verdict") == "need_fix" or it.get("status") == "fixing") and it.get("status") not in ("done", "skipped")
    ]
    if need_fix_items:
        lines.extend(["", "## 优先处理（正在修 / 确认需改代码）"])
        for it in need_fix_items:
            lines.append(
                f"- **{it['id']}**（{it.get('status')}）：改动 `{', '.join(it.get('files') or [])}`；"
                f"验收 `{it.get('verify', '')}`"
            )

    lines.extend(
        [
            "",
            "| 编号 | 类型 | 状态 | 定性 | 涉及文件 | 摘要 / 结论 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for it in items:
        tid = it.get("id", "")
        kind = it.get("kind", "other")
        status = it.get("status", "open")
        verdict = VERDICT_LABELS.get(it.get("verdict", "pending"), it.get("verdict", ""))
        files = ", ".join(it.get("files") or []) or "-"
        summary = (it.get("fact") or it.get("title") or "").replace("\n", " ").replace("|", "/")
        if len(summary) > 90:
            summary = summary[:87] + "..."
        lines.append(f"| `{tid}` | {kind} | {status} | {verdict} | {files} | {summary} |")

    lines.append("")
    return "\n".join(lines)


def save_tasks(root: Path, data: dict[str, Any]) -> Path:
    jp = tasks_json_path(root)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tasks_md_path(root).write_text(render_tasks_markdown(data), encoding="utf-8")
    return jp


def add_task(
    root: Path,
    task_id: str,
    title: str,
    *,
    kind: str = "bug",
) -> dict[str, Any]:
    task_id = task_id.strip()
    title = title.strip()
    if not task_id:
        raise TaskValidationError("任务编号不能为空")
    if not title:
        raise TaskValidationError("任务标题不能为空")
    if kind not in VALID_KINDS:
        raise TaskValidationError(f"非法 kind={kind}，可选: {', '.join(VALID_KINDS)}")

    data = load_tasks(root)
    existing = _find_item(data, task_id)
    now = _now_str()
    if existing is not None:
        existing["title"] = title
        existing["kind"] = kind
        existing["updated_at"] = now
        save_tasks(root, data)
        return existing

    item: dict[str, Any] = {
        "id": task_id,
        "title": title,
        "kind": kind,
        "status": "open",
        "verdict": "pending",
        "fact": "",
        "files": [],
        "verify": "",
        "note": "",
        "owner": "main",
        "updated_at": now,
    }
    data["items"].append(item)
    save_tasks(root, data)
    return item


def update_task(
    root: Path,
    task_id: str,
    *,
    title: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    verdict: str | None = None,
    fact: str | None = None,
    files: list[str] | str | None = None,
    verify: str | None = None,
    note: str | None = None,
    owner: str | None = None,
    force_collision: bool = False,
) -> dict[str, Any]:
    data = load_tasks(root)
    item = _find_item(data, task_id)
    if item is None:
        if not title:
            title = task_id
        item = {
            "id": task_id.strip(),
            "title": title.strip(),
            "kind": kind if kind in VALID_KINDS else "bug",
            "status": "open",
            "verdict": "pending",
            "fact": "",
            "files": [],
            "verify": "",
            "note": "",
            "owner": "main",
            "updated_at": _now_str(),
        }
        data["items"].append(item)

    new_kind = kind if kind is not None else item["kind"]
    new_status = status if status is not None else item["status"]
    new_verdict = verdict if verdict is not None else item["verdict"]
    new_fact = fact.strip() if fact is not None else item["fact"]
    new_files = _normalize_files(files) if files is not None else list(item.get("files") or [])
    new_verify = verify.strip() if verify is not None else item["verify"]
    new_note = note.strip() if note is not None else item["note"]
    new_owner = owner.strip() if owner is not None else item["owner"]

    if new_kind not in VALID_KINDS:
        raise TaskValidationError(f"非法 kind={new_kind}，可选: {', '.join(VALID_KINDS)}")
    if new_status not in VALID_STATUSES:
        raise TaskValidationError(f"非法 status={new_status}，可选: {', '.join(VALID_STATUSES)}")
    if new_verdict not in VALID_VERDICTS:
        raise TaskValidationError(f"非法 verdict={new_verdict}，可选: {', '.join(VALID_VERDICTS)}")

    # 长度防膨胀硬卡
    if len(new_fact) > MAX_FACT_CHARS:
        raise TaskValidationError(
            f"--fact 过长（{len(new_fact)} 字 > 上限 {MAX_FACT_CHARS} 字），请精简为精确的文件:行号与核心证据"
        )
    if len(new_note) > MAX_NOTE_CHARS:
        raise TaskValidationError(
            f"--note 过长（{len(new_note)} 字 > 上限 {MAX_NOTE_CHARS} 字），请保持一句话"
        )

    # 核心定性硬校验
    if new_verdict == "need_fix":
        missing: list[str] = []
        if not new_files:
            missing.append("--files（必须明确改动文件范围，防并行子 Agent 撞车）")
        if not new_verify:
            missing.append("--verify（必须写清验收命令或可观测通过标准）")
        if not new_fact:
            missing.append("--fact（必须写清已核实的根因证据与文件:行号）")
        if missing:
            raise TaskValidationError("verdict=need_fix 校验未通过，缺少: " + "；".join(missing))

    if new_verdict == "fixed_pending_qa" and not new_fact:
        raise TaskValidationError(
            "verdict=fixed_pending_qa 必须通过 --fact 写明当前代码中确认仍在生效的修复位置（文件:行号）"
        )

    if new_verdict == "blocked_external" and not new_note:
        raise TaskValidationError(
            "verdict=blocked_external 必须通过 --note 写明具体缺哪项本机无法自测的外部条件（如 QA 原图/原日志/真机复现）"
        )

    # 并行改代码文件碰撞检查
    if not force_collision:
        conflicts = _check_file_collisions(data, task_id, new_files, new_status)
        if conflicts:
            desc = ", ".join(f"{oid} 已占用 {fp}" for oid, fp in conflicts)
            raise TaskValidationError(
                f"并行文件冲突（禁止两个子 Agent 同时改同一文件）：{desc}。请串行处理或等对方完成后再派发。"
            )

    if title is not None:
        item["title"] = title.strip()
    item["kind"] = new_kind
    item["status"] = new_status
    item["verdict"] = new_verdict
    item["fact"] = new_fact
    item["files"] = new_files
    item["verify"] = new_verify
    item["note"] = new_note
    item["owner"] = new_owner
    item["updated_at"] = _now_str()

    save_tasks(root, data)
    return item


def build_subagent_brief(root: Path, task_id: str, *, mode: str = "auto") -> str:
    """生成可直接交给干净子 Agent 的精简任务包（避免传整段主对话历史）。"""
    data = load_tasks(root)
    item = _find_item(data, task_id)
    if item is None:
        raise TaskValidationError(f"找不到任务 {task_id}")

    actual_mode = mode
    if actual_mode == "auto":
        actual_mode = "fix" if item.get("verdict") == "need_fix" else "investigate"

    kind = item.get("kind", "bug")
    if actual_mode == "fix":
        skill_hint = "bug-fix-verify + existing-flow-review" if kind != "ui" else "bug-fix-verify + web-prototype-to-unity / existing-flow-review"
        files_str = ", ".join(item.get("files") or []) or "<未指定>"
        return "\n".join(
            [
                f"任务：修复 [{item['id']}] {item['title']}",
                f"- 遵循技能：`{skill_hint}`，先读项目 `AGENTS.md` 及已确认取舍/决策清单（不翻旧案、优先复用原流程）",
                f"- 已核实根因与证据：{item.get('fact') or '<见主任务说明>'}",
                f"- 改动文件边界（严禁越界修改范围外文件，防并行撞车）：{files_str}",
                "- 改动预算硬闸门：运行代码 ≤3 文件、净增 ≤80 行、不新增状态变量/缓存/锁、减法优先；超限或需改核心枢纽文件公共状态机必须先停下回传 5 行方向卡请示。",
                f"- 验收标准（先红后绿）：{item.get('verify') or '<必须跑最小回归验证>'}；改完必须自跑 `python -m harness diff-guard`。",
                "- 回执格式（控制在 8 行内）：改了哪几处（文件:行号）+ diff-guard 结果 / 修前红 vs 修后绿证据 / 是否存在未验证项。",
            ]
        )

    skill_hint = "bug-investigation" if kind == "bug" else "existing-flow-review"
    return "\n".join(
        [
            f"任务：独立只读核查 [{item['id']}] {item['title']}",
            f"- 遵循技能：`{skill_hint}`，先读项目 `AGENTS.md` 及已确认取舍/决策清单（已拍板取舍直接过滤，不按 P0 过度报警）",
            "- 纪律：不改业务代码；看到截图/文案/报错必须追进当前代码/Prefab 核实真实实现，禁止只挑历史证据毛病用“待验证”交差；本机能查能跑的自己先验完。",
            "- 开口前 3 问自检：为何正常流程没挂（触发前提与线上概率）/ 改造前旧版是不是也这样 / 项目决策清单是否已接受。",
            "- 回执格式（控制在 10 行内，方便主总控直接录入 `python -m harness task update`）：",
            "  1. 定性：`need_fix`（当前代码可见缺陷） / `fixed_pending_qa`（修复逻辑仍在当前代码，待新包/QA复测） / `no_fix`（设计如此/无需改） / `blocked_external`（真缺图/界面线索，打回 QA）",
            "  2. 事实：精确 `文件:行号` 与当前代码核查结论（≤300字）",
            "  3. 若为 `need_fix`：明确给出 `--files`（只动哪些文件）和 `--verify`（验收命令/现象）",
            "  4. 若为 `blocked_external`：写清具体缺哪项外部线索",
        ]
    )


def clear_tasks(root: Path, *, only_done: bool = True) -> int:
    data = load_tasks(root)
    before = len(data["items"])
    if only_done:
        data["items"] = [it for it in data["items"] if it.get("status") not in ("done", "skipped")]
    else:
        data["items"] = []
    removed = before - len(data["items"])
    save_tasks(root, data)
    return removed
