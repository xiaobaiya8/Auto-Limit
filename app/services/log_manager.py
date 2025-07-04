import json
import os
from datetime import datetime
from flask import current_app

class LogManager:
    """
    管理JSON格式的日志文件。
    """
    def __init__(self, max_entries=500):
        self.log_path = None
        self.max_entries = max_entries

    def init_app(self, app):
        """用Flask app实例来初始化"""
        self.log_path = os.path.join(app.config['DATA_DIR'], 'logs.json')

    def get_logs(self):
        """从JSON文件安全地加载日志"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")
        
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            current_app.logger.error(f"读取日志文件失败: {e}")
        return []

    def log_event(self, event_type, message):
        """记录事件到JSON日志文件，并保持日志数量上限"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")

        current_app.logger.info(f"[{event_type}] {message}")
        
        logs = self.get_logs()
        
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "message": message
        }
        
        logs.insert(0, log_entry)
        
        trimmed_logs = logs[:self.max_entries]
        
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(trimmed_logs, f, indent=4)
        except IOError as e:
            current_app.logger.error(f"保存日志文件失败: {e}")

log_manager = LogManager() 