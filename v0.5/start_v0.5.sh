#!/bin/bash
# V0.5 服务器启动脚本

cd /Volumes/Ollama-Models/Athenaeum/v0.5

# 提示用户选择模式
echo "=========================================="
echo "  V0.5 记忆回廊 启动脚本"
echo "=========================================="
echo ""
echo "1) 使用 MiniMax API Key（云端对话摘要）"
echo "2) 仅使用本地 Ollama（无云端）"
echo ""
echo -n "请选择 [1/2]: "
read choice
echo ""

case $choice in
  1)
    echo "请输入 MiniMax API Key (输入后按回车):"
    read -s API_KEY
    echo ""
    if [ -n "$API_KEY" ]; then
      export ANTHROPIC_API_KEY="$API_KEY"
      export MINIMAX_API_KEY="$API_KEY"
      echo "API Key 已设置，将使用 MiniMax 云端 LLM"
      echo "  - 世界/角色/关系生成: MiniMax"
      echo "  - 对话/意图生成: 本地 Ollama"
      echo "  - 记忆摘要: MiniMax"
    else
      echo "未输入 API Key，将使用本地 Ollama"
      export USE_OLLAMA=1
    fi
    ;;
  2)
    export USE_OLLAMA=1
    echo "已选择纯本地模式"
    ;;
  *)
    echo "无效选择，将使用本地 Ollama"
    export USE_OLLAMA=1
    ;;
esac

echo ""
echo "构建前端..."
cd /Volumes/Ollama-Models/Athenaeum/v0.3/client
npm run build

echo ""
echo "启动服务器..."
cd /Volumes/Ollama-Models/Athenaeum/v0.5
source server/venv/bin/activate
cd server
python server.py
