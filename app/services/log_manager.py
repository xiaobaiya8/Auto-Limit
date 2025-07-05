import json
import os
from datetime import datetime
from flask import current_app, has_request_context, session, has_app_context
from flask_babel import gettext as _

class LogManager:
    """
    管理JSON格式的日志文件。
    """
    def __init__(self, max_entries=500):
        self.log_path = None
        self.max_entries = max_entries
        self._app = None  # 存储应用实例的引用

    def init_app(self, app):
        """用Flask app实例来初始化"""
        self.log_path = os.path.join(app.config['DATA_DIR'], 'logs.json')
        self._app = app

    def get_logs(self):
        """从JSON文件安全地加载日志"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")
        
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self._safe_log_error(f"读取日志文件失败: {e}")
        return []

    def _safe_log_error(self, message):
        """安全地记录错误日志"""
        if has_app_context():
            current_app.logger.error(message)
        elif self._app:
            self._app.logger.error(message)
        else:
            print(f"ERROR: {message}")

    def _safe_log_info(self, message):
        """安全地记录信息日志"""
        if has_app_context():
            current_app.logger.info(message)
        elif self._app:
            self._app.logger.info(message)
        else:
            print(f"INFO: {message}")

    def _translate(self, message):
        """
        翻译消息。
        对于后台任务，它会创建一个临时的请求上下文。
        """
        try:
            # 如果有请求上下文，直接使用标准的翻译函数
            if has_request_context():
                return _(message)
            
            # 如果没有请求上下文（例如在后台线程中），但有应用上下文
            if self._app and has_app_context():
                # 创建一个临时的请求上下文来启用翻译
                with self._app.test_request_context():
                    from .config_manager import config_manager
                    # 强制从磁盘重新加载配置，确保获取最新语言设置
                    config_manager.load_settings()
                    # 从配置文件中获取语言并设置到临时session中
                    session['language'] = config_manager.get_language()
                    return _(message)
        except Exception as e:
            # 如果翻译因任何原因失败，返回原始消息
            self._safe_log_error(f"翻译日志消息失败: {e}")
            return message
        
        # 如果以上条件都不满足，返回原始消息
        return message

    def log_event(self, event_type, message):
        """记录事件到JSON日志文件"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")

        translated_message = self._translate(message)
        self._safe_log_info(f"[{event_type}] {translated_message}")
        
        logs = self.get_logs()
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "message": translated_message
        }
        logs.insert(0, log_entry)
        
        trimmed_logs = logs[:self.max_entries]
        
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(trimmed_logs, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self._safe_log_error(f"保存日志文件失败: {e}")

    def log_formatted_event(self, event_type, message_template, *args, **kwargs):
        """记录格式化的日志事件"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")

        try:
            translated_template = self._translate(message_template)
            formatted_message = translated_template.format(*args, **kwargs)
        except:
            try:
                formatted_message = message_template.format(*args, **kwargs)
            except:
                formatted_message = message_template

        self._safe_log_info(f"[{event_type}] {formatted_message}")
        
        logs = self.get_logs()
        
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "message": formatted_message
        }
        
        logs.insert(0, log_entry)
        
        trimmed_logs = logs[:self.max_entries]
        
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump(trimmed_logs, f, indent=4, ensure_ascii=False)
        except IOError as e:
            self._safe_log_error(f"保存日志文件失败: {e}")

log_manager = LogManager() 