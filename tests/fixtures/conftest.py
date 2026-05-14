# This conftest.py prevents pytest from collecting test files inside fixture
# worktree directories (they are fixture data, not real test files).
collect_ignore_glob = ["**/worktree/**"]
