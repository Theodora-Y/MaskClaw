---
name: behavior-monitor
description: >
  监听 GUI Agent 执行过程中的 UI 事件与用户修正动作，
  归一化为结构化 JSON 日志流供规则进化模块消费。
  当需要追踪用户对 Agent 操作的接受/拒绝/修正行为时使用此技能。
  触发词: openclaw, 纠偏日志, 行为监听, correction
---

# Behavior Monitor Skill

## 何时使用
- proxy_agent 每次处理完一个操作请求后，调用本 Skill 记录日志。
- 不做隐私识别，不写 RAG，只做事件标准化与日志输出。

## 核心概念
- 单条记录契约：`{"timestamp": int, "action": str, "correction": str, "metadata": object}`。
- `correction` 用于标识纠偏行为，空字符串表示未发生纠偏。
- 记录格式说明见 `references/log_schema.md`。

## 工作流
- Step 1: 准备输入事件列表（JSON 数组），字段可包含 `timestamp/action/metadata`。
- Step 2: 执行 `scripts/monitor.py --input <path>` 或 `scripts/monitor.py --mock-input`。
- Step 3: 获得标准化输出 `records`，下游直接传给 skill-evolution-mechanic。

## 输入
- `--input <file>`: JSON 数组，单项为事件对象。
- `--mock-input`: 生成内置示例事件。
- `--output <file>`: 可选，将 JSON 结果写入文件。

## 输出
- 标准 JSON 对象：
  - `session_id`: 会话标识。
  - `record_count`: 记录数。
  - `records`: 标准化事件数组。
  - `summary.correction_count`: 非空 correction 数量。

## 边界情况
- 输入为空时返回 `record_count=0`，不报错。
- 输入文件不存在、JSON 非法或结构错误时，输出结构化错误并退出非零码。