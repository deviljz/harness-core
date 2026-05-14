"""Root conftest.py — prevents pytest from collecting test files inside
fixture worktree directories (they are fixture data, not real tests).
"""
collect_ignore_glob = [
    "tests/fixtures/*/worktree/**",
    "tests/fixtures/regression/*/worktree/**",
    "tests/fixtures/template_project/*/worktree/**",
]
