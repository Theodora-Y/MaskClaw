# RAG 数据模式

本文档定义了 MaskClaw 框架中 ChromaDB 向量数据库的存储范式与元数据设计。

## 1. 概述

MaskClaw 使用 ChromaDB 作为本地向量数据库，支持 RAG（检索增强生成）语义检索，用于：

- 隐私规则知识库检索
- 相似场景匹配
- 用户行为模式存储
- 历史案例参考

## 2. 集合设计

### 2.1 集合列表

| 集合名 | 用途 | 典型规模 |
|:---|:---|:---|
| `privacy_rules` | 隐私规则库 | ~100-1000 条 |
| `behavior_logs` | 行为日志向量 | ~10000+ 条 |
| `user_preferences` | 用户偏好 | ~100 条/用户 |
| `scenario_context` | 场景上下文 | ~500 条 |

### 2.2 向量配置

```python
# 向量配置
EMBEDDING_CONFIG = {
    "model": "text-embedding-3-small",  # 或本地 MiniCPM embedding
    "dimension": 1536,
    "normalize": True,
    "metric": "cosine"
}
```

## 3. privacy_rules 集合

### 3.1 Schema

```json
{
  "id": "rule_privacy_001",
  "scenario": "账号注册/登录页",
  "target_field": "手机号",
  "action_type": "mask",
  "document": "禁止填写真实手机号，应使用虚拟号或脱敏处理",
  "examples": [
    "注册时要求填写手机号",
    "登录页显示手机号输入框"
  ],
  "confidence_threshold": 0.8,
  "source": "system_default",
  "version": "1.0.0",
  "created_at": 1711867260000,
  "updated_at": 1711867260000,
  "user_id": null,
  "tags": ["registration", "phone", "sensitive"]
}
```

### 3.2 元数据字段说明

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `id` | `str` | 规则唯一标识 |
| `scenario` | `str` | 场景描述 |
| `target_field` | `str` | 目标字段 |
| `action_type` | `str` | 动作类型：allow/block/mask/ask |
| `document` | `str` | 规则文档描述 |
| `examples` | `List[str]` | 典型示例 |
| `confidence_threshold` | `float` | 置信度阈值 |
| `source` | `str` | 来源：system_default/user_evolution/collab_filter |
| `version` | `str` | 规则版本 |
| `created_at` | `int` | 创建时间戳 |
| `updated_at` | `int` | 更新时间戳 |
| `user_id` | `str\|null` | 用户ID（null表示通用规则） |
| `tags` | `List[str]` | 标签 |

### 3.3 向量化内容

```python
def get_rule_embedding_text(rule: dict) -> str:
    """生成规则向量化的文本"""
    parts = [
        f"场景: {rule['scenario']}",
        f"目标字段: {rule['target_field']}",
        f"动作: {rule['action_type']}",
        f"规则说明: {rule['document']}",
    ]
    if rule.get('examples'):
        parts.append(f"示例: {'; '.join(rule['examples'])}")
    return " | ".join(parts)
```

## 4. behavior_logs 集合

### 4.1 Schema

```json
{
  "id": "log_20260331_123456",
  "session_id": "sess_abc123",
  "user_id": "user_001",
  "action_type": "user_correction",
  "original_action": {
    "type": "agent_operation",
    "operation": "fill_form",
    "field": "phone_number",
    "value": "13812345678"
  },
  "corrected_action": {
    "type": "user_override",
    "corrected_value": "138****8888",
    "reason": "隐私保护"
  },
  "context": {
    "app": "wechat",
    "page": "friend_verification",
    "ui_elements": ["输入框", "确认按钮"]
  },
  "extracted_pattern": "在微信好友验证场景下，不应填写真实手机号",
  "will_generate_rule": true,
  "created_at": 1711867260000
}
```

### 4.2 索引策略

```python
# 索引配置
INDEX_CONFIG = {
    "enable": True,
    "fields": ["user_id", "action_type", "created_at"]
}
```

## 5. user_preferences 集合

### 5.1 Schema

```json
{
  "id": "pref_user_001_privacy_level",
  "user_id": "user_001",
  "preference_type": "privacy_level",
  "value": "high",
  "inferred_from": ["log_20260331_123456", "log_20260331_123457"],
  "confidence": 0.92,
  "updated_at": 1711867260000
}
```

## 6. scenario_context 集合

### 6.1 Schema

```json
{
  "id": "ctx_wechat_friend_verification",
  "app": "wechat",
  "page": "friend_verification",
  "description": "微信好友验证页面",
  "common_fields": ["手机号", "微信号", "QQ号"],
  "sensitivity": "high",
  "related_rules": ["rule_privacy_001", "rule_user_001_01"],
  "typical_actions": ["填写验证信息", "提交验证"]
}
```

## 7. 检索优化策略

### 7.1 语义去重

```python
def deduplicate_rules(new_rule: dict, existing_rules: list, threshold: float = 0.85) -> bool:
    """
    检查新规则是否与现有规则重复
    
    Returns:
        True: 新规则有效，可以添加
        False: 新规则与现有规则重复
    """
    for existing in existing_rules:
        similarity = compute_similarity(new_rule['document'], existing['document'])
        if similarity >= threshold:
            # 检查是否有冲突
            if new_rule['action_type'] != existing['action_type']:
                return False  # 冲突的重复规则
    return True
```

### 7.2 优先级排序

```python
def rank_rules(rules: list, query_context: dict) -> list:
    """
    根据上下文对规则进行排序
    
    排序因素:
    1. 用户个性化规则优先
    2. 场景匹配度
    3. 规则置信度
    4. 更新时间（新规则优先）
    """
    scored = []
    for rule in rules:
        score = 0.0
        
        # 用户个性化 (+0.4 if user_id matches)
        if rule.get('user_id') == query_context.get('user_id'):
            score += 0.4
        
        # 场景匹配 (+0.3)
        if query_context.get('app') in rule.get('tags', []):
            score += 0.3
        
        # 规则置信度 (+0.2)
        score += rule.get('confidence_threshold', 0.5) * 0.2
        
        # 更新时间 (+0.1)
        recency = (rule.get('updated_at', 0) - time.time()) / (365 * 24 * 3600)
        score += max(0, 0.1 - recency)
        
        scored.append((score, rule))
    
    return [r for _, r in sorted(scored, reverse=True)]
```

### 7.3 生命周期管理

```python
# 规则过期策略
EXPIRATION_POLICY = {
    "user_generated_rules": {
        "ttl_days": 90,  # 用户规则90天后需要重新验证
        "extend_on_use": True
    },
    "system_rules": {
        "ttl_days": None,  # 系统规则永不过期
        "deprecate_on_new_version": True
    },
    "collab_filter_rules": {
        "ttl_days": 30,  # 协同过滤规则30天后降权
        "decay_factor": 0.5
    }
}
```

## 8. 备份与恢复

### 8.1 备份

```bash
# 导出集合
chroma export --collection privacy_rules --output backup/rules.json

# 全量备份
chroma backup --output backup/full_backup_$(date +%Y%m%d).zip
```

### 8.2 恢复

```bash
# 恢复集合
chroma import --collection privacy_rules --input backup/rules.json

# 从备份恢复
chroma restore --input backup/full_backup_20260331.zip
```

## 9. 性能指标

| 指标 | 目标值 |
|:---|:---|
| 查询延迟 (P99) | < 50ms |
| 插入吞吐量 | > 1000 docs/s |
| 检索召回率 (@5) | > 90% |
| 存储空间占用 | < 1GB (典型规模) |
