FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个应用代码到镜像中
COPY . .

# 复制并设置启动脚本权限
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 创建非root用户
RUN adduser --disabled-password --gecos '' appuser

# 创建数据目录并设置正确权限
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV DATA_DIR=/app/data

# 注意：不切换用户，保持为 root，让启动脚本处理权限

# 暴露端口
EXPOSE 9190

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:9190/health || exit 1

# 启动命令
CMD ["/entrypoint.sh"] 