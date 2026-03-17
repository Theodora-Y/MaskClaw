---
name: skill-evolution-mechanic
description: >
  分析用户对 Agent 的纠错行为日志，自动抽取个性化隐私规则，
  生成结构化 JSON 规则对象。
  当收到包含 correction 字段的日志并需要更新本地规则库时使用此技能。
  触发词: openclaw, 规则进化, correction, rag更新
---

# Skill Evolution Mechanic

## 何时使用
- behavior-monitor 日志中出现非空 correction。
- 需要将重复纠偏行为归纳为可存入规则库的候选规则。

## 工作流
- Step 1: 读取日志流并过滤 correction 为空记录。
- Step 2: 基于 action/correction 聚合频次。
- Step 3: 仅对频次达到阈值的模式生成候选规则。
- Step 4: 计算 confidence 并标注 needs_review。
- Step 5: 输出规则 JSON 列表（不直接写库）。

## 输入格式
- JSON 日志列表，字段见 references/rule_schema.md 与 monitor 输出契约。

## 输出格式
- JSON 对象，含 candidates 数组与统计信息。

## 边界情况
- 若无有效 correction，输出空 candidates。
- 输入文件缺失或格式错误，返回结构化错误信息并退出非零码。
