"""语言模块注册表。

核心层通过 `get_language_module(name)` 拿到语言模块实例，
不直接 import 具体语言。新增语言在下面注册即可。
"""
from __future__ import annotations

from .base import LanguageModule
from .fallback import FallbackModule

_REGISTRY: dict[str, type[LanguageModule]] = {
    "fallback": FallbackModule,
}


def register_language(name: str, cls: type[LanguageModule]) -> None:
    """动态注册语言模块（阶段 2/3 会调）"""
    _REGISTRY[name] = cls


def get_language_module(name: str) -> LanguageModule:
    """按 name 拿模块实例。不存在时返回 fallback。"""
    cls = _REGISTRY.get(name, FallbackModule)
    return cls()


def list_languages() -> list[str]:
    return sorted(_REGISTRY.keys())


# 延迟 import，避免 python 模块依赖还没装好时 fallback 也失败
def _register_python():
    try:
        from .python import PythonModule
        register_language("python", PythonModule)
    except ImportError:
        pass


def _register_dart():
    try:
        from .dart import DartModule
        register_language("dart", DartModule)
    except ImportError:
        pass


_register_python()
_register_dart()
