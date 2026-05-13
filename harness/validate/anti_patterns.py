"""反模式正则扫描。

按文件扩展名映射到语言，跑 config 里 anti_patterns.<lang> 下的规则。
"all" 段的规则对所有扩展名都跑。

设计：
- 纯正则，跨语言通用，不需要 AST
- 单条规则失败（正则非法）→ 跳过 + warn 日志，不影响其他规则
- 单个文件读取失败 → 静默跳过（PNG / 二进制等）
"""
from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..config import AntiPatternRule, HarnessConfig
from ..reporter import CheckResult

logger = logging.getLogger(__name__)


# 扩展名 → 语言段名（必须与 config.yaml 的 anti_patterns key 一致）
EXT_TO_LANG: dict[str, str] = {
    ".dart": "dart",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
}


@dataclass(frozen=True)
class AntiPatternFinding:
    file: str
    line: int
    rule: str
    msg: str
    severity: str  # "error" | "warn"


def scan_file(file_path: Path, rules: list[AntiPatternRule], project_root: Path) -> list[AntiPatternFinding]:
    """扫描单个文件。"""
    if not file_path.is_file():
        return []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    rel = _relative(file_path, project_root)
    findings: list[AntiPatternFinding] = []
    for rule in rules:
        flags = re.MULTILINE
        if rule.multiline:
            flags |= re.DOTALL
        try:
            for m in re.finditer(rule.pattern, content, flags):
                line_no = content[: m.start()].count("\n") + 1
                findings.append(
                    AntiPatternFinding(
                        file=rel,
                        line=line_no,
                        rule=rule.name,
                        msg=rule.msg or rule.name,
                        severity=rule.severity,
                    )
                )
        except re.error as e:
            logger.warning("[anti_patterns] bad regex in rule %s: %s", rule.name, e)
    return findings


def _relative(p: Path, project_root: Path) -> str:
    try:
        return p.resolve().relative_to(project_root.resolve()).as_posix()
    except Exception:
        return p.as_posix()


def _is_ignored(rel_posix: str, ignore_patterns: list[str]) -> bool:
    """检查相对路径（posix）是否匹配任意 ignore glob 模式。"""
    for pat in ignore_patterns:
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        # 支持 "scripts/**" 形式：也匹配 "scripts/foo.py"
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
                return True
    return False


def _rules_for_file(file_path: Path, anti_patterns: dict[str, list[AntiPatternRule]]) -> list[AntiPatternRule]:
    ext = file_path.suffix.lower()
    lang = EXT_TO_LANG.get(ext)
    rules: list[AntiPatternRule] = []
    if lang and lang in anti_patterns:
        rules.extend(anti_patterns[lang])
    rules.extend(anti_patterns.get("all", []))
    return rules


def _iter_tracked_files(project_root: Path) -> Iterable[Path]:
    """全量扫描时迭代 git tracked 文件。无 git 时 fallback 到 rglob。"""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        for line in out.stdout.splitlines():
            p = project_root / line.strip()
            if p.suffix.lower() in EXT_TO_LANG and p.exists():
                yield p
    except Exception:
        for ext in EXT_TO_LANG:
            for p in project_root.rglob(f"*{ext}"):
                if any(part in {".git", "node_modules", ".dart_tool", "build", "dist", "vendor"} for part in p.parts):
                    continue
                yield p


def run_anti_patterns(
    config: HarnessConfig,
    project_root: Path,
    changed_file: str | None,
) -> CheckResult:
    """跑反模式检查。返回单个 CheckResult。

    changed_file 指定 → 只扫该文件
    changed_file None → 全量扫所有 tracked 源文件
    """
    if not config.anti_patterns:
        return CheckResult(
            check_name="anti_patterns",
            target="global",
            status="skip",
            message="no anti_patterns configured",
        )

    ignore = config.ignore_paths_global  # list[str]，缺省为 []

    findings: list[AntiPatternFinding] = []
    if changed_file:
        p = Path(changed_file)
        if not p.is_absolute():
            p = (project_root / changed_file).resolve()
        rel = _relative(p, project_root)
        if not _is_ignored(rel, ignore):
            rules = _rules_for_file(p, config.anti_patterns)
            if rules and p.exists():
                findings.extend(scan_file(p, rules, project_root))
    else:
        for p in _iter_tracked_files(project_root):
            rel = _relative(p, project_root)
            if _is_ignored(rel, ignore):
                continue
            rules = _rules_for_file(p, config.anti_patterns)
            if rules:
                findings.extend(scan_file(p, rules, project_root))

    errors = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity == "warn"]

    if errors:
        status = "fail"
    elif warns:
        status = "warn"
    else:
        status = "pass"

    return CheckResult(
        check_name="anti_patterns",
        target="global",
        status=status,
        message=f"{len(errors)} error(s), {len(warns)} warn(s)",
        details={
            "findings": [
                {
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "rule": f.rule,
                    "msg": f.msg,
                }
                for f in findings[:50]
            ],
            "total": len(findings),
        },
    )
