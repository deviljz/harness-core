"""允许在任意机器上通过 `python -m harness ...` 调用 CLI（不依赖 Scripts 加入 PATH）。"""
from .cli import main

if __name__ == "__main__":
    main()
