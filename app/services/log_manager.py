import json
import os
import tempfile
import shutil
from datetime import datetime
from threading import RLock
from flask import current_app, has_request_context, has_app_context
from flask_babel import gettext as _, force_locale

class LogManager:
    """
    管理JSON格式的日志文件。
    """
    def __init__(self, max_entries=500):
        self.log_path = None
        self.max_entries = max_entries
        self._app = None  # 存储应用实例的引用
        self._lock = RLock()  # 线程安全锁

    def init_app(self, app):
        """用Flask app实例来初始化"""
        self.log_path = os.path.join(app.config['DATA_DIR'], 'logs.json')
        self._app = app

    def get_logs(self):
        """从JSON文件安全地加载日志"""
        if self.log_path is None:
            raise RuntimeError("LogManager has not been initialized. Call init_app(app) first.")
        
        with self._lock:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self._safe_log_error(f"读取日志文件失败: {e}")
                # 如果日志文件损坏，尝试从备份恢复
                backup_path = self.log_path + '.backup'
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            logs = json.load(f)
                        self._safe_log_error("从备份文件恢复日志成功")
                        return logs
                    except (json.JSONDecodeError, IOError):
                        self._safe_log_error("备份文件也损坏，创建新的日志文件")
                
                # 如果无法恢复，创建新的日志文件
                self._create_new_log_file()
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

    def _create_new_log_file(self):
        """创建新的日志文件"""
        try:
            initial_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "SYSTEM",
                "message": "日志系统已重新初始化"
            }
            with open(self.log_path, 'w', encoding='utf-8') as f:
                json.dump([initial_log], f, indent=4, ensure_ascii=False)
        except IOError as e:
            self._safe_log_error(f"创建新日志文件失败: {e}")

    def _atomic_write_logs(self, logs):
        """原子性地写入日志文件"""
        if not logs:
            return False
            
        try:
            # 创建临时文件
            temp_dir = os.path.dirname(self.log_path)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', 
                                           dir=temp_dir, delete=False, 
                                           suffix='.tmp') as temp_file:
                json.dump(logs, temp_file, indent=4, ensure_ascii=False)
                temp_path = temp_file.name
            
            # 创建备份
            backup_path = self.log_path + '.backup'
            if os.path.exists(self.log_path):
                shutil.copy2(self.log_path, backup_path)
            
            # 原子性地移动临时文件到目标位置
            if os.name == 'nt':  # Windows
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                shutil.move(temp_path, self.log_path)
            else:  # Unix/Linux
                os.rename(temp_path, self.log_path)
            
            return True
            
        except Exception as e:
            self._safe_log_error(f"原子写入日志文件失败: {e}")
            # 清理临时文件
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
            return False

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
                # 获取配置的语言设置
                from .config_manager import config_manager
                try:
                    config_language = config_manager.get_language()
                    if config_language in self._app.config.get('LANGUAGES', ['zh', 'en']):
                        # 使用 force_locale 强制设置语言环境
                        with force_locale(config_language):
                            return _(message)
                except:
                    pass
                
                # 如果获取语言失败，使用默认语言
                with self._app.test_request_context():
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
        
        with self._lock:
            logs = self.get_logs()
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": event_type,
                "message": translated_message
            }
            logs.insert(0, log_entry)
            
            trimmed_logs = logs[:self.max_entries]
            
            # 使用原子写入
            if not self._atomic_write_logs(trimmed_logs):
                self._safe_log_error(f"保存日志文件失败")

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
        
        with self._lock:
            logs = self.get_logs()
            
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": event_type,
                "message": formatted_message
            }
            
            logs.insert(0, log_entry)
            
            trimmed_logs = logs[:self.max_entries]
            
            # 使用原子写入
            if not self._atomic_write_logs(trimmed_logs):
                self._safe_log_error(f"保存日志文件失败")

log_manager = LogManager() 