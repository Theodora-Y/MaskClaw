#!/bin/bash
# scripts/download_ollama_models.sh
# 下载 Ollama 模型到项目 models 文件夹
#
# 使用方法：
#   chmod +x scripts/download_ollama_models.sh
#   ./scripts/download_ollama_models.sh
#
# 前提条件：
#   1. 已安装 Ollama: https://ollama.com
#   2. Ollama 服务正在运行: ollama serve

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${PROJECT_ROOT}/models"

# Ollama 模型存放目录（设置为项目 models 文件夹）
export OLLAMA_MODELS="${MODELS_DIR}"

echo "=========================================="
echo "Ollama 模型下载脚本"
echo "=========================================="
echo "模型存放目录: ${OLLAMA_MODELS}"
echo ""

# 检查 Ollama 是否安装
if ! command -v ollama &> /dev/null; then
    echo "❌ 错误: Ollama 未安装"
    echo ""
    echo "请先安装 Ollama:"
    echo "  macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Windows:     https://ollama.com/download"
    echo ""
    echo "安装完成后，确保 Ollama 服务正在运行:"
    echo "  ollama serve"
    exit 1
fi

echo "✅ Ollama 已安装"

# 检查服务是否运行
if ! curl -s http://localhost:11434/api/version &> /dev/null; then
    echo "⚠️  Ollama 服务未运行，正在启动..."
    echo ""
    echo "请在新终端运行:"
    echo "  ollama serve"
    echo ""
    echo "或者后台运行:"
    echo "  nohup ollama serve > /dev/null 2>&1 &"
    exit 1
fi

echo "✅ Ollama 服务正在运行"
echo ""

# 列出当前已有的模型
echo "当前已下载的模型:"
echo "-------------------------------------------"
ollama list
echo ""

# 要下载的模型列表
MODELS=(
    "gemma:2b"
)

# 下载每个模型
for model in "${MODELS[@]}"; do
    echo "-------------------------------------------"
    echo "📥 正在下载: ${model}"
    echo "-------------------------------------------"
    ollama pull "${model}"
    echo "✅ ${model} 下载完成"
    echo ""
done

# 确认下载结果
echo "=========================================="
echo "✅ 下载完成！"
echo "=========================================="
echo ""
echo "最终模型列表:"
ollama list
echo ""
echo "模型存放位置: ${OLLAMA_MODELS}"
echo ""
echo "现在可以在代码中调用了:"
echo "  python model_server/ollama_example.py"
