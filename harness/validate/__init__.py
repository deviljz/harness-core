"""验证层：跑检查 + 交付闸 + 断路器 + 增量缓存"""
from __future__ import annotations

from .gate import evaluate_gate, GateResult
from .runner import run_checks
from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .cache import IncrementalCache

__all__ = [
    "run_checks",
    "evaluate_gate",
    "GateResult",
    "CircuitBreaker",
    "CircuitBreakerState",
    "IncrementalCache",
]
