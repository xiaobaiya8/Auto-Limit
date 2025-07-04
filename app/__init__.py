from flask import Flask
import os

from .services.config_manager import config_manager
from .services.log_manager import log_manager
from .services.scheduler import scheduler

def create_app():
    """
    创建并配置Flask应用实例。
    这是一个应用工厂函数，有助于创建多个应用实例（例如用于测试）。
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # 从环境变量或默认值加载配置
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key'),
        # 定义数据目录，所有配置文件将存储在这里
        DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'),
    )

    # 确保数据目录存在
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # 初始化服务管理器
    config_manager.init_app(app)
    log_manager.init_app(app)
    scheduler.init_app(app)

    # 注册蓝图
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # 启动后台调度器
    if not scheduler.running:
        scheduler.start()

    return app 