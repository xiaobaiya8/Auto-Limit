import re
import uuid
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from .services.config_manager import config_manager
from .services.log_manager import log_manager
from .services.scheduler import scheduler

main = Blueprint('main', __name__)

@main.route('/')
def index():
    settings = config_manager.get_settings()
    return render_template('index.html', settings=settings)

def parse_form_data(form_data):
    """
    解析来自配置页面的动态表单数据。
    表单字段命名格式应为: list_name[index][field_name]
    例如: media_servers[0][name]
    """
    parsed = {}
    for key, value in form_data.items():
        match = re.match(r'(\w+)\[(\d+)\]\[(\w+)\]', key)
        if match:
            list_name, index, field = match.groups()
            index = int(index)
            
            if list_name not in parsed:
                parsed[list_name] = []
            
            # 确保列表足够长
            while len(parsed[list_name]) <= index:
                parsed[list_name].append({})
            
            parsed[list_name][index][field] = value
        else:
            # 处理非动态字段，例如 rates[default_download_limit]
            match_simple = re.match(r'(\w+)\[(\w+)\]', key)
            if match_simple:
                group, field = match_simple.groups()
                if group not in parsed:
                    parsed[group] = {}
                parsed[group][field] = value

    # 将 "on" 转换为布尔值
    for list_name in ['media_servers', 'downloaders']:
        if list_name in parsed:
            for item in parsed[list_name]:
                item['enabled'] = 'enabled' in item

    return parsed

@main.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        form_data = request.form.to_dict()
        new_settings = parse_form_data(form_data)

        # 获取当前的settings，主要是为了保留rates和scheduler
        settings = config_manager.get_settings()
        
        # 清理已删除的实例并更新或添加新实例
        for instance_type in ['media_servers', 'downloaders']:
            updated_list = []
            form_list = new_settings.get(instance_type, [])
            for item in form_list:
                if item.get('deleted') != 'true':
                    if not item.get('id') or 'INDEX' in item.get('id'):
                        item['id'] = str(uuid.uuid4()) # 为新实例分配ID
                    updated_list.append(item)
            settings[instance_type] = updated_list
        
        # 更新通用设置
        if 'rates' in new_settings:
            for key, value in new_settings['rates'].items():
                 settings['rates'][key] = int(value) if value.isdigit() else 0
        if 'scheduler' in new_settings:
             for key, value in new_settings['scheduler'].items():
                 settings['scheduler'][key] = int(value) if value.isdigit() else 15

        config_manager.save_settings(settings)
        log_manager.log_event("CONFIG", "配置已更新，调度器将重启以应用新设置")
        scheduler.restart()
        return redirect(url_for('main.index'))
    
    settings = config_manager.get_settings()
    # 为模板提供一些上下文，例如可用的插件类型
    available_plugins = {
        'media_servers': ['emby', 'jellyfin', 'plex'],
        'downloaders': ['qbittorrent', 'transmission', 'clouddrive2']
    }
    return render_template('config.html', settings=settings, available_plugins=available_plugins)

@main.route('/logs')
def logs_page():
    logs = log_manager.get_logs()
    return render_template('logs.html', logs=logs)

@main.route('/api/status')
def api_status():
    return jsonify({
        'active_sessions': len(scheduler.active_session_ids),
        'sessions': list(scheduler.active_session_ids),
        'running': scheduler.running
    })

@main.route('/test_connection', methods=['POST'])
def test_connection():
    """通用的插件连接测试路由，通过POST请求接收实例配置"""
    instance_config = request.json.get('instance_config', {})
    plugin_type_plural = request.json.get('instance_type', '') # media_servers or downloaders

    if not instance_config or not plugin_type_plural:
        return jsonify({'status': 'error', 'message': '无效的请求'}), 400

    instance = scheduler._get_plugin_instance(plugin_type_plural, instance_config)
    if not instance:
        return jsonify({'status': 'error', 'message': f'无法加载插件 {instance_config.get("type")}'}), 404
        
    success, message = instance.test_connection()
    
    plugin_name = instance_config.get("type", "UNKNOWN").upper()
    log_event_type = f"TEST_{plugin_name}"
    if success:
        log_manager.log_event(log_event_type, f"连接测试成功: {message}")
        return jsonify({'status': 'success', 'message': f'连接成功: {message}'})
    else:
        log_manager.log_event(f"{log_event_type}_ERROR", f"连接测试失败: {message}")
        return jsonify({'status': 'error', 'message': f'连接失败: {message}'}), 400

@main.route('/api/media_server/sessions')
def api_media_server_sessions():
    sessions = []
    total_sessions = 0
    settings = config_manager.get_settings()

    for server_instance in settings.get('media_servers', []):
        if server_instance.get('enabled'):
            media_server = scheduler._get_plugin_instance('media_servers', server_instance)
            if media_server:
                current_sessions = media_server.get_active_sessions()
                if current_sessions:
                    # 为每个会话添加来源服务器信息
                    for session in current_sessions:
                        session['source_server'] = server_instance.get('name', server_instance.get('id', '未知服务器'))
                    sessions.extend(current_sessions)
                    total_sessions += len(current_sessions)
    
    if sessions:
        return jsonify({'status': 'success', 'sessions': sessions, 'count': total_sessions})
    else:
        return jsonify({'status': 'success', 'sessions': [], 'count': 0})

@main.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy' if scheduler.running else 'unhealthy',
        'timestamp': __import__('time').time(),
        'monitoring': 'active' if scheduler.running else 'inactive'
    }), 200 if scheduler.running else 503

@main.route('/save_instance', methods=['POST'])
def save_instance():
    """保存单个实例配置"""
    try:
        instance_config = request.json.get('instance_config', {})
        instance_type = request.json.get('instance_type', '')
        
        if not instance_config or not instance_type:
            return jsonify({'status': 'error', 'message': '无效的请求数据'}), 400
        
        # 获取当前设置
        settings = config_manager.get_settings()
        
        # 确保实例类型存在
        if instance_type not in settings:
            settings[instance_type] = []
        
        # 查找现有实例或创建新实例
        instance_id = instance_config.get('id')
        found_index = -1
        
        if instance_id and 'INDEX' not in instance_id:
            # 查找现有实例
            for i, existing in enumerate(settings[instance_type]):
                if existing.get('id') == instance_id:
                    found_index = i
                    break
        
        # 为新实例生成ID
        if not instance_id or 'INDEX' in instance_id:
            instance_config['id'] = str(uuid.uuid4())
            instance_id = instance_config['id']
        
        # 数据类型转换
        instance_config['enabled'] = instance_config.get('enabled', False)
        
        # 为下载器处理限速设置
        if instance_type == 'downloaders':
            for rate_field in ['default_download_limit', 'default_upload_limit', 'backup_download_limit', 'backup_upload_limit']:
                value = instance_config.get(rate_field, 0)
                instance_config[rate_field] = int(value) if str(value).isdigit() else 0
        
        # 为媒体服务器处理轮询间隔设置
        if instance_type == 'media_servers':
            poll_interval = instance_config.get('poll_interval', 15)
            instance_config['poll_interval'] = int(poll_interval) if str(poll_interval).isdigit() and int(poll_interval) >= 5 else 15
        
        # 更新或添加实例
        if found_index >= 0:
            settings[instance_type][found_index] = instance_config
            log_manager.log_event("CONFIG", f"更新了{instance_config.get('name', '未命名')}实例配置")
        else:
            settings[instance_type].append(instance_config)
            log_manager.log_event("CONFIG", f"添加了新的{instance_config.get('name', '未命名')}实例")
        
        # 保存设置
        if config_manager.save_settings(settings):
            # 重启调度器以应用新配置
            scheduler.restart()
            return jsonify({
                'status': 'success', 
                'message': '实例配置保存成功',
                'instance_id': instance_id
            })
        else:
            return jsonify({'status': 'error', 'message': '保存配置文件失败'}), 500
            
    except Exception as e:
        current_app.logger.error(f"保存实例配置时出错: {e}")
        return jsonify({'status': 'error', 'message': f'保存失败: {str(e)}'}), 500


@main.route('/delete_instance', methods=['POST'])
def delete_instance():
    """删除单个实例配置"""
    try:
        instance_id = request.json.get('instance_id', '')
        instance_type = request.json.get('instance_type', '')
        
        if not instance_id or not instance_type:
            return jsonify({'status': 'error', 'message': '无效的请求数据'}), 400
        
        # 获取当前设置
        settings = config_manager.get_settings()
        
        # 确保实例类型存在
        if instance_type not in settings:
            return jsonify({'status': 'error', 'message': '实例类型不存在'}), 404
        
        # 查找并删除实例
        found_index = -1
        instance_name = '未知实例'
        
        for i, existing in enumerate(settings[instance_type]):
            if existing.get('id') == instance_id:
                found_index = i
                instance_name = existing.get('name', '未命名')
                break
        
        if found_index >= 0:
            # 删除实例
            settings[instance_type].pop(found_index)
            
            # 保存设置
            if config_manager.save_settings(settings):
                log_manager.log_event("CONFIG", f"删除了{instance_name}实例")
                # 重启调度器以应用新配置
                scheduler.restart()
                return jsonify({
                    'status': 'success', 
                    'message': '实例删除成功'
                })
            else:
                return jsonify({'status': 'error', 'message': '保存配置文件失败'}), 500
        else:
            return jsonify({'status': 'error', 'message': '未找到要删除的实例'}), 404
            
    except Exception as e:
        current_app.logger.error(f"删除实例配置时出错: {e}")
        return jsonify({'status': 'error', 'message': f'删除失败: {str(e)}'}), 500

 