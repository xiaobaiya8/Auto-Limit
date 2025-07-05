#!/bin/bash

# 启动脚本 - 处理权限问题并启动应用

echo "=== Auto-Limit 容器启动 ==="

# 检查数据目录权限
DATA_DIR=${DATA_DIR:-/app/data}
echo "检查数据目录: $DATA_DIR"

# 确保数据目录存在
if [ ! -d "$DATA_DIR" ]; then
    echo "创建数据目录: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# 获取当前用户信息
CURRENT_USER=$(whoami)
echo "当前用户: $CURRENT_USER"

# 检查是否有写入权限
if [ ! -w "$DATA_DIR" ]; then
    echo "警告: 数据目录没有写入权限"
    echo "尝试修复权限..."
    
    # 如果是 root 用户，修复权限后切换到 appuser
    if [ "$CURRENT_USER" = "root" ]; then
        chown -R appuser:appuser "$DATA_DIR"
        echo "权限已修复，切换到 appuser 运行应用"
        exec su appuser -c "python run.py"
    else
        echo "当前用户无权限修复目录权限"
        echo "建议使用以下命令修复主机目录权限:"
        echo "sudo chown -R 1000:1000 /mnt/user/appdata/auto-limit"
        echo ""
        echo "或者以 root 用户运行容器:"
        echo "docker run --user root ..."
        echo ""
        echo "继续以当前权限启动，可能无法保存配置..."
    fi
fi

# 启动应用
echo "启动 Auto-Limit 应用..."
exec python run.py 