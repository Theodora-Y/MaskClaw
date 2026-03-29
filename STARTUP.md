# 启动方式

## Docker 方式（一行命令，推荐）

```bash
docker-compose up --build
```

启动后：
- API 服务：http://localhost:8001
- 模型服务：http://localhost:8000
- 前端：http://localhost:5173

## 手动方式

### 1. 启动模型服务
```bash
cd /path/to/privacy_agent_project
python model_server/minicpm_api.py
```
等待输出 `[start] MiniCPM-o API ready on :8000`

### 2. 启动 API 服务
```bash
python api_server.py
```
等待输出 `Uvicorn running on http://0.0.0.0:8001`

### 3. 启动前端
```bash
cd frontend/ui-app
npm install
npm run dev
```

## 首次配置

首次启动后，运行脚本初始化演示账号和默认 Skill：

```bash
# 初始化演示账号
python -c "
import sqlite3, hashlib, time
conn = sqlite3.connect('maskclaw.db')
pw = hashlib.sha256('demo1234'.encode()).hexdigest()
conn.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)',
    ('demo_UserA','demo_usera@maskclaw.dev',pw,'张医生','医疗顾问',1,0))
conn.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)',
    ('demo_UserC','demo_userc@maskclaw.dev',pw,'王明','普通职员',1,0))
conn.commit()
conn.close()
print('demo accounts seeded')
"

# 初始化默认 Skills
python scripts/seed_skills_db.py
python scripts/generate_skills.py
```

演示账号：
- 邮箱：`demo_usera@maskclaw.dev` / `demo_userc@maskclaw.dev`
- 密码：`demo1234`
