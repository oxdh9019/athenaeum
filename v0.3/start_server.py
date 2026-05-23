#!/usr/bin/env python3
"""
启动脚本 - 从项目根目录运行
"""

import os
import sys
import subprocess

# 设置工作目录为项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 设置环境变量
os.environ["PYTHONPATH"] = os.getcwd()

# 设置使用本地 Ollama（取消注释下面一行以启用）
# os.environ["USE_OLLAMA"] = "true"

# 检查是否设置了 USE_OLLAMA 环境变量
use_ollama = os.environ.get("USE_OLLAMA", "").lower() in ("1", "true", "yes")

# 如果没有设置，询问用户或默认使用本地 Ollama
if not use_ollama:
    # 默认使用本地 Ollama
    os.environ["USE_OLLAMA"] = "true"
    print("[Start] 默认使用本地 Ollama (设置 USE_OLLAMA=false 可切换到云端 LLM)")

# 启动 uvicorn
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "server.api.server:app",
    "--host", "0.0.0.0",
    "--port", "8000"
])
