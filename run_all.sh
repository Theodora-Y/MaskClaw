#!/bin/bash
# =============================================================================
# MaskClaw 一键启动脚本（强制重启版）
# 启动三个服务：模型服务(8000) + API服务(8001) + 前端(5173)
# 使用方式: bash run_all.sh
#
# 行为：
#   - 每次运行强制重启：检测到端口被占用则先 kill 再启动
#   - 日志直接写入 logs/{service}.log（覆盖）
#   - .pid 文件记录当前运行的 PID
# =============================================================================

# 注意：不使用 set -e，避免误退出。脚本内部通过条件判断处理错误。

# conda base Python（必须使用，包含 torch/chromadb 等依赖）
CONDA_PYTHON="/root/miniconda3/bin/python"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 日志文件（固定名称，覆盖写入）
LOG_MINICPM="$LOG_DIR/minicpm.log"
LOG_API="$LOG_DIR/api_server.log"
LOG_FRONTEND="$LOG_DIR/frontend.log"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  MaskClaw 一键启动${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# -----------------------------------------------------------------------------
# 辅助函数
# -----------------------------------------------------------------------------

# 杀掉占用指定端口的进程（通过 netstat 查找，始终返回 0）
kill_port() {
    local port=$1
    local killed=0

    # 用 netstat -tlnp 获取 PID（最可靠）
    local pids=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $NF}' | cut -d'/' -f1 | grep -E '^[0-9]+$' | sort -u || true)

    if [ -n "$pids" ]; then
        for pid in $pids; do
            [ -z "$pid" ] && continue
            if kill -0 "$pid" 2>/dev/null; then
                local cmdline=$(ps -p "$pid" -o cmd --no-headers 2>/dev/null || echo "unknown")
                echo -e "  ${YELLOW}⚠ 杀掉占用端口 $port 的进程 PID=$pid: $cmdline${NC}"
                kill -9 "$pid" 2>/dev/null || true
                killed=1
            fi
        done
        [ "$killed" = "1" ] && sleep 2
    fi

    return 0
}

# 杀掉已记录在 .pid 文件中的进程（如有）
kill_pid_file() {
    local pidfile=$1
    local name=$2
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${YELLOW}⚠ 杀掉旧 PID=$pid ($name)${NC}"
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
}

# 检查端口是否响应
check_port() {
    local port=$1
    curl -s --max-time 2 "http://127.0.0.1:$port/" > /dev/null 2>&1
}

# 等待端口就绪
wait_port() {
    local port=$1
    local name=$2
    local max_wait=${3:-10}
    for i in $(seq 1 $max_wait); do
        sleep 1
        if check_port $port; then
            return 0
        fi
    done
    return 1
}

# -----------------------------------------------------------------------------
# Step 0: 环境检查
# -----------------------------------------------------------------------------
echo -e "${CYAN}[Step 0] 环境检查${NC}"
echo ""

if [ -x "$CONDA_PYTHON" ]; then
    echo -e "  ${GREEN}✅ Python: $($CONDA_PYTHON --version 2>&1) [conda base]${NC}"
elif command -v python3 > /dev/null 2>&1; then
    echo -e "  ${RED}⚠ conda base 未找到，回退系统 Python: $(python3 --version 2>&1)${NC}"
else
    echo -e "  ${RED}❌ Python3 未安装${NC}"
    exit 1
fi

if command -v npm > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ npm: v$(npm --version 2>&1)${NC}"
else
    echo -e "  ${RED}❌ npm 未安装${NC}"
    exit 1
fi

if [ -d "frontend/ui-app/node_modules" ]; then
    echo -e "  ${GREEN}✅ 前端依赖已安装${NC}"
else
    echo -e "${YELLOW}⏳ 前端依赖未安装，正在安装...${NC}"
    cd frontend/ui-app
    npm install
    cd "$PROJECT_ROOT"
    echo -e "  ${GREEN}✅ 前端依赖安装完成${NC}"
fi

echo ""

# -----------------------------------------------------------------------------
# Step 1: 模型服务（8000端口）
# -----------------------------------------------------------------------------
echo -e "${CYAN}[Step 1] 启动模型服务（端口 8000）${NC}"

# 先尝试杀掉旧 PID 文件中的进程
kill_pid_file "$LOG_DIR/minicpm.pid" "模型服务"

# 如果端口仍被占用，强制杀掉
if check_port 8000; then
    echo -e "  ${YELLOW}⚠ 端口 8000 仍被占用，强制清理...${NC}"
    kill_port 8000
fi

    echo -e "  启动命令: cd model_server && $CONDA_PYTHON minicpm_api.py"
cd "$PROJECT_ROOT/model_server"
    nohup "$CONDA_PYTHON" minicpm_api.py > "$LOG_MINICPM" 2>&1 &
MODEL_PID=$!
echo $MODEL_PID > "$LOG_DIR/minicpm.pid"
cd "$PROJECT_ROOT"
echo -e "  ${YELLOW}⏳ 等待模型服务启动（PID=$MODEL_PID）...${NC}"

if wait_port 8000 "模型服务" 15; then
    echo -e "  ${GREEN}✅ 模型服务启动成功（PID: $MODEL_PID）${NC}"
else
    echo -e "  ${RED}❌ 模型服务启动超时，请检查 logs/minicpm.log${NC}"
    tail -20 "$LOG_MINICPM"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: API 服务（8001端口）
# -----------------------------------------------------------------------------
echo -e "${CYAN}[Step 2] 启动 API 服务（端口 8001）${NC}"

kill_pid_file "$LOG_DIR/api_server.pid" "API 服务"

if check_port 8001; then
    echo -e "  ${YELLOW}⚠ 端口 8001 仍被占用，强制清理...${NC}"
    kill_port 8001
fi

    echo -e "  启动命令: $CONDA_PYTHON api_server.py"
    nohup "$CONDA_PYTHON" api_server.py > "$LOG_API" 2>&1 &
API_PID=$!
echo $API_PID > "$LOG_DIR/api_server.pid"
echo -e "  ${YELLOW}⏳ 等待 API 服务启动（PID=$API_PID）...${NC}"

if wait_port 8001 "API 服务" 10; then
    echo -e "  ${GREEN}✅ API 服务启动成功（PID: $API_PID）${NC}"
else
    echo -e "  ${RED}❌ API 服务启动超时，请检查 logs/api_server.log${NC}"
    tail -20 "$LOG_API"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 3: 前端 Vite（5173端口）
# -----------------------------------------------------------------------------
echo -e "${CYAN}[Step 3] 启动前端 Vite（端口 5173）${NC}"

kill_pid_file "$LOG_DIR/frontend.pid" "前端服务"

if check_port 5173; then
    echo -e "  ${YELLOW}⚠ 端口 5173 仍被占用，强制清理...${NC}"
    kill_port 5173
fi

echo -e "  启动命令: cd frontend/ui-app && npm run dev"
cd "$PROJECT_ROOT/frontend/ui-app"
nohup npm run dev -- --host 0.0.0.0 --port 5173 > "$LOG_FRONTEND" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
cd "$PROJECT_ROOT"
echo -e "  ${YELLOW}⏳ 等待前端服务启动（PID=$FRONTEND_PID）...${NC}"

if wait_port 5173 "前端服务" 20; then
    echo -e "  ${GREEN}✅ 前端服务启动成功（PID: $FRONTEND_PID）${NC}"
else
    echo -e "  ${RED}❌ 前端服务启动超时，请检查 logs/frontend.log${NC}"
    tail -20 "$LOG_FRONTEND"
fi
echo ""

# -----------------------------------------------------------------------------
# 生成 stop_all.sh（覆盖写入）
# -----------------------------------------------------------------------------
cat > "$PROJECT_ROOT/stop_all.sh" << 'EOFSTOP'
#!/bin/bash
echo "正在停止 MaskClaw 服务..."
# 优先通过 .pid 文件停止
for pidfile in logs/*.pid; do
    if [ -f "$pidfile" ]; then
        NAME=$(basename "$pidfile" .pid)
        PID=$(cat "$pidfile")
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            echo "停止 $NAME (PID=$PID)..."
            kill "$PID" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
done
# 兜底：通过端口清理残余进程
for port in 8000 8001 5173; do
    if command -v lsof > /dev/null 2>&1; then
        for pid in $(lsof -ti :$port 2>/dev/null || true); do
            if kill -0 "$pid" 2>/dev/null; then
                echo "清理残余进程 PID=$pid (端口 $port)..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
    fi
done
echo "所有服务已停止"
EOFSTOP
chmod +x "$PROJECT_ROOT/stop_all.sh"

# -----------------------------------------------------------------------------
# 完成
# -----------------------------------------------------------------------------
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 启动完成！${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  前端地址:  ${CYAN}http://localhost:5173${NC}"
echo -e "  API 服务:  ${CYAN}http://localhost:8001${NC}"
echo -e "  模型服务:  ${CYAN}http://localhost:8000${NC}"
echo ""
echo -e "  演示账号:"
echo -e "    UserA:  ${CYAN}demo_usera@maskclaw.dev${NC} / demo1234"
echo -e "    UserC:  ${CYAN}demo_userc@maskclaw.dev${NC} / demo1234"
echo ""
echo -e "  日志文件:  ${CYAN}$LOG_DIR/minicpm.log${NC}"
echo -e "             ${CYAN}$LOG_DIR/api_server.log${NC}"
echo -e "             ${CYAN}$LOG_DIR/frontend.log${NC}"
echo ""
echo -e "${YELLOW}  停止服务: bash stop_all.sh${NC}"
echo ""

# 健康检查
echo -e "${CYAN}[健康检查]${NC}"
API_MSG=$(curl -s http://localhost:8001/ | python3 -c 'import sys,json; print(json.load(sys.stdin).get("message","未知"))' 2>/dev/null || echo "失败")
echo -e "  API 服务: $API_MSG"
echo ""
