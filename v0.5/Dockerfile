# V0.7 后端 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY server/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY server/ /app/

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
CMD ["python", "server.py"]