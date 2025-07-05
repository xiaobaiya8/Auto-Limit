from flask import Flask, request, session
from flask_babel import Babel, get_locale
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
        # 国际化配置
        LANGUAGES=['zh', 'en'],
        BABEL_DEFAULT_LOCALE='zh',
        BABEL_DEFAULT_TIMEZONE='UTC'
    )

    # 确保数据目录存在
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # 定义语言选择器函数
    def locale_selector():
        # 1. 如果用户手动选择了语言，使用用户选择的语言
        if 'language' in session:
            return session['language']
        # 2. 否则根据浏览器的Accept-Language头部自动选择
        return request.accept_languages.best_match(app.config['LANGUAGES']) or app.config['BABEL_DEFAULT_LOCALE']

    # 初始化Babel，传入语言选择器
    babel = Babel(app, locale_selector=locale_selector)

    # 注册模板上下文处理器，使国际化函数在模板中可用
    @app.context_processor
    def inject_conf_vars():
        from flask_babel import get_locale
        return {
            'get_locale': get_locale,
            'LANGUAGES': app.config['LANGUAGES']
        }

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