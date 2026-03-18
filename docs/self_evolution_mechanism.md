# 日中记录读取之日总结规则 — 自进化机制设计

## 概述

本文档记录了隐私代理系统中**自进化机制**的架构设计与实现细节。该机制借鉴了 Anthropic 的 skill-creator 方法论，构建了一套类似软件工程流水线的自动化规则生成与验证系统。

---

## 一、核心概念：四阶段进化闭环

整个自进化机制由四个核心阶段组成，形成完整的生产级生命周期：

### 阶段 1：收集（Collect）— Behavior Monitor

**职责**：实时监听 GUI Agent 执行过程中的用户行为与纠错信号。

**关键特性**：
- **实时/同步**：嵌入 `proxy_agent.py` 或 `api_server.py` 的主干流
- **轻量级**：每次云端 Agent 返回动作或用户修正时立即捕获并记录
- **极度轻量**：绝不能阻塞用户当前的 GUI 操作

**输出**：
- `behavior_log.jsonl` — 所有操作的轻量记录
- `correction_log.jsonl` — 只有用户参与的完整记录（Evolution Mechanic 的原料）

**详细设计** 见 `skills/behavior-monitor/references/log_schema.md`

---

### 阶段 2：评估（Evaluate）— 规则置信度计算

**职责**：对收集的日志进行配对、分组与置信度评估。

**工作流**：
1. 读取 `logs/{user_id}/correction_log.jsonl`
2. 按 (user_id, action, app_context) 分组
3. 计算每组的 confidence（置信度）
4. 过滤掉 `confidence < 0.6` 的组（待观察）
5. 过滤掉分组数量 < N=2 的组（信号不足）

**详细设计** 见 `skills/skill-evolution-mechanic/references/confidence_policy.md`

---

### 阶段 3：生成（Generate）— 规则提炼

**职责**：调用端侧 MiniCPM-o 大模型，基于用户纠错日志提炼个性化隐私规则。

**工作流**：
1. 打包输入（Prompt 模板 + 日志数据）
2. POST 请求至 `http://127.0.0.1:8000/chat`
3. 解析模型输出，提取结构化规则 JSON
4. 解析失败时记录错误，跳过本组，不中断整体流程

**输出格式**：
```json
{
  "rule_id": "user_B_20260318_001",
  "user_id": "user_B",
  "scene": "非电商平台注册",
  "sensitive_field": "home_address",
  "strategy": "replace",
  "replacement": "公司地址",
  "rule_text": "在非电商平台注册时，用公司地址替代家庭住址",
  "confidence": 0.82,
  "trigger_count": 3,
  "created_ts": 1700000000
}
```

---

### 阶段 4：验证（Verify）— 沙盒回归测试

**职责**：确保新规则不与历史 Allow 记录冲突，防止策略坍塌。

**工作流**：
1. 读取该用户历史 Allow 记录（behavior_log 中 resolution=allow 的条目）
2. 逐条检验：新规则是否会误拦历史 Allow 操作
3. 发现冲突：记录冲突原因，尝试缩窄规则的 scene 条件后重新验证
4. 二次验证仍冲突：拒绝写入，写入 `candidate_rules_rejected.jsonl`
5. 验证通过：进入写入 RAG 阶段

**详细设计** 见 `skills/skill-evolution-mechanic/references/sandbox_policy.md`

---

## 二、架构决策

### 决策 1：实时监控与闲时进化的解耦

**问题**：Monitor 和 Evolution 能放在一起执行吗？

**结论**：逻辑上属于同一个"自进化子系统"，但在执行流上必须**完全解耦**。

| 模块 | 执行模式 | 特点 |
|------|----------|------|
| Behavior Monitor | 实时/同步 | 必须嵌在主干流中，轻量级，绝不阻塞 GUI 操作 |
| Evolution Mechanic | 异步/批处理 | 调用大模型进行深度思考，可能耗时十几秒甚至几分钟 |

**正确的连接方式**：通过**存储解耦**，即日志文件（或数据库）。

```
Monitor (Write) → 日志文件 → Evolution (Read) → ChromaDB
```

---

### 决策 2：多租户用户隔离

**问题**：云端服务器如何处理多本地客户端？

**架构设计**：

#### 第一步：API 接口必须带 `user_id`

本地 Windows 客户端在请求云端时，必须在 Header 或 Payload 中附带唯一标识（如 `client_id="win_user_001"`）。

#### 第二步：Monitor 的隔离存储

按用户建文件夹存 JSON：

```
logs/
├── /win_user_001
│     └── conflict_logs.jsonl  ← 只存 user_001 的行为日志
└── /win_user_002
      └── conflict_logs.jsonl
```

#### 第三步：Evolution 的隔离归纳与入库

利用 ChromaDB 的 Collection 机制实现分区：

```python
# chroma_manager.py 核心伪代码
def save_rule_for_user(user_id, rule_text, rule_metadata):
    # 每个用户在 ChromaDB 里拥有独立的 Collection
    collection_name = f"rules_{user_id}" 
    collection = chroma_client.get_or_create_collection(name=collection_name)
    
    # 将进化出的规则存入该用户的专属库
    collection.add(
        documents=[rule_text],
        metadatas=[rule_metadata],
        ids=[generate_uuid()]
    )
```

#### 第四步：Proxy Agent 的个性化读取

1. `proxy_agent.py` 拿到 `user_id="win_user_001"` 和当前屏��画面
2. 去 ChromaDB 查询 `Collection("rules_win_user_001")`
3. 拿出专属规则，塞进系统 Prompt 里，完成防护

---

## 三、模块职责边界

### Behavior Monitor（行为监控）

**职责**：
- 提供 `log_conflict(user_id, original_action, user_correction)` 函数
- 在 `api_server.py` 里被调用
- 只做事件标准化与日志输出，不做隐私识别，不写 RAG

**核心概念**：
- 单条记录契约：`{"timestamp": int, "action": str, "correction": str, "metadata": object}`
- `correction` 用于标识纠偏行为，空字符串表示未发生纠偏

---

### Evolution Mechanic（自进化引擎）

**职责**：
- 提供 `run_evolution(user_id)` 函数
- 处理繁重的离线大脑任务
- 调用大模型进行 Self-RAG + 沙箱验证

**触发条件**：
- 同一用户的同一类操作，累积了 N=2 条以上有效纠错记录
- 用户主动请求"总结我的习惯"或"更新隐私规则"
- 系统进入空闲时段（夜间定时任务）

---

### 如何串联

不需要强行把它们写在一个"主执行代码"里。可以：

1. 在 `api_server.py` 里起一个**后台线程**
2. 或加一个专门的 API 接口 `/trigger_evolution`

当某个用户的日志满 5 条时，`behavior_monitor.py` 发送异步信号，触发 `evolution_mechanic.py` 去干活。

---

## 四、目录结构

```
skills/
├── behavior-monitor/
│     ├── SKILL.md
│     ├── references/
│     │     ├── event_types.md      # action/resolution/correction_type 枚举
│     │     └── log_schema.md       # 日志格式定义
│     └── scripts/
│           └── monitor.py          # 监控脚本
│
└── skill-evolution-mechanic/
      ├── SKILL.md
      ├── references/
      │     ├── pairing_spec.md     # 日志配对规范
      │     ├── confidence_policy.md # 置信度计算策略
      │     ├── prompt_template.md   # Prompt 模板
      │     ├── rule_schema.md      # 规则结构定义
      │     └── sandbox_policy.md   # 沙盒验证逻辑
      └── scripts/
            └── extract_rule.py     # 规则提取脚本

memory/
└── chroma_storage/
      ├── rules.json                # 基础隐私规则
      └── chroma.sqlite3            # 向量数据库

logs/
└── {user_id}/
      ├── behavior_log.jsonl       # 轻量记录
      └── correction_log.jsonl     # 完整记录（Evolution 原料）
```

---

## 五、日志 Schema 要点

### 级别 1：轻量记录

```json
{
  "event_id": "user_A_1700000001_3821",
  "user_id": "user_A",
  "ts": 1700000001,
  "app_context": "taobao",
  "action": "fill_shipping_address",
  "field": "home_address",
  "resolution": "allow",
  "level": 1,
  "processed": false,
  "expire_ts": 1700086401
}
```

### 级别 2：完整记录（用户纠错）

```json
{
  "event_id": "user_A_1700000042_1156",
  "user_id": "user_A",
  "ts": 1700000042,
  "app_context": "wechat",
  "action": "send_file",
  "field": "file_content",
  "resolution": "interrupt",
  "level": 2,
  "processed": false,
  "expire_ts": 1700086442,
  "value_preview": "病历截图.jpg",
  "correction_type": "user_interrupted",
  "correction_value": null,
  "pii_types_involved": ["MEDICAL_RECORD"]
}
```

### 哪些 correction_type 进入 Evolution

只有以下三种是有效的训练信号：
- `user_denied` — 用户明确不想要这个操作
- `user_modified` — 用户有具体偏好，信号最强
- `user_interrupted` — 用户主动介入，行为意图最明确

---

## 六、后续工作建议

### 选项 A：实现 Monitor 的具体功能

- 如何接收拦截数据
- 如何以高并发安全的方式追加写入 `logs/{user_id}/conflict.jsonl`

### 选项 B：实现 Evolution 的主逻辑

- 如何读取 JSONL
- 如何拼装 Prompt 交给模型
- 如何调用 `chroma_manager.py` 写入对应用户的向量库

---

## 七、参考文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统整体工作流与端云协同架构
- [docs/SKILLS_API.md](docs/SKILLS_API.md) — 四大核心 Skills 的输入输出契约
- [docs/RAG_SCHEMA.md](docs/RAG_SCHEMA.md) — ChromaDB 向量数据库的存储范式
- [docs/PROMPT_TEMPLATES.md](docs/PROMPT_TEMPLATES.md) — Prompt 模板集合
- `skills/behavior-monitor/SKILL.md` — Behavior Monitor 技能定义
- `skills/skill-evolution-mechanic/SKILL.md` — Evolution Mechanic 技能定义