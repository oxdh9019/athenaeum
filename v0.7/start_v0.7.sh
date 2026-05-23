#!/bin/bash
# V0.7 灵魂增强版启动脚本

cd /Volumes/Ollama-Models/Athenaeum/v0.7/server

echo "=========================================="
echo "  V0.7 灵魂增强版 启动脚本"
echo "=========================================="

# 检查并激活虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -q fastapi uvicorn pydantic httpx anthropic numpy 2>/dev/null

# 启动选项
echo ""
echo "选择运行模式:"
echo "1) 仅使用本地 Ollama（无云端）"
echo "2) 使用 MiniMax API Key（云端对话摘要）"
echo ""
read -p "请选择 [1/2, 默认1]: " choice
choice=${choice:-1}

export USE_OLLAMA=1

case $choice in
  2)
    echo "请输入 MiniMax API Key:"
    read -s API_KEY
    if [ -n "$API_KEY" ]; then
      export ANTHROPIC_API_KEY="$API_KEY"
      export MINIMAX_API_KEY="$API_KEY"
      export USE_OLLAMA=0
      echo "API Key 已设置，将使用云端 LLM"
    fi
    ;;
esac

echo ""
echo "启动服务器..."
echo "  API: http://localhost:8000"
echo "  Health: http://localhost:8000/health"
echo ""

python server.py