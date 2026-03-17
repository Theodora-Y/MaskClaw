---
name: behavior-monitor
description: >
  监听 GUI Agent 执行过程中的 UI 事件与用户修正动作，
  将行为记录为结构化 JSON 日志流。
  当需要追踪用户对 Agent 操作的接受/拒绝/修正行为时使用此技能。
  触发词: openclaw, 纠偏日志, 行为监听, correction
---

# Behavior Monitor Skill

## 何时使用
- Agent 正在执行连续操作，且需要记录用户是否接受或修正。
- 需要输出可供规则进化模块消费的标准化日志。

## 工作流
- Step 1: 初始化会话并生成 session_id。
- Step 2: 运行 scripts/monitor.py 采集或加载事件。
- Step 3: 归一化事件为 timestamp/action/correction 结构。
- Step 4: 输出 JSON 日志流供下游使用。

## 输入格式
- 默认无输入，使用 --mock-input 生成示例事件。
- 或通过 --input 传入 JSON 事件文件。

## 输出格式
- JSON 对象，含 session_id、records、summary。
- records 中每条记录格式见 references/log_schema.md。

## 边界情况
- 无有效事件时输出空 records，不报错退出。
- 非法输入 JSON 返回结构化错误信息并退出非零码。
