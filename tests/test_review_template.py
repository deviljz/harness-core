"""验证 Pass A review 模板包含必要的工作树核对约束"""
from __future__ import annotations

from harness.review.runner import _load_template


class TestReviewTemplateConstraints:
    def setup_method(self):
        self.template = _load_template()

    def test_contains_worktree_truth_statement(self):
        assert "工作树状态是真相" in self.template

    def test_contains_git_ls_files_instruction(self):
        assert "git ls-files" in self.template

    def test_contains_strict_check_section(self):
        assert "严格核对步骤" in self.template

    def test_diff_truncation_warning_present(self):
        assert "diff 截断" in self.template

    def test_allowed_tools_listed(self):
        assert "Bash" in self.template
        assert "Read" in self.template

    def test_original_task_section_preserved(self):
        """确保原有 Your Task 段落未被破坏"""
        assert "## Your Task" in self.template
        assert "Implements what the spec says" in self.template

    def test_original_focus_placeholder_preserved(self):
        assert "{focus}" in self.template

    def test_original_spec_placeholder_preserved(self):
        assert "{spec_content}" in self.template

    def test_original_diff_placeholder_preserved(self):
        assert "{diff_content}" in self.template

    # ─── 0.3.1 新增：User Flow trace 强制段 ─────────────────────────────

    def test_user_flow_trace_section_present(self):
        """spec User Flow 段非 N/A 时必须逐条 trace"""
        assert "User Flow 步骤逐条 trace" in self.template

    def test_anti_skip_phrases_listed(self):
        """偷工措辞硬禁清单（push-back 触发条件）"""
        assert "先跳过 UI 入口" in self.template
        assert "留 service API 可调" in self.template

    def test_manual_e2e_audit_requirement(self):
        """spec Testing 段要求手工 E2E 时，diff 无实测痕迹应报 issue"""
        assert "手工 E2E 验收" in self.template
        assert "reports/" in self.template

    def test_integration_test_requirement(self):
        """spec 要求集成测试但只有 mock 单测时应报 issue"""
        assert "只有 mock 单测" in self.template


class TestHarnessFullSkillPushback:
    """harness-full skill 文档应含偷工 push-back 模式"""

    def setup_method(self):
        import pathlib
        path = (
            pathlib.Path(__file__).parent.parent
            / "harness/adapters/claude_code/commands/harness-full.md"
        )
        self.skill_text = path.read_text(encoding="utf-8")

    def test_pushback_section_exists(self):
        assert "偷工模式 push-back" in self.skill_text

    def test_pushback_keywords_listed(self):
        assert "先跳过 UI 入口" in self.skill_text
        assert "留 service API 可调" in self.skill_text

    def test_pushback_prompt_template_exists(self):
        assert "请补做" in self.skill_text
