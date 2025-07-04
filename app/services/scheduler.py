import importlib
from threading import Timer, RLock
from flask import current_app
from .config_manager import config_manager
from .log_manager import log_manager

class Scheduler:
    """
    负责动态加载插件、定时检查状态和更新速率的核心调度器。
    支持每个媒体服务器实例独立的轮询间隔。
    """
    def __init__(self):
        self.timers = {}  # 存储每个媒体服务器的定时器 {server_id: timer}
        self.active_session_ids = set()  # 所有活跃会话的合并集合
        self.running = False
        self.lock = RLock()
        self.app = None

    def init_app(self, app):
        """用Flask app实例来初始化调度器"""
        self.app = app

    def start(self):
        """启动调度器的主循环"""
        if self.app is None:
            raise RuntimeError("Scheduler has not been initialized. Call init_app(app) first.")

        with self.app.app_context():
            with self.lock:
                if not self.running:
                    self.running = True
                    log_manager.log_event("SCHEDULER", "调度器已启动")
                    self._schedule_all_servers()

    def stop(self):
        """停止调度器"""
        with self.lock:
            # 取消所有定时器
            for timer in self.timers.values():
                if timer:
                    timer.cancel()
            self.timers.clear()
            self.running = False
        
        # 仅在app上下文可用时记录日志
        if self.app:
            with self.app.app_context():
                log_manager.log_event("SCHEDULER", "调度器已停止")

    def restart(self):
        """重启调度器以应用新配置"""
        self.stop()
        self.start()

    def _schedule_all_servers(self):
        """为所有启用的媒体服务器创建独立的定时器"""
        if not self.running:
            return
            
        settings = config_manager.get_settings()
        
        # 清理已有的定时器
        with self.lock:
            for timer in self.timers.values():
                if timer:
                    timer.cancel()
            self.timers.clear()
        
        # 为每个启用的媒体服务器创建定时器
        for server_instance in settings.get('media_servers', []):
            if server_instance.get('enabled'):
                server_id = server_instance.get('id')
                poll_interval = float(server_instance.get('poll_interval', 15))
                
                if server_id and self.running:
                    timer = Timer(poll_interval, self._check_server_status, args=[server_id])
                    timer.daemon = True
                    self.timers[server_id] = timer
                    timer.start()
                    
                    log_manager.log_event("SCHEDULER", 
                        f"为服务器 {server_instance.get('name', server_id)} 设置 {poll_interval} 秒轮询间隔")

    def _check_server_status(self, server_id):
        """检查单个媒体服务器的状态"""
        if not self.running or self.app is None:
            return

        with self.app.app_context():
            settings = config_manager.get_settings()
            
            # 找到对应的服务器实例
            server_instance = None
            for server in settings.get('media_servers', []):
                if server.get('id') == server_id and server.get('enabled'):
                    server_instance = server
                    break
            
            if not server_instance:
                # 服务器已被删除或禁用
                with self.lock:
                    if server_id in self.timers:
                        del self.timers[server_id]
                return
            
            # 获取该服务器的活跃会话
            media_server = self._get_plugin_instance('media_servers', server_instance)
            if media_server:
                current_sessions = media_server.get_active_sessions()
                
                # 计算该服务器的会话ID
                server_session_ids = set()
                if current_sessions:
                    for session in current_sessions:
                        session['source_server'] = server_instance.get('name', server_id)
                        server_session_ids.add(f"{server_id}:{session['session_id']}")
                
                # 更新全局活跃会话集合
                with self.lock:
                    # 移除该服务器之前的会话
                    old_server_sessions = {sid for sid in self.active_session_ids if sid.startswith(f"{server_id}:")}
                    self.active_session_ids.difference_update(old_server_sessions)
                    
                    # 添加该服务器的新会话
                    self.active_session_ids.update(server_session_ids)
                    
                    # 检查是否需要更新下载器速率
                    total_sessions = len(self.active_session_ids)
                    if old_server_sessions != server_session_ids:
                        if total_sessions > 0:
                            log_manager.log_event("PLAY_STATUS", f"检测到 {total_sessions} 个总活跃播放")
                        else:
                            log_manager.log_event("PLAY_STATUS", "所有播放已停止")
                        
                        self._update_speed(settings)
            
            # 重新安排下次检查
            if self.running:
                poll_interval = float(server_instance.get('poll_interval', 15))
                timer = Timer(poll_interval, self._check_server_status, args=[server_id])
                timer.daemon = True
                with self.lock:
                    self.timers[server_id] = timer
                timer.start()

    def check_status(self):
        """为了保持向后兼容而保留的方法，现在只是触发重新调度"""
        self._schedule_all_servers()

    def _get_plugin_instance(self, plugin_type_plural, instance_config):
        """根据实例配置动态加载并实例化插件"""
        plugin_type_single = instance_config.get("type")
        if not plugin_type_single:
            log_manager.log_event("PLUGIN_ERROR", f"实例配置缺少'type'字段: {instance_config}")
            return None
        try:
            # e.g., 'app.media_servers.emby'
            module_name = f'app.{plugin_type_plural}.{plugin_type_single}'
            
            # 特殊处理一些插件的类名
            class_name_mapping = {
                'clouddrive2': 'CloudDrive2',
                'qbittorrent': 'Qbittorrent',
                'transmission': 'Transmission'
            }
            
            if plugin_type_single in class_name_mapping:
                class_name = class_name_mapping[plugin_type_single]
            else:
                # e.g., 'Emby'
                class_name = ''.join(word.capitalize() for word in plugin_type_single.split('_'))
            
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            
            return plugin_class(instance_config)

        except (ImportError, AttributeError) as e:
            log_manager.log_event("PLUGIN_ERROR", f"加载插件 {plugin_type_single} 失败: {e}")
            return None

    def _update_speed(self, settings):
        """根据播放状态更新所有已启用下载器的速率"""
        # 遍历所有已启用的下载器实例并应用各自的速率设置
        for downloader_instance in settings.get('downloaders', []):
            if downloader_instance.get('enabled'):
                downloader = self._get_plugin_instance('downloaders', downloader_instance)
                if downloader:
                    # 根据是否有播放活动确定要使用的速率
                    if len(self.active_session_ids) > 0:
                        # 使用播放时的速率
                        dl_limit = downloader_instance.get('backup_download_limit', 1024)
                        ul_limit = downloader_instance.get('backup_upload_limit', 512)
                    else:
                        # 使用默认速率
                        dl_limit = downloader_instance.get('default_download_limit', 0)
                        ul_limit = downloader_instance.get('default_upload_limit', 0)
                    
                    downloader.set_speed_limits(dl_limit, ul_limit)

scheduler = Scheduler() 