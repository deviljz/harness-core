"""Unity batchmode test runner + NUnit3 XML 解析。

跑命令：
    Unity.exe -batchmode -projectPath <root> -runTests -testPlatform EditMode
              -testResults <xml> -logFile <log> -quit [-testFilter <regex>]

实测坑（详见 docs/unity_batchmode_baseline.md）：
- Editor 开着 + 同 projectPath → exit 21 + crash dump，必须 pre-flight 拦截
- 完整测试 30-60s 冷启动 + 编译，timeout 默认 300s
- TestResults.xml 是 NUnit3 v3.x schema
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from ..base import TestResult, TestRunResult


class UnityEditorLockedError(RuntimeError):
    """Editor 占着同 projectPath，batchmode 跑不了。"""


# ─────────────────────────────────────────────────
# pre-flight: Editor 锁检测
# ─────────────────────────────────────────────────

def _is_unity_editor_holding(project_path: Path) -> tuple[bool, str | None]:
    """psutil 扫 Unity.exe 进程，看 cmdline 是否含 -projectPath <project_path>。
    返回 (是否锁住, 锁住的进程 pid str)。psutil 没装时返回 (False, None) 让 batchmode 自己抛 exit 21。
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        return False, None
    target = str(project_path.resolve()).replace("\\", "/").lower()
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if not name.startswith("unity"):
                continue
            # 跳过 Unity Hub / Licensing client
            if "hub" in name or "licensing" in name:
                continue
            cmdline = proc.info.get("cmdline") or []
            cmd_joined = " ".join(cmdline).replace("\\", "/").lower()
            # 匹配 -projectPath <root> 或 工程目录被作为参数传
            if target in cmd_joined:
                return True, str(proc.info.get("pid"))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False, None


# ─────────────────────────────────────────────────
# Unity.exe 路径解析
# ─────────────────────────────────────────────────

def _resolve_unity_exe(target_config: dict, project_root: Path) -> str:
    """优先级：
    1. target_config["unity_exe"] 显式指定
    2. project_root/ProjectSettings/ProjectVersion.txt 找 m_EditorVersion → Hub 默认装路径
    3. PATH 上的 Unity（少见）
    """
    explicit = target_config.get("unity_exe")
    if explicit:
        return explicit

    pv = project_root / "ProjectSettings" / "ProjectVersion.txt"
    if pv.exists():
        try:
            for line in pv.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"m_EditorVersion:\s*(\S+)", line)
                if m:
                    version = m.group(1)
                    candidates = [
                        rf"C:\Program Files\Unity\Hub\Editor\{version}\Editor\Unity.exe",
                        rf"/Applications/Unity/Hub/Editor/{version}/Unity.app/Contents/MacOS/Unity",
                    ]
                    for c in candidates:
                        if Path(c).exists():
                            return c
        except OSError:
            pass

    # fallback: PATH 上的 Unity
    return "Unity.exe"


# ─────────────────────────────────────────────────
# run_unity_tests
# ─────────────────────────────────────────────────

def run_unity_tests(
    test_files: list[str],
    target_config: dict,
    project_root: Path,
) -> TestRunResult:
    """跑 Unity batchmode EditMode 测试。

    target_config 可选字段：
    - unity_exe: 显式 Unity.exe 路径（不传则从 ProjectVersion.txt 推）
    - test_platform: "EditMode" | "PlayMode"（默认 EditMode，快 10x）
    - test_filter: 显式 regex 覆盖 test_files 推导
    - timeout: 秒，默认 300
    """
    unity_exe = _resolve_unity_exe(target_config, project_root)
    test_platform = target_config.get("test_platform", "EditMode")
    timeout = int(target_config.get("timeout", 300))

    # pre-flight: Editor 锁
    locked, pid = _is_unity_editor_holding(project_root)
    if locked:
        msg = (
            f"Unity Editor (pid={pid}) 正在用 projectPath={project_root}，batchmode 跑不了。\n"
            f"  原因：同 projectPath 会触发 'Project already open' abort（exit 21 + crash dump）。\n"
            f"  解决：关掉 Editor 或用 -projectPath 指向工程副本后重试。"
        )
        raise UnityEditorLockedError(msg)

    # 跑前删上次 results XML 避免 stale 读取
    results_xml = project_root / "Library" / "HarnessUnityTestResults.xml"
    log_file = project_root / "Library" / "HarnessUnityTestRun.log"
    for p in (results_xml, log_file):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass
    results_xml.parent.mkdir(parents=True, exist_ok=True)

    # 拼 -testFilter（从 test_files 推：FooTests.cs → FooTests）
    explicit_filter = target_config.get("test_filter")
    if explicit_filter:
        test_filter = explicit_filter
    elif test_files:
        names = [Path(f).stem for f in test_files]
        test_filter = "|".join(names) if names else ""
    else:
        test_filter = ""

    cmd = [
        unity_exe,
        "-batchmode",
        "-projectPath", str(project_root),
        "-runTests",
        "-testPlatform", test_platform,
        "-testResults", str(results_xml),
        "-logFile", str(log_file),
        "-quit",
    ]
    if test_filter:
        cmd += ["-testFilter", test_filter]

    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        # 实际输出基本都在 -logFile 里，stdout 通常空
        log_text = ""
        if log_file.exists():
            try:
                log_text = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        # 把 results_xml 路径塞进 stdout 让 parse 阶段能拿到
        stdout = (result.stdout or "") + f"\n__HARNESS_UNITY_RESULTS_XML__={results_xml}\n"
        return TestRunResult(
            cmd=cmd_str,
            cwd=str(project_root),
            exit_code=result.returncode,
            stdout=stdout,
            stderr=(result.stderr or "") + "\n" + log_text[-4000:],  # log 尾部 4KB 够诊断
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return TestRunResult(
            cmd=cmd_str,
            cwd=str(project_root),
            exit_code=124,
            stdout=e.stdout.decode(errors="replace") if e.stdout else "",
            stderr=(e.stderr.decode(errors="replace") if e.stderr else "")
                   + f"\n[harness] Unity batchmode 超时 {timeout}s",
            duration_ms=duration_ms,
        )


# ─────────────────────────────────────────────────
# parse_nunit3_xml
# ─────────────────────────────────────────────────

_UNITY_EXIT_HINTS = {
    0: "all tests passed",
    2: "some tests failed (但命令本身成功)",
    3: "general error",
    12: "compile error",
    21: "license error / project locked",
    124: "harness timeout",
}


def parse_nunit3_xml(raw: TestRunResult) -> TestResult:
    """从 stdout 找 __HARNESS_UNITY_RESULTS_XML__= 路径，解析 NUnit3 XML。
    XML 不存在时 fallback 看 exit_code：
    - 0 → 假装 1 passed
    - 非 0 → 1 failed
    """
    # 提 results_xml 路径
    m = re.search(r"__HARNESS_UNITY_RESULTS_XML__=([^\r\n]+)", raw.stdout or "")
    if m:
        xml_path = Path(m.group(1).strip())
    else:
        return _fallback_result(raw)

    if not xml_path.exists():
        return _fallback_result(raw, note=f"results xml 未生成: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()  # <test-run>
    except ET.ParseError as e:
        return _fallback_result(raw, note=f"XML 解析失败: {e}")

    # <test-run total="N" passed="N" failed="N" skipped="N" inconclusive="N">
    def _attr_int(key: str) -> int:
        try:
            return int(root.attrib.get(key, "0") or "0")
        except ValueError:
            return 0

    passed = _attr_int("passed")
    failed = _attr_int("failed")
    skipped = _attr_int("skipped") + _attr_int("inconclusive")
    total = _attr_int("total")
    # NUnit 老版本不写 total，回退到求和
    if total == 0:
        total = passed + failed + skipped

    failures: list[dict] = []
    # 遍历所有 <test-case result="Failed">
    for tc in root.iter("test-case"):
        if tc.attrib.get("result") != "Failed":
            continue
        fullname = tc.attrib.get("fullname") or tc.attrib.get("name") or "(unknown test)"
        fail_el = tc.find("failure")
        msg = ""
        stack = ""
        if fail_el is not None:
            m_el = fail_el.find("message")
            s_el = fail_el.find("stack-trace")
            if m_el is not None and m_el.text:
                msg = m_el.text.strip()
            if s_el is not None and s_el.text:
                stack = s_el.text.strip()
        # 从 stack 提 file:line（Unity stack 格式：at Foo.Bar () [0x00000] in <hash>:0）
        file_hint, line_hint = _extract_file_line(stack)
        failures.append({
            "file": file_hint or "(unknown)",
            "test": fullname,
            "message": msg or "(no message)",
            "traceback": stack[:2000] if stack else "",
            "line": line_hint,
        })

    return TestResult(
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=0,
        failures=failures,
        raw_output=raw.stdout or "",
    )


def _extract_file_line(stack: str) -> tuple[str | None, int | None]:
    """从 C# stack trace 行提 file:line。Unity 常见格式：
        at Namespace.Class.Method () [0x00000] in <hash>:0
        at Namespace.Class.Method () [0x00000] in /path/to/File.cs:42
    """
    if not stack:
        return None, None
    # 允许 Windows 盘符（D:/...）和 Unix 绝对路径（/foo/...）
    # 非贪婪匹配 .cs 之前所有字符（包括冒号）
    for line in stack.splitlines():
        m = re.search(r"\bin\s+(.+?\.cs):(\d+)", line)
        if m:
            try:
                return m.group(1).replace("\\", "/"), int(m.group(2))
            except ValueError:
                return m.group(1).replace("\\", "/"), None
    return None, None


def _fallback_result(raw: TestRunResult, note: str = "") -> TestResult:
    """XML 不可用时按 exit code 估计"""
    hint = _UNITY_EXIT_HINTS.get(raw.exit_code, "")
    suffix = f" ({hint})" if hint else ""
    if note:
        suffix = f"{suffix} [{note}]"
    if raw.exit_code == 0:
        return TestResult(passed=1, raw_output=raw.stdout)
    return TestResult(
        failed=1,
        failures=[{
            "file": "(unity batchmode)",
            "test": raw.cmd,
            "message": f"exit code {raw.exit_code}{suffix}",
            "traceback": (raw.stderr or raw.stdout)[:2000],
            "line": None,
        }],
        raw_output=(raw.stdout or "") + "\n" + (raw.stderr or ""),
    )
