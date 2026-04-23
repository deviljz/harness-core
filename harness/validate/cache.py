"""增量检查缓存：30s 去抖 + 文件 hash 跳过

存在 .harness/check_cache.json 里。内容 hash 变了才重新跑。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class IncrementalCache:
    def __init__(self, cache_file: Path, debounce_seconds: int = 30):
        self.cache_file = cache_file
        self.debounce_seconds = debounce_seconds
        self.data = self._load()

    def _load(self) -> dict:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {}

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def should_skip(self, file_path: Path) -> tuple[bool, str]:
        """返回 (skip?, reason)"""
        if not file_path.exists():
            return False, "file missing"
        try:
            content = file_path.read_bytes()
        except OSError as e:
            return False, f"read error: {e}"

        content_hash = hashlib.sha256(content).hexdigest()[:16]
        key = str(file_path).replace("\\", "/")
        entry = self.data.get(key)

        if entry:
            if entry.get("hash") == content_hash:
                age = time.time() - entry.get("checked_at", 0)
                if age < self.debounce_seconds:
                    return True, f"debounced (last check {int(age)}s ago, hash unchanged)"
                # 超时但 hash 没变，仍然可以认为"不用重跑"（内容真没改）
                return True, "hash unchanged"
        return False, "new or changed"

    def record(self, file_path: Path) -> None:
        if not file_path.exists():
            return
        try:
            content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
        except OSError:
            return
        key = str(file_path).replace("\\", "/")
        self.data[key] = {
            "hash": content_hash,
            "checked_at": time.time(),
        }
        self._save()

    def clear(self) -> None:
        self.data = {}
        self._save()
