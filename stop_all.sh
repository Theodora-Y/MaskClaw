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
