# 隐私保护代理 - 快速入门指南

## 环境要求

- Python 3.10+
- CUDA 可选（用于 GPU 加速）

## 安装依赖

```bash
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python fastapi uvicorn requests
```

## 项目结构

```
privacy_agent_project/
├── proxy_agent.py          # 核心隐私代理
├── api_server.py           # FastAPI HTTP 服务
├── skills/
│   └── smart_masker.py     # 视觉打码模块
├── memory/
│   └── chroma_storage/
│       └── rules.json       # 隐私规则库
├── prompts/
│   ├── retrieval_decision.txt
│   └── relevance_assessment.txt
├── model_server/
│   └── minicpm_api.py       # MiniCPM API 服务
└── temp/                    # 临时文件目录
```

## 启动方式

### 方式 1：直接运行 Python 测试

```bash
# 测试 ChromaDB 检索
python3 proxy_agent.py --test
```

### 方式 2：启动 FastAPI HTTP 服务

```bash
python3 api_server.py
# 默认端口: 8001
```

### 方式 3：启动 MiniCPM API 服务

```bash
cd model_server
python3 minicpm_api.py
# 默认端口: 8000
```

## API 接口说明

### 1. 健康检查
```bash
curl http://localhost:8001/
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
curl -X POST http://localhost:8001/rules/add \
  -F "scenario=测试场景" \
  -F "target_field=测试字段" \
  -F "document=测试规则内容"
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

如果要在本地 Windows 调用服务器 API：

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
│  2. MiniCPM 分析隐私信息               │
│  3. Smart Masker 视觉打码              │
└─────────────────────────────────────────┘
    ↓
返回脱敏后的截图
```
