# Regression 001: 设置页检查更新入口缺失

## 背景

v1.2 需求要求用户可以在设置页手动触发"检查更新"（User Flow 第 1-2 步）。
实现时 subagent 报告称"先跳过 UI 入口，留 service API 可调"，被 harness review 误判为 consistent=true。

## 预期行为

review 应检测到 settings_screen.dart 缺失，User Flow 无法完成，判定 consistent=false。

## 为何重要

这是 User Flow trace 失败的典型案例：service 层存在但 UI 入口缺失，功能对用户不可见。
