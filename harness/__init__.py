"""harness-core: AI 工程化 Harness 框架"""
# 从已安装包 metadata 读版本，避免硬编码漂移
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("harness-core")
except PackageNotFoundError:  # 源码直接 import 而未 pip install 时
    __version__ = "0.0.0+dev"
