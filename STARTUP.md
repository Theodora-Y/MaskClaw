# 启动方式

## 方式一：一键启动（推荐）

```bash
cd privacy_agent_project
bash run_all.sh
```

一键启动三个服务：
- 模型服务（端口 8000）
- API 服务（端口 8001）
- 前端 Vite（端口 5173）

> 脚本会自动检测端口占用，已运行的服务会跳过，避免重复启动。

停止服务：

```bash
bash stop_all.sh
```

---

## 方式二：手动分步启动

### 1. 启动模型服务

```bash
cd privacy_agent_project/model_server
python3 minicpm_api.py
```

等待输出 `[start] MiniCPM-o API ready on :8000`

### 2. 启动 API 服务

```bash
cd privacy_agent_project
python3 api_server.py
```

等待输出 `Uvicorn running on http://0.0.0.0:8001`

### 3. 启动前端

```bash
cd privacy_agent_project/frontend/ui-app
npm install    # 首次运行需要安装依赖
npm run dev
```

---

## 首次配置

首次启动后，运行脚本初始化演示账号和默认 Skill：

```bash
cd privacy_agent_project
python3 scripts/seed_skills_db.py
python3 scripts/generate_skills.py
```

---

## 演示账号

| 用户 | 邮箱 | 密码 | 职业 |
|:---|:---|:---|:---|
| demo_UserA | demo_usera@maskclaw.dev | demo1234 | 医疗顾问（医生） |
| demo_UserC | demo_userc@maskclaw.dev | demo1234 | 普通职员 |

---

## 模型服务

### Ollama 本地模型（轻量级，gemma:2b 等）

适用于资源有限的环境，gemma:2b 仅需约 1.4GB 显存：

```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. 下载模型
ollama pull gemma:2b

# 3. 启动 Ollama 服务（后台运行）
ollama serve &

# 4. 启动 API 代理（端口 8005）
cd privacy_agent_project/model_server
pip install httpx pydantic
python3 ollama_api.py
```

访问 `http://localhost:8005` 查看 API 文档。

### MiniCPM/Gemma4（高质量，资源密集）

适用于有 GPU 的服务器：

```bash
cd privacy_agent_project/model_server
pip install -r requirements.txt
python3 minicpm_api.py  # 端口 8000
```

### API 调用示例

```python
# 方式一：直接 HTTP
import requests
requests.post("http://localhost:8005/chat", json={
    "model": "gemma:2b",
    "messages": [{"role": "user", "content": "你好"}]
})

# 方式二：OpenAI SDK（兼容）
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8005/v1", api_key="ollama")
response = client.chat.completions.create(
    model="gemma:2b",
    messages=[{"role": "user", "content": "你好"}]
)
```

---

## 访问地址

- 前端：`http://localhost:5173`
- API 服务：`http://localhost:8001`
- Ollama API：`http://localhost:8005`
- MiniCPM API：`http://localhost:8000`

---

## 系统架构

```
云服务器（Python API + 模型服务 + 前端 Vite）
    │
    ├── 8001 ← Python API 服务
    ├── 8000 ← 模型服务（MiniCPM）
    └── 5173 ← 前端 Vite
            └── /autoglm/* → SSH 隧道 → 本地 Windows AutoGLM 后端（28080）
                                           └── USB ADB → 手机
```
