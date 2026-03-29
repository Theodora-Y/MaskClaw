FROM python:3.11-slim

WORKDIR /app

# ── API 服务依赖 ──────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 模型服务依赖（与 API 部分重叠）──────────────────────────
COPY model_server/requirements.txt ./model_requirements.txt
RUN pip install --no-cache-dir -r model_requirements.txt || true

# ── 复制项目代码 ──────────────────────────────────────────────
COPY . .

# ── 统一入口脚本 ──────────────────────────────────────────────
COPY <<'EOF' /usr/local/bin/start.sh
#!/bin/bash
set -e

# 启动模型服务（后台）
echo "[start] launching model service on :8000 ..."
python model_server/minicpm_api.py &
MODEL_PID=$!

# 等待模型服务就绪
sleep 3

# 启动 API 服务
echo "[start] launching API service on :8001 ..."
exec python api_server.py
EOF
RUN chmod +x /usr/local/bin/start.sh

EXPOSE 8000 8001

CMD ["/usr/local/bin/start.sh"]
