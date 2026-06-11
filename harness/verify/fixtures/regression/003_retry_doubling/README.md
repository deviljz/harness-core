# Regression 003: 选图打卡失败重试导致缩略图翻倍 (1→2→4)

## 背景

2026-06 选图打卡乐观渲染需求：上传失败时缩略图标红，点红角标重试。
实现 `_retryFailed` 调 `resetFailed(key)`（只清红、项仍在列表），再调 `_uploadPaths`，
而 `_uploadPaths` 开头又 `addPaths(key, paths)` 把同样路径重新入列一份 → 每重试一轮翻倍。
单测只覆盖了 `PendingUploads` 各方法的单元行为，没测 `_retryFailed→_uploadPaths` 的编排，
review 未发现，合并后家里在生产暴露 (commit 9d9ed50 修复)。

## 预期行为

review 应 trace 失败重试 User Flow，发现重试路径会重复 `addPaths`（状态累积），
且测试未覆盖"连续重试断言数量不累积"，判定 consistent=false。

## 为何重要

重试/失败恢复类的"状态累积"盲区：单次重试看不出（被 clearSucceeded 掩盖），
必须连续 N 轮才暴露。review 必须对重试路径做状态累积检查，而非只看单元测试是否绿。
