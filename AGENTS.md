# AGENTS.md - MaskClaw Agent 行为约束文档

## 1. 项目身份

**MaskClaw** 是一个**基于端侧 Tool-Use 的隐私前置代理框架 (Privacy-Preserving Forward Proxy via On-device Tool-Use)**。

它充当云端 Agent (AutoGLM) 与手机/桌面 UI 之间的"安全保镖"。系统通过端侧 MiniCPM-V 大模型调度一组原子化工具 (Skills)，在执行前对敏感数据进行实时识别、动态脱敏，并通过用户行为反馈实现隐私防护策略的自进化。

## 2. 知识库索引

| 文档 | 说明 |
|:---|:---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统整体工作流与端云协同架构 |
| [docs/SKILLS_API.md](docs/SKILLS_API.md) | 四大核心 Skills (PII_Detection, Smart_Masker, Behavior_Monitor, Skill_Evolution) 的输入输出契约 |
| [docs/RAG_SCHEMA.md](docs/RAG_SCHEMA.md) | 本地 ChromaDB 向量数据库的存储范式与元数据设计 |
| [docs/PROMPT_TEMPLATES.md](docs/PROMPT_TEMPLATES.md) | 端侧 LLM 进行推理、Critique 及代码补丁生成的 Prompt 模板 |

## 3. 目录分工

- `skills/`：系统内置 Skill（平台级能力，随项目发布）
- `user_skills/`：用户个性化 Skill（由 L3 Evolution 生成与版本化管理）

系统运行时可同时读取两类 Skill，但生成逻辑只写入 `user_skills/`。

## 4. 架构速览：Tool-Use 调度模式

本系统彻底摒弃了静态流水线，采用 **"LLM 调度 Skills"** 的动态决策架构：

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MaskClaw 动态调度架构                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 感知层 (Perception)                                              │
│     通过视觉与 XML 结构分析，将屏幕状态转化为大模型可理解的上下文        │
│                                                                     │
│  2. 认知层 (Cognition)                                              │
│     MiniCPM-V 作为调度中心，根据当前 UI 上下文动态检索 RAG 规则        │
│                                                                     │
│  3. 工具层 (Tool-Use)                                               │
│     执行打码、过滤、修改动作，将"已脱敏的安全数据"转发给云端 Agent    │
│                                                                     │
│  4. 进化层 (Self-Evolution)                                         │
│     通过监控用户对 Agent 的纠错行为，触发 Skill_Evolution 模块生成新规则│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 5. Agent 行为约束

### 5.1 工具调用优先原则

> **严禁在业务逻辑中直接硬编码拦截策略。所有拦截逻辑必须封装为独立的 Skill，并由 LLM 动态调用。**

**原因**：硬编码的拦截策略难以维护、无法自适应、无法从用户反馈中学习。

**正确做法**：
```python
# ❌ 错误：硬编码拦截
if "phone" in user_input:
    block_request()

# ✅ 正确：通过 Skill 调度
decision = await llm_router.decide(
    context=current_context,
    rules=rag_retriever.query(current_context)
)
await skills[decision.skill].execute(decision.params)
```

### 5.2 端侧闭环原则

> **任何涉及用户隐私的计算（OCR、打码、行为归纳）必须在端侧设备完成，严禁将原始截图与未脱敏数据上传云端。**

**原因**：云端处理存在隐私泄露风险，不满足医疗、金融等行业合规要求。

**正确做法**：
- PII 检测在端侧完成
- 视觉打码在端侧完成
- 行为分析在端侧完成
- 仅将脱敏后的结果发送给云端

### 5.3 防御先于执行原则

> **Agent 必须确保在转发数据前，已完成所有的 PII_Detection 与 Smart_Masker 任务。**

**执行顺序**：
```
1. 截获 Agent 请求
2. 执行 PII_Detection
3. 执行 Smart_Masker（如需要）
4. 更新 RAG 规则（如需要）
5. 转发脱敏数据给云端 Agent
```

### 5.4 沙盒验证规范

> **L3 层自进化生成的新技能或补丁，必须通过 `sandbox/regression_test.py` 测试后方可投入使用，防止策略坍塌。**

**验证流程**：
```
新规则生成
    ↓
沙盒测试（离线）
    ↓
性能评估
    ↓
人工审核（如需要）
    ↓
灰度发布
    ↓
全量上线
```

### 5.5 防御链路幂等性

> **同一页面若多次触发拦截，需通过 RAG 语义去重，避免重复存储冗余的个性化规则。**

**去重策略**：
- 新规则与现有规则相似度 > 0.85 时，合并而非新增
- 新规则与现有规则冲突时，标记冲突并进入审核流程
- 定期执行规则库清理，合并相似规则

## 6. 五大核心约束

| 约束 | 说明 | 违规风险 |
|:---|:---|:---|
| **工具调用优先** | 所有拦截逻辑通过 Skill 调用 | 系统僵化，无法自适应 |
| **端侧闭环** | 隐私计算在端侧完成 | 合规风险，数据泄露 |
| **防御先于执行** | 脱敏先于转发 | 隐私保护失效 |
| **沙盒验证** | 新规则需测试验证 | 策略坍塌风险 |
| **语义去重** | 规则库无冗余 | 规则膨胀，性能下降 |

## 7. 快速入门

### 7.1 环境初始化

确认模型服务已启动（`model_server/minicpm_api.py`），确保端侧算力节点就绪。

### 7.2 连接验证

通过测试脚本调用 `PII_Detection_Skill` 和 `Smart_Masker_Skill`，验证端侧打码功能是否正常回传安全截图。

### 7.3 闭环测试

手动触发一个用户纠偏动作（如：删除 Agent 误填的隐私信息），观察 `Behavior_Monitor_Skill` 是否成功记录，并等待后续 `Skill_Evolution` 自动生成新规则。

## 8. 常见问题

### Q1: 何时触发 Skill_Evolution？

当 `Behavior_Monitor` 检测到用户主动修正 Agent 操作时，会记录日志并检查是否达到触发阈值（默认：连续3次相同类型的修正）。

### Q2: 如何处理冲突规则？

当新规则与现有规则冲突时，系统会：
1. 暂停新规则上线
2. 通知人工审核
3. 审核通过后，标记旧规则为 deprecated

### Q3: 冷启动阶段如何处理？

系统上线时携带通用基础规则集，覆盖常见场景。对于未知场景，Unsure 机制会主动向用户确认。
