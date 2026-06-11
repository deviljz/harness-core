"""validator §6 盲区条件 warn：状态累积 / 异步慢依赖中间态.

来源：2026-06 选图打卡两个真实事故，spec 没写对应 Testing 要求 → review 没标尺 → 漏检。
- 重试翻倍(1→2→4)：spec 涉及"失败重试"但没要求"连续 N 轮断言状态不累积"
- 100%空窗：spec 涉及"上传进度/乐观渲染"但没要求"注入慢依赖断言中间态"
validate 应在触发词出现而 Testing 缺对应守卫时 warn（默认 warning，非 error）。
"""

from pathlib import Path

from harness.plan.validator import validate_spec


def _write(tmp_path, *, objective_extra="", testing_extra="") -> Path:
    spec = f"""# 测试 spec

**complexity**: complex

## 1. Objective
做什么：实现某功能 {objective_extra}
成功标准（可验证）：
1. 能用

## 2. User Flow
1. 用户点按钮 → 看到结果

## 3. Commands
- POST /api/x

## 4. Structure
- lib/x.dart

## 5. Style
- 现有风格

## 6. Testing
交互性测试：await tester.tap(find.byIcon(Icons.add))；时序竞态：上传中断言 _busy。
{testing_extra}

## 7. Boundaries
### 绝不做
- 不做 Y
### 必须做
- 做 X

## 8. Data Migration
N/A
"""
    p = tmp_path / "spec.md"
    p.write_text(spec, encoding="utf-8")
    return p


def _msgs(issues):
    return " || ".join(i.message for i in issues)


# ── 状态累积（重试/失败恢复）──

def test_retry_without_accumulation_guard_warns(tmp_path):
    p = _write(tmp_path, objective_extra="支持上传失败重试")
    issues = validate_spec(p)
    assert any("累积" in i.message and i.severity == "warning" for i in issues), _msgs(issues)


def test_retry_with_accumulation_guard_ok(tmp_path):
    p = _write(tmp_path, objective_extra="支持上传失败重试",
               testing_extra="编排测试：失败→重试→再失败→再重试，连续 N 轮断言同一项不累积。")
    issues = validate_spec(p)
    assert not any("累积" in i.message for i in issues), _msgs(issues)


# ── 异步慢依赖中间态（上传进度/乐观渲染）──

def test_progress_without_slow_dependency_warns(tmp_path):
    p = _write(tmp_path, objective_extra="选图后显示本地缩略图与上传进度（乐观渲染）")
    issues = validate_spec(p)
    assert any("慢依赖" in i.message and i.severity == "warning" for i in issues), _msgs(issues)


def test_progress_with_slow_dependency_ok(tmp_path):
    p = _write(tmp_path, objective_extra="选图后显示上传进度（乐观渲染）",
               testing_extra="注入慢依赖 fake service（延迟 resolve），断言 100% 后显示处理中态。")
    issues = validate_spec(p)
    assert not any("慢依赖" in i.message for i in issues), _msgs(issues)


# ── 不相关 spec 不应误报 ──

def test_unrelated_spec_no_blindspot_warn(tmp_path):
    p = _write(tmp_path, objective_extra="一个纯静态文案展示页")
    issues = validate_spec(p)
    assert not any("累积" in i.message or "慢依赖" in i.message for i in issues), _msgs(issues)
