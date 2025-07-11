import importlib
from threading import Timer, RLock
from time import time
from flask import current_app
from flask_babel import _
from .config_manager import config_manager
from .log_manager import log_manager
from ..utils import should_skip_speed_limit

class Scheduler:
    """
    负责动态加载插件、定时检查状态和更新速率的核心调度器。
    支持每个媒体服务器实例独立的轮询间隔。
    """
    def __init__(self):
        self.timers = {}  # 存储每个媒体服务器的定时器 {server_id: timer}
        self.active_session_ids = set()  # 所有活跃会话的合并集合
        self.last_speed_state = {}  # 记录每个下载器的最后速率状态 {downloader_id: (dl_limit, ul_limit)}
        self.last_session_count = 0  # 记录上次的会话数量
        self.last_status_log_time = 0  # 上次记录状态日志的时间
        self.last_skip_log_time = {}  # 记录每个用户上次跳过日志的时间 {user_name: timestamp}
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
                    log_manager.log_event("SCHEDULER", _("调度器已启动"))
                    self._schedule_all_servers()

    def stop(self):
        """停止调度器"""
        with self.lock:
            # 取消所有定时器
            for timer in self.timers.values():
                if timer:
                    timer.cancel()
            self.timers.clear()
            # 清理状态记录
            self.last_speed_state.clear()
            self.active_session_ids.clear()
            self.last_session_count = 0
            self.last_status_log_time = 0
            self.last_skip_log_time.clear()
            self.running = False
        
        # 仅在app上下文可用时记录日志
        if self.app:
            with self.app.app_context():
                log_manager.log_event("SCHEDULER", _("调度器已停止"))

    def restart(self):
        """重启调度器以应用新配置"""
        # 保存当前的速率状态，避免重启后重复设置相同速率
        saved_speed_state = self.last_speed_state.copy()
        
        self.stop()
        self.start()
        
        # 恢复速率状态
        self.last_speed_state = saved_speed_state

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
                    
                    # 确保在应用上下文中记录日志
                    if self.app:
                        with self.app.app_context():
                            log_manager.log_formatted_event("SCHEDULER", 
                                _("为服务器 {0} 设置 {1} 秒轮询间隔"), 
                                server_instance.get('name', server_id), poll_interval)

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
                
                # 计算该服务器的会话ID（只计算不被跳过的会话）
                server_session_ids = set()
                current_time = time()
                skipped_count = 0
                
                if current_sessions:
                    for session in current_sessions:
                        session['source_server'] = server_instance.get('name', server_id)
                        session_id = f"{server_id}:{session['session_id']}"
                        
                        # 检查是否应该跳过此会话的限速
                        if should_skip_speed_limit(session, server_instance):
                            skipped_count += 1
                            # 减少SKIP_LIMIT日志频率：同一用户60秒内只记录一次
                            user_name = session.get('user_name', 'Unknown')
                            last_log_time = self.last_skip_log_time.get(user_name, 0)
                            if current_time - last_log_time > 60:  # 60秒间隔
                                reason = "本地播放" if session.get('client_ip') and session.get('client_ip') != '' else "白名单用户"
                                log_manager.log_formatted_event("SKIP_LIMIT", _("跳过限速 - 用户: {0}, 原因: {1}"), 
                                                               user_name, reason)
                                self.last_skip_log_time[user_name] = current_time
                        else:
                            server_session_ids.add(session_id)
                
                # 更新全局活跃会话集合
                with self.lock:
                    # 移除该服务器之前的会话
                    old_server_sessions = {sid for sid in self.active_session_ids if sid.startswith(f"{server_id}:")}
                    self.active_session_ids.difference_update(old_server_sessions)
                    
                    # 添加该服务器的新会话（不包括跳过的）
                    self.active_session_ids.update(server_session_ids)
                    
                    # 检查是否需要更新下载器速率和记录日志
                    total_sessions = len(self.active_session_ids)
                    session_changed = old_server_sessions != server_session_ids
                    count_changed = total_sessions != self.last_session_count
                    
                    # 只在会话数量实际变化或30秒无状态更新时记录日志
                    if session_changed and (count_changed or current_time - self.last_status_log_time > 30):
                        if total_sessions > 0:
                            log_manager.log_formatted_event("PLAY_STATUS", _("检测到 {0} 个需要限速的播放"), total_sessions)
                            if skipped_count > 0:
                                log_manager.log_formatted_event("PLAY_STATUS", _("已跳过 {0} 个本地/白名单播放"), skipped_count)
                        else:
                            log_manager.log_event("PLAY_STATUS", _("所有播放已停止"))
                        
                        self.last_session_count = total_sessions
                        self.last_status_log_time = current_time
                        
                        self._update_speed(settings)
                    elif session_changed:
                        # 会话变化但数量未变，仍需更新速率但不记录重复日志
                        self._update_speed(settings)
                    
                    # 定期清理过期的跳过日志时间戳（每10分钟清理一次）
                    if current_time - self.last_status_log_time > 600:  # 10分钟
                        expired_users = [user for user, timestamp in self.last_skip_log_time.items() 
                                       if current_time - timestamp > 3600]  # 1小时过期
                        for user in expired_users:
                            del self.last_skip_log_time[user]
            
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
            log_manager.log_formatted_event("PLUGIN_ERROR", _("实例配置缺少'type'字段: {0}"), instance_config)
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
            log_manager.log_formatted_event("PLUGIN_ERROR", _("加载插件 {0} 失败: {1}"), plugin_type_single, e)
            return None

    def _update_speed(self, settings):
        """根据播放状态更新所有已启用下载器的速率"""
        # 遍历所有已启用的下载器实例并应用各自的速率设置
        for downloader_instance in settings.get('downloaders', []):
            if downloader_instance.get('enabled'):
                downloader_id = downloader_instance.get('id')
                downloader_name = downloader_instance.get('name', downloader_id)
                
                # 根据是否有播放活动确定要使用的速率，需要考虑不同下载器的特性
                downloader_type = downloader_instance.get('type', '')
                
                if len(self.active_session_ids) > 0:
                    # 使用播放时的速率，需要为SABnzbd设置不同的默认值
                    if downloader_type == 'sabnzbd':
                        dl_limit = downloader_instance.get('backup_download_limit', 50)  # SABnzbd默认50%
                        ul_limit = 0  # SABnzbd不支持上传
                    else:
                        dl_limit = downloader_instance.get('backup_download_limit', 1024)
                        ul_limit = downloader_instance.get('backup_upload_limit', 512)
                else:
                    # 使用默认速率，需要为SABnzbd设置不同的默认值
                    if downloader_type == 'sabnzbd':
                        dl_limit = downloader_instance.get('default_download_limit', 100)  # SABnzbd默认100%
                        ul_limit = 0  # SABnzbd不支持上传
                    else:
                        dl_limit = downloader_instance.get('default_download_limit', 0)
                        ul_limit = downloader_instance.get('default_upload_limit', 0)
                
                # 检查速率是否有变化，避免重复设置
                current_speed = (dl_limit, ul_limit)
                last_speed = self.last_speed_state.get(downloader_id)
                
                if last_speed != current_speed:
                    downloader = self._get_plugin_instance('downloaders', downloader_instance)
                    if downloader:
                        success = downloader.set_speed_limits(dl_limit, ul_limit)
                        if success:
                            # 记录成功日志，使用实例名称，区分SABnzbd的百分比显示
                            if downloader_type == 'sabnzbd':
                                log_manager.log_formatted_event("SPEED_CHANGE", _("{0} 速率限制设置成功: 下载 {1}%, 上传不支持"), downloader_name, dl_limit)
                            else:
                                log_manager.log_formatted_event("SPEED_CHANGE", _("{0} 速率限制设置成功: 下载 {1} KB/s, 上传 {2} KB/s"), downloader_name, dl_limit, ul_limit)
                            # 只有成功设置后才更新状态记录
                            self.last_speed_state[downloader_id] = current_speed
                        else:
                            log_manager.log_formatted_event("SPEED_ERROR", _("{0} 速率设置失败"), downloader_name)
                # else:
                #     # 速率未变化，跳过设置（可选：记录调试日志）
                #     log_manager.log_event("SPEED_DEBUG", f"{downloader_name} 速率未变化，跳过设置")

scheduler = Scheduler() 