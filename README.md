# 隐私保护代理框架 (Privacy-Preserving Forward Proxy)

## 项目简介

本项目是一个**基于端侧 Tool-Use 的隐私前置代理框架 (Privacy-Preserving Forward Proxy via On-device Tool-Use)**。

它充当云端 Agent (AutoGLM) 与手机/桌面 UI 之间的"安全保镖"。系统通过端侧 MiniCPM-V 视觉大模型调度一组原子化工具 (Skills)，在执行前对敏感数据进行实时识别、动态脱敏，并通过用户行为反馈实现隐私防护策略的自进化。

### 核心功能

- **PII 检测**：自动识别截图中的个人隐私信息（手机号、身份证、银行卡等）
- **视觉脱敏**：对敏感区域进行智能打码处理
- **行为监控**：记录用户纠错行为，用于策略优化
- **自进化机制**：根据反馈自动生成新的防御规则

### 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    云端 Agent (AutoGLM)                  │
└─────────────────────────┬───────────────────────────────┘
                          │ 脱敏后数据
┌─────────────────────────▼───────────────────────────────┐
│              隐私保护代理 (Privacy Proxy)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ PII检测Skill│  │ 视觉脱敏Skill│  │ 行为监控Skill│     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │            │
│  ┌──────▼────────────────▼────────────────▼──────┐     │
│  │              ChromaDB RAG 知识库               │     │
│  └────────────────────────────────────────────────┘     │
└─────────────────────────┬───────────────────────────────┘
                          │ 原始截图/UI
┌─────────────────────────▼───────────────────────────────┐
│                  端侧设备 (手机/桌面)                     │
└─────────────────────────────────────────────────────────┘
```

---

## 环境要求

- **Python**: 3.10+
- **CUDA**: 可选（用于 GPU 加速）
- **视觉模型**: MiniCPM-V-4_5 (位于 `models/OpenBMB/MiniCPM-V-4_5/`)
- **Node.js**: 16+ (用于前端开发)
- **Conda**: 推荐使用 conda 管理 Python 环境

---

## 安装依赖

### Python 依赖

```bash
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python fastapi uvicorn requests transformers>=4.51.0 torch
```

### 前端依赖

```bash
cd frontend/ui-app
npm install
```

---

## 项目结构

```
privacy_agent_project/
├── api_server.py               # FastAPI HTTP 服务 (端口 8001)
│
├── model_server/
│   └── minicpm_api.py          # MiniCPM-V 视觉模型 API (端口 8000)
│   └── requirements.txt         # 模型服务依赖
│
├── frontend/
│   └── ui-app/                  # React 前端应用
│       └── package.json
│
├── models/                      # 模型文件目录
│   └── OpenBMB/
│       └── MiniCPM-V-4_5/       # 视觉理解模型 (~16.5GB)
│
├── skills/                      # Skills 模块
│   ├── smart_masker.py          # 视觉打码模块
│   ├── behavior_monitor.py      # 行为监控模块
│   └── evolution_mechanic.py    # 自进化机制
│
├── memory/                      # 记忆存储
│   ├── chroma_manager.py        # ChromaDB 管理器
│   └── chroma_storage/           # ChromaDB 数据库文件
│
├── prompts/                    # Prompt 模板
│
├── docs/                       # 架构文档
│   ├── ARCHITECTURE.md         # 系统架构文档
│   ├── SKILLS_API.md           # Skills API 文档
│   ├── RAG_SCHEMA.md           # RAG 数据模式
│   └── PROMPT_TEMPLATES.md     # Prompt 模板文档
│
├── temp/                       # 临时文件目录
├── logs/                       # 日志目录
│
├── autoglm_server.py           # Windows 端 AutoGLM 服务
├── demo.py                      # API 测试演示脚本
├── run_with_privacy.sh         # 隐私保护启动脚本
└── README.md                   # 本文件
```

---

## 完整操作流程

### 步骤 1：启动模型服务 (端口 8000)

首先启动 MiniCPM-V 视觉模型 API 服务：

```bash
cd model_server
python minicpm_api.py
```

服务启动后，将监听端口 8000。

---

### 步骤 2：启动隐私代理服务 (端口 8001)

在新的终端窗口中启动隐私代理 HTTP 服务：

```bash
python api_server.py
```

服务启动后，将监听端口 8001。

---

### 步骤 3：验证服务运行状态

使用 curl 命令检查服务是否正常运行：

```bash
curl http://127.0.0.1:8001/
```

正常情况下会返回服务状态信息。

---

### 步骤 4：重启隐私代理服务（如需）

如果服务需要重启，先杀掉旧进程再启动：

```bash
# 杀掉占用 8001 端口的进程（进程号根据实际情况修改）
kill 90176

# 重新启动服务
python api_server.py
```

---

### 步骤 5：启动前端应用

在新的终端窗口中启动 React 前端：

```bash
cd frontend/ui-app
npm run dev
```

前端启动后，通常监听本地端口（如 3000 或 5173），可通过浏览器访问。

---

## Windows 本地开发配置

### 激活 Conda 环境

```bash
conda activate autoglm
```

### 启动 AutoGLM 服务

在 Windows 命令行中启动本地服务：

```bash
python autoglm_server.py
```

### 关闭 SSH 连接

如需关闭 SSH 连接，在 Windows 命令行执行：

```bash
taskkill /f /im ssh.exe
```

---

## SSH 端口映射配置

### 方式一：映射 8001 端口到本地

在 Windows CMD 中执行，将服务器的 8001 端口映射到本地 8001：

```bash
ssh -L 8001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -N
```

### 方式二：完整双端口映射

需要同时映射两个端口时，执行以下两条命令：

**Windows 命令行 1**（映射 8001 端口）：

```bash
ssh -L 9001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -p 36647 -N
```

**Windows 命令行 2**（映射 28080 端口）：

```bash
ssh -R 28080:127.0.0.1:28080 root@connect.bjb1.seetacloud.com -p 36647 -N
```

---

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

---

## 隐私规则格式

规则存储在 `memory/chroma_storage/rules.json` 中：

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

---

## Skills 核心模块

| 模块 | 功能描述 |
|------|----------|
| `PII_Detection` | 检测图片中的个人隐私信息（手机号、身份证、银行卡等） |
| `Visual_Obfuscation` | 对敏感区域进行智能视觉打码 |
| `Behavior_Monitor` | 监控用户纠错行为，记录反馈数据 |
| `Skill_Evolution` | 根据用户反馈自进化生成新的防御规则 |

---

## 工作流程

```
用户截图
    ↓
┌─────────────────────────────────────────┐
│  1. ChromaDB 检索规则 (Self-RAG)        │
│  2. MiniCPM-V 分析隐私信息              │
│  3. Smart Masker 视觉打码              │
└─────────────────────────────────────────┘
    ↓
返回脱敏后的截图 → 发送给云端 Agent
```

---

## 快速启动脚本

使用一键启动脚本（需先赋予执行权限）：

```bash
chmod +x run_with_privacy.sh
./run_with_privacy.sh
```

---

## 文档索引

- [系统架构文档](docs/ARCHITECTURE.md)：了解系统整体设计与端云协同架构
- [Skills API 文档](docs/SKILLS_API.md)：四大核心 Skills 的输入输出契约
- [RAG 数据模式](docs/RAG_SCHEMA.md)：ChromaDB 向量数据库的存储范式
- [Prompt 模板](docs/PROMPT_TEMPLATES.md)：端侧 LLM 推理与代码生成的模板
- [Agent 行为约束](AGENTS.md)：LLM 调度 Skills 的核心原则

---

## 故障排查

### 端口被占用

```bash
# 查看端口占用情况
lsof -i :8001

# 杀掉占用进程
kill -9 <PID>
```

### 模型文件缺失

确保已将 MiniCPM-V-4_5 模型文件放置在 `models/OpenBMB/MiniCPM-V-4_5/` 目录。

### 前端启动失败

```bash
cd frontend/ui-app
rm -rf node_modules package-lock.json
npm install
```
