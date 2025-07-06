from functools import wraps
from flask import session, redirect, url_for, request, jsonify, g
from .services.config_manager import config_manager

def init_auth(app):
    """初始化认证模块"""
    app.secret_key = app.config.get('SECRET_KEY', 'your-secret-key-change-this')
    
    @app.before_request
    def check_auth():
        """在每个请求前检查认证状态"""
        g.is_authenticated = is_authenticated()
        g.is_legacy_install = config_manager.is_legacy_install()
        g.auth_required = config_manager.is_auth_required()
        
        # 旧版本安装且无认证配置，重定向到设置页面
        if g.is_legacy_install and request.endpoint not in ['auth.setup', 'auth.setup_post', 'main.set_language', 'static']:
            return redirect(url_for('auth.setup'))
        
        # 需要认证但未登录的情况
        if g.auth_required and not g.is_authenticated:
            # API请求返回401
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'message': '需要登录'}), 401
            # 页面请求重定向到登录页面
            if request.endpoint not in ['auth.login', 'auth.login_post', 'main.set_language', 'static']:
                return redirect(url_for('auth.login'))

def is_authenticated():
    """检查用户是否已登录"""
    if not config_manager.is_auth_required():
        return True  # 如果不需要认证，则认为已认证
    
    return session.get('authenticated', False)

def login_required(f):
    """需要登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # API请求返回401
            if request.path.startswith('/api/'):
                return jsonify({'status': 'error', 'message': '需要登录'}), 401
            # 页面请求重定向到登录页面
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def login_user(username):
    """登录用户"""
    session['authenticated'] = True
    session['username'] = username
    session.permanent = True

def logout_user():
    """登出用户"""
    session.pop('authenticated', None)
    session.pop('username', None)

def get_current_user():
    """获取当前用户名"""
    return session.get('username') 