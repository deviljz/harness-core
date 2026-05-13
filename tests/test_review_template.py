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
