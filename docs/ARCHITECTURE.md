# 系统架构文档

## 1. 项目身份

**MaskClaw** 是一个基于端侧 Tool-Use 的隐私前置代理框架 (Privacy-Preserving Forward Proxy via On-device Tool-Use)。

它充当云端 Agent (AutoGLM) 与手机/桌面 UI 之间的"安全保镖"。系统通过端侧 MiniCPM-V 大模型调度一组原子化工具 (Skills)，在执行前对敏感数据进行实时识别、动态脱敏，并通过用户行为反馈实现隐私防护策略的自进化。

## 2. 知识库索引

| 文档 | 说明 |
|:---|:---|
| [SKILLS_API.md](SKILLS_API.md) | 四大核心 Skills (PII_Detection, Smart_Masker, Behavior_Monitor, Skill_Evolution) 的输入输出契约 |
| [RAG_SCHEMA.md](RAG_SCHEMA.md) | 本地 ChromaDB 向量数据库的存储范式与元数据设计 |
| [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md) | 端侧 LLM 进行推理、Critique 及代码补丁生成的 Prompt 模板 |

## 3. 目录分工

- `skills/`：系统内置 Skill（平台级能力，随项目发布）
- `user_skills/`：用户个性化 Skill（由 L3 Evolution 生成与版本化管理）

系统运行时可同时读取两类 Skill，但生成逻辑只写入 `user_skills/`。

## 4. 架构速览：Tool-Use 调度模式

本系统彻底摒弃了静态流水线，采用 **"LLM 调度 Skills"** 的动态决策架构：

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MaskClaw 四层协同架构                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐ │
│  │  感知层    │ → │  认知层    │ → │  工具层    │ → │  进化层    │ │
│  │ Perception │    │ Cognition │    │ Tool-Use  │    │Evolution  │ │
│  └───────────┘    └───────────┘    └───────────┘    └───────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                        ChromaDB RAG                          │  │
│  │              规则知识库 + 行为记忆 + 场景匹配                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.1 感知层 (Perception)

通过视觉与 XML 结构分析，将屏幕状态转化为大模型可理解的上下文：

- 截图预处理与区域划分
- UI 元素结构化提取
- 敏感区域初步定位

### 4.2 认知层 (Cognition)

MiniCPM-V 作为调度中心，根据当前 UI 上下文动态检索 RAG 规则，确定何种情况适配哪个规则，并决定哪个 Skill 的调用：

- ChromaDB 隐私规则向量检索
- 场景匹配与策略选择
- Skill 动态调度决策

### 4.3 工具层 (Tool-Use)

执行打码、过滤、修改动作，将"已脱敏的安全数据"以及检索到的规则转发给云端 Agent：

- PII 检测与定位
- 视觉智能打码
- 脱敏后数据转发

### 4.4 进化层 (Self-Evolution)

通过监控用户对 Agent 的纠错行为，触发自动规则更新：

- 用户行为日志捕获
- 模式识别与规则生成
- 沙盒验证与版本管理

## 5. 核心流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         核心处理流程                                 │
└─────────────────────────────────────────────────────────────────────┘

1. 感知与预处理
   - 当云端 Agent 发起请求时，代理截获原始截图
   - PaddleOCR 快速识别格式化敏感信息
   - 区域划分与初步定位

2. LLM 调度与认知
   - MiniCPM-V 接收截图，检索 RAG 规则库
   - 根据规则调度 Skills
   - 语义级隐私判断

3. 安全执行
   - Smart Masker 执行视觉脱敏
   - ChromaDB 规则匹配
   - 五级置信度判决 (Allow/Block/Mask/Ask/Unsure)

4. 安全转发
   - 将"处理后的图片 + 个性化操作准则"下发至云端 Agent
   - 保持对上游 Agent 透明

5. 行为自进化 (闭环)
   - Behavior_Monitor 捕获用户纠错日志
   - Skill_Evolution 分析并生成新技能/规则
   - 存入本地数据库，沙盒测试验证后挂载
```

## 6. 端云交互协议

### 6.1 入方向（端 → 云）

```json
{
  "action": "forward_to_agent",
  "image": "<base64_encoded_masked_image>",
  "rules_applied": ["rule_id_1", "rule_id_2"],
  "judgment": "Mask",
  "confidence": 0.95,
  "metadata": {
    "timestamp": 1234567890,
    "source_app": "wechat",
    "sensitive_regions": [[x1, y1, x2, y2]]
  }
}
```

### 6.2 出方向（云 → 端）

```json
{
  "action": "agent_request",
  "raw_screenshot": "<base64>",
  "intent": "send_message",
  "target_app": "wechat",
  "callback_rules": ["wait_for_user_confirm"]
}
```

## 7. Agent 行为约束

- **工具调用优先原则**：严禁在业务逻辑中直接硬编码拦截策略。所有拦截逻辑必须封装为独立的 Skill，并由 LLM 动态调用。
- **端侧闭环原则**：任何涉及用户隐私的计算（OCR、打码、行为归纳）必须在端侧设备完成，严禁将原始截图与未脱敏数据上传云端。
- **防御先于执行**：Agent 必须确保在转发数据前，已完成所有的 PII_Detection 与 Smart_Masker 任务。
- **沙盒验证规范**：L3 层自进化生成的新技能或补丁，必须通过 `sandbox/regression_test.py` 测试后方可投入使用，防止策略坍塌。
- **防御链路幂等性**：同一页面若多次触发拦截，需通过 RAG 语义去重，避免重复存储冗余的个性化规则。

## 8. 快速入门

1. **环境初始化**：确认模型服务已启动（`model_server/minicpm_api.py`），确保端侧算力节点就绪
2. **连接验证**：通过测试脚本调用 `PII_Detection_Skill` 和 `Smart_Masker_Skill`，验证端侧打码功能是否正常回传安全截图
3. **闭环测试**：手动触发一个用户纠偏动作（如：删除 Agent 误填的隐私信息），观察 `Behavior_Monitor_Skill` 是否成功记录，并等待后续 `Skill_Evolution` 自动生成新规则
