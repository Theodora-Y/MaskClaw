# 隐私保护代理 - 快速入门指南

## 环境要求

- Python 3.10+
- CUDA 可选（用于 GPU 加速）
- 视觉模型: MiniCPM-V-4_5 (位于 `models/OpenBMB/MiniCPM-V-4_5/`)

## 安装依赖

```bash
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python fastapi uvicorn requests transformers>=4.51.0 torch
```

## 项目结构

```
privacy_agent_project/
├── proxy_agent.py              # 核心隐私代理 (PrivacyProxyAgent)
├── api_server.py               # FastAPI HTTP 服务 (端口 8001)
│
├── model_server/
│   └── minicpm_api.py          # MiniCPM-V-4_5 视觉模型 API (端口 8000)
│   └── requirements.txt         # 模型服务依赖
│
├── models/                      # 模型文件目录
│   └── OpenBMB/
│       └── MiniCPM-V-4_5/       # 视觉理解模型 (~16.5GB)
│
├── skills/                      # Skills 模块
│   ├── smart_masker.py          # 视觉打码模块
│   ├── behavior_monitor.py      # 行为监控模块
│   ├── evolution_mechanic.py    # 自进化机制
│   ├── behavior-monitor/       # 行为监控 Skill
│   │   ├── SKILL.md
│   │   ├── scripts/monitor.py
│   │   └── references/
│   └── skill-evolution-mechanic/  # 技能进化 Skill
│       ├── SKILL.md
│       ├── scripts/extract_rule.py
│       └── references/
│
├── memory/                     # 记忆存储
│   ├── chroma_manager.py       # ChromaDB 管理器
│   ├── chroma_manager.md       # ChromaDB 说明文档
│   └── chroma_storage/
│       └── rules.json          # 隐私规则库
│
├── prompts/                    # Prompt 模板
│   ├── privacy_analysis.txt    # 隐私分析提示词
│   ├── retrieval_decision.txt  # 检索决策提示词
│   └── relevance_assessment.txt # 相关性评估提示词
│
├── docs/                       # 架构文档
│   ├── ARCHITECTURE.md         # 系统架构文档
│   ├── SKILLS_API.md           # Skills API 文档
│   ├── RAG_SCHEMA.md           # RAG 数据模式
│   ├── PROMPT_TEMPLATES.md     # Prompt 模板文档
│   └── self_evolution_mechanism.md  # 自进化机制
│
├── temp/                       # 临时文件目录
├── logs/                       # 日志目录
├── sandbox/                    # 沙盒测试目录
│
├── demo.py                     # API 测试演示脚本
├── run_with_privacy.sh         # 隐私保护启动脚本
├── README.md                   # 本文件
└── AGENTS.md                   # Agent 行为约束文档
```

## 启动方式

### 1. 启动 MiniCPM-V-4_5 视觉模型 API (端口 8000)

```bash
python model_server/minicpm_api.py
# 服务地址: http://127.0.0.1:8000
```

### 2. 启动隐私代理 HTTP 服务 (端口 8001)

```bash
python api_server.py
# 服务地址: http://127.0.0.1:8001
```

### 3. 直接运行测试

```bash
# 测试 API
python demo.py

# 测试 ChromaDB 检索
python proxy_agent.py --test
```

## API 接口说明

### 1. 健康检查

```bash
# 隐私代理服务
curl http://localhost:8001/

# MiniCPM 视觉模型
curl -X POST http://localhost:8000/chat -F "prompt=hello"
```

### 2. 处理截图（返回脱敏图片）

```bash
curl -X POST http://localhost:8001/process \
  -F "image=@test.jpg" \
  -F "command=分析当前页面隐私" \
  -o output.jpg
```

### 3. 查看所有规则

```bash
curl http://localhost:8001/rules
```

### 4. 添加新规则

```bash
curl -X POST http://localhost:8001/rules \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "账号注册页",
    "target_field": "手机号",
    "document": "禁止填写真实手机号",
    "skill": "Visual_Obfuscation_Skill"
  }'
```

## 隐私规则格式 (rules.json)

```json
{
  "rules": [
    {
      "id": "rule_privacy_001",
      "scenario": "账号注册/登录页",
      "target_field": "手机号",
      "document": "禁止填写真实手机号",
      "skill": "Visual_Obfuscation_Skill"
    }
  ]
}
```

## SSH 端口映射（本地开发）

如果要在本地调用服务器 API：

```bash
# 映射 MiniCPM API (8000)
ssh -L 8000:172.17.0.2:8000 root@connect.bjb1.seetacloud.com -N

# 映射隐私代理 API (8001)
ssh -L 8001:172.17.0.2:8001 root@connect.bjb1.seetacloud.com -N
```

## 工作流程

```
用户截图
    ↓
┌─────────────────────────────────────────┐
│  1. ChromaDB 检索规则 (Self-RAG)       │
│  2. MiniCPM-V-4_5 分析隐私信息         │
│  3. Smart Masker 视觉打码              │
└─────────────────────────────────────────┘
    ↓
返回脱敏后的截图
```

## Skills 核心模块

| 模块 | 功能 |
|------|------|
| `PII_Detection` | 检测图片中的个人隐私信息 |
| `Visual_Obfuscation` | 对敏感区域进行视觉打码 |
| `Behavior_Monitor` | 监控用户纠错行为 |
| `Skill_Evolution` | 根据反馈自进化生成新规则 |
