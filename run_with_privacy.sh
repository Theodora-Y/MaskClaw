#!/bin/bash
# =============================================================================
# 隐私保护前置代理启动脚本
# 使用方式: bash run_with_privacy.sh [手机端执行的任务]
# 示例: bash run_with_privacy.sh "打开淘宝，搜索耳机"
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  隐私保护前置代理 - 启动脚本${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# -----------------------------------------------------------------------------
# 配置项（根据你的环境修改）
# -----------------------------------------------------------------------------
export MINICPM_API_URL="http://127.0.0.1:8000/chat"     # MiniCPM API 地址
export PHONE_AGENT_BASE_URL="http://127.0.0.1:8000/v1"   # 云端 Agent API 地址
export PHONE_AGENT_MODEL="autoglm-phone-9b"
export PHONE_AGENT_API_KEY="EMPTY"
export PHONE_AGENT_MAX_STEPS=50

# ADB 设备 ID（如果只有一个设备，可以留空自动选择）
export PHONE_AGENT_DEVICE_ID=""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# -----------------------------------------------------------------------------
# Step 1: 检查 MiniCPM API 服务
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 1] 检查 MiniCPM API 服务...${NC}"

if curl -s --max-time 2 "$MINICPM_API_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MiniCPM API 服务已运行: $MINICPM_API_URL${NC}"
else
    echo -e "${RED}❌ MiniCPM API 服务未运行${NC}"
    echo -e "${YELLOW}请先启动 MiniCPM API 服务:${NC}"
    echo "  cd $PROJECT_ROOT/model_server"
    echo "  python minicpm_api.py"
    echo ""
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 2: 检查 ADB 连接
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 2] 检查 ADB 设备连接...${NC}"

if [ -z "$PHONE_AGENT_DEVICE_ID" ]; then
    DEVICES=$(adb devices | grep -E "^[a-zA-Z0-9]+" | grep -v "List" | wc -l)
    if [ "$DEVICES" -eq 0 ]; then
        echo -e "${RED}❌ 未检测到 ADB 设备${NC}"
        echo -e "${YELLOW}请确保手机已通过 USB 连接并开启 USB 调试${NC}"
        exit 1
    elif [ "$DEVICES" -gt 1 ]; then
        echo -e "${YELLOW}检测到多个设备，请指定设备 ID:${NC}"
        adb devices
        echo -e "${YELLOW}使用方式: PHONE_AGENT_DEVICE_ID=设备ID $0 $@${NC}"
        exit 1
    fi
    PHONE_AGENT_DEVICE_ID=$(adb devices | grep -E "^[a-zA-Z0-9]+" | grep -v "List" | awk '{print $1}')
fi

echo -e "${GREEN}✅ ADB 设备已连接: $PHONE_AGENT_DEVICE_ID${NC}"

# -----------------------------------------------------------------------------
# Step 3: 安装隐私代理 Hook
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 3] 安装隐私代理 Hook...${NC}"

# 安装 Hook（一次性操作）
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from proxy_agent import install_hook
install_hook()
print('✅ Hook 安装成功')
"

# -----------------------------------------------------------------------------
# Step 4: 运行云端 Agent
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 4] 启动云端 Agent...${NC}"
echo ""

# 传递所有参数给 main.py
cd "$PROJECT_ROOT/Open-AutoGLM-main"

# 设置环境变量
export PHONE_AGENT_BASE_URL
export PHONE_AGENT_MODEL
export PHONE_AGENT_API_KEY
export PHONE_AGENT_MAX_STEPS
export PHONE_AGENT_DEVICE_ID

# 运行 Agent
python3 main.py "$@"
