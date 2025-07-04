#!/usr/bin/env python3
import os
from app import create_app

# 使用应用工厂模式创建Flask应用
# 这使得我们可以在不同的配置下创建多个应用实例
app = create_app()

if __name__ == '__main__':
    # 从环境变量获取端口，默认为9190
    port = int(os.environ.get('PORT', 9190))
    # 启动Web服务器
    # `debug=True` 会在代码变更时自动重载，但在生产环境中应关闭
    app.run(host='0.0.0.0', port=port, debug=True) 