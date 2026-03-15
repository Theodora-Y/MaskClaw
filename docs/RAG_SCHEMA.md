# RAG 数据库规范

本地 ChromaDB 存储的规则，用于指导端侧 LLM 的决策。

## 规则格式
- **ID**: 唯一标识 (例如: `rule_user_001`)
- **Metadata**: 
  - `scenario`: UI 场景描述 (例如: "非电商注册页")
  - `target_field`: 涉及的 UI 字段 (例如: "住址")
- **Document**: 个性化操作准则 (例如: "禁止填写真实地址，强制填入公司地址")
- **Skill_Reference**: 关联的技能 (例如: `Visual_Obfuscation_Skill`)