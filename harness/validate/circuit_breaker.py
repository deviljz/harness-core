"""死循环断路器：防止 AI "改→挂→改回→挂" 烧 Token

状态持久化到 .harness/circuit_state.json。
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class CircuitBreakerState:
    retries: int = 0
    error_signatures: list[str] = field(default_factory=list)  # 最近 N 次错误签名
    last_triggered_at: float | None = None
    paused: bool = False
    pause_context: dict = field(default_factory=dict)


class CircuitBreaker:
    def __init__(
        self,
        state_file: Path,
        max_retries: int = 3,
        same_error_limit: int = 2,
    ):
        self.state_file = state_file
        self.max_retries = max_retries
        self.same_error_limit = same_error_limit
        self.state = self._load()

    def _load(self) -> CircuitBreakerState:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return CircuitBreakerState(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return CircuitBreakerState()

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")

    def reset(self) -> None:
        self.state = CircuitBreakerState()
        self._save()

    def record_failure(self, error_signature: str, context: dict | None = None) -> bool:
        """记录一次失败。返回 True 表示应该触发断路（调用方应暂停流程）。"""
        self.state.retries += 1
        self.state.error_signatures.append(error_signature)
        # 只保留最近 10 条
        self.state.error_signatures = self.state.error_signatures[-10:]

        should_trip = False
        if self.state.retries >= self.max_retries:
            should_trip = True
        # 同一 signature 连续 N 次
        if len(self.state.error_signatures) >= self.same_error_limit:
            recent = self.state.error_signatures[-self.same_error_limit:]
            if all(s == error_signature for s in recent):
                should_trip = True

        if should_trip:
            self.state.paused = True
            self.state.last_triggered_at = time.time()
            self.state.pause_context = context or {}
        self._save()
        return should_trip

    def record_success(self) -> None:
        """成功时重置计数"""
        self.reset()

    def is_paused(self) -> bool:
        return self.state.paused

    def resume(self) -> None:
        """外部手动恢复"""
        self.reset()


def error_signature(failure: dict) -> str:
    """从一个 failure dict 生成稳定签名"""
    return f"{failure.get('file', '?')}::{failure.get('test', '?')}::{failure.get('message', '?')[:80]}"
