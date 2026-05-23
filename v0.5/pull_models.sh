#!/bin/bash
# V0.7 Ollama 模型预热脚本
# 容器启动时自动拉取所需模型

set -e

echo "正在拉取 Ollama 模型..."

# 拉取对话模型
echo "拉取 qwen3.5:4b..."
ollama pull qwen3.5:4b

# 拉取嵌入模型
echo "拉取 bge-m3..."
ollama pull bge-m3

echo "模型预热完成，启动 Ollama 服务..."

# 启动 Ollama 服务
exec ollama serve