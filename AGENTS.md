# AGENTS.md

## 项目身份
本项目是一个**基于端侧 Tool-Use 的隐私前置代理框架 (Privacy-Preserving Forward Proxy via On-device Tool-Use)**。
它充当云端 Agent (AutoGLM) 与手机/桌面 UI 之间的“安全保镖”。系统通过端侧 MiniCPM-o 大模型调度一组原子化工具 (Skills)，在执行前对敏感数据进行实时识别、动态脱敏，并通过用户行为反馈实现隐私防护策略的自进化。

## 知识库索引
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)：系统整体工作流与端云协同架构。
- [docs/SKILLS_API.md](docs/SKILLS_API.md)：四大核心 Skills (PII_Detection, Visual_Obfuscation, Behavior_Monitor, Skill_Evolution) 的输入输出契约。
- [docs/RAG_SCHEMA.md](docs/RAG_SCHEMA.md)：本地 ChromaDB 向量数据库的存储范式与元数据设计。
- [docs/PROMPT_TEMPLATES.md](docs/PROMPT_TEMPLATES.md)：端侧 LLM 进行推理、Critique 及代码补丁生成的 Prompt 模板。

## 架构速览：Tool-Use 调度模式
本系统彻底摒弃了静态流水线，采用 **“LLM 调度 Skills”** 的动态决策架构：
1.  **感知层 (Perception)**：通过视觉与 XML 结构分析，将屏幕状态转化为大模型可理解的上下文。
2.  **认知层 (Cognition)**：MiniCPM-o 作为调度中心，根据当前 UI 上下文动态检索 RAG 规则，确定何种情况适配哪个RAG规则，并决定哪个skill的调用。
3.  **工具层 (Tool-Use)**：执行打码、过滤、修改动作，将“已脱敏的安全数据”以及检索到的RAG规则转发给云端 Agent。
4.  **进化层 (Self-Evolution)**：通过监控用户对 Agent 的纠错行为，触发 Skill_Evolution 模块编写新的防御补丁并入库。

## Agent 行为约束
- **工具调用优先原则**：严禁在业务逻辑中直接硬编码拦截策略。所有拦截逻辑必须封装为独立的 Skill，并由 LLM 动态调用。
- **端侧闭环原则**：任何涉及用户隐私的计算（OCR、打码、行为归纳）必须在端侧设备完成，严禁将原始截图与未脱敏数据上传云端。
- **防御先于执行**：Agent 必须确保在 `cloud_connector.py` 转发数据前，已完成所有的 `PII_Detection` 与 `Visual_Obfuscation` 任务。
- **沙盒验证规范**：L3 层自进化生成的新技能或补丁，必须通过 `sandbox/regression_test.py` 测试后方可投入使用，防止策略坍塌。
- **防御链路幂等性**：同一页面若多次触发拦截，需通过 RAG 语义去重，避免重复存储冗余的个性化规则。

## 快速入门
1. **环境初始化**：确认模型服务已启动（`model_server/minicpm_api.py`），确保端侧算力节点就绪。
2. **连接验证**：通过测试脚本调用 `PII_Detection_Skill` 和 `Visual_Obfuscation_Skill`，验证端侧打码功能是否正常回传安全截图。
3. **闭环测试**：手动触发一个用户纠偏动作（如：删除 Agent 误填的隐私信息），观察 `Behavior_Monitor_Skill` 是否成功记录，并等待后续 `Skill_Evolution` 自动生成新规则。