# 架构速览：Tool-Augmented Privacy Proxy

本系统采用 **端侧隐私代理（Privacy Proxy）** 架构，置于云端 Agent 与本地 UI 之间。

## 核心流程
1. **感知与预处理**：当云端 Agent 发起请求时，代理截获原始截图。
2. **LLM 调度与认知**：端侧 MiniCPM-o 接收截图，检索 RAG 规则库，并根据规则调度 `Skills`。
3. **安全执行**：使用MiniCPM对图片终端隐私信息进行判定，调用`Smart_Masker`进行脱敏。
4. **安全转发**：将“处理后的图片 + 个性化操作准则”下发至云端 Agent。
5. **行为自进化 (闭环)**：`Behavior_Monitor` 捕获用户纠错日志，`Skill_Evolution` 分析并生成新技能/规则存入本地数据库。