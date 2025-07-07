import json
import os
import shutil
import tempfile
from datetime import datetime
from threading import RLock
from flask import current_app, has_request_context, has_app_context
from flask_babel import gettext as _, force_locale

class LogManager:
    """
    管理JSON格式的日志文件。
    使用原子写入和优化的锁机制来防止并发写入时的数据损坏。
    """
    def __init__(self, max_entries=500):
        self.log_path = None
        self.max_entries = max_entries
        self._app = None  # 存储应用实例的引用
        self._lock = RLock()  # 线程安全锁
        self._write_lock = RLock()  # 专门用于文件写入的锁

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
            except UnicodeDecodeError as e:
                self._safe_log_error(f"日志文件编码错误: {e}")
                # 尝试恢复日志文件
                recovered_logs = self._try_recover_logs()
                if recovered_logs is not None:
                    # 如果恢复成功，重新写入文件
                    self._backup_corrupted_log_file()
                    self._atomic_write_logs(recovered_logs)
                    return recovered_logs
                else:
                    # 恢复失败，备份并重新创建
                    self._backup_corrupted_log_file()
                    self._create_new_log_file()
            except (json.JSONDecodeError, IOError) as e:
                self._safe_log_error(f"读取日志文件失败: {e}")
                # 如果日志文件损坏，创建新的日志文件
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

    def _try_recover_logs(self):
        """尝试从损坏的日志文件中恢复数据"""
        try:
            if not os.path.exists(self.log_path):
                return None
            
            # 尝试用不同的编码读取文件
            encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    with open(self.log_path, 'r', encoding=encoding, errors='replace') as f:
                        content = f.read()
                    break
                except:
                    continue
            
            if content is None:
                return None
            
            # 尝试修复JSON格式
            try:
                # 首先尝试直接解析
                return json.loads(content)
            except json.JSONDecodeError:
                # 如果失败，尝试找到最后一个完整的日志条目
                try:
                    # 查找最后一个完整的 '}]' 结构
                    last_bracket = content.rfind('}]')
                    if last_bracket > 0:
                        truncated_content = content[:last_bracket + 2]
                        return json.loads(truncated_content)
                except:
                    pass
                
                # 尝试逐行解析，构建有效的日志条目
                try:
                    lines = content.split('\n')
                    valid_logs = []
                    current_entry = ""
                    brace_count = 0
                    
                    for line in lines:
                        current_entry += line
                        brace_count += line.count('{') - line.count('}')
                        
                        # 如果大括号平衡，尝试解析当前条目
                        if brace_count == 0 and current_entry.strip():
                            try:
                                # 移除可能的逗号和括号
                                entry_text = current_entry.strip().rstrip(',').strip('[]')
                                if entry_text:
                                    entry = json.loads(entry_text)
                                    if isinstance(entry, dict) and 'timestamp' in entry:
                                        valid_logs.append(entry)
                            except:
                                pass
                            current_entry = ""
                    
                    return valid_logs if valid_logs else []
                except:
                    pass
                
                # 如果所有修复尝试都失败，返回空列表
                return []
        
        except Exception as e:
            self._safe_log_error(f"恢复日志文件失败: {e}")
            return None

    def _backup_corrupted_log_file(self):
        """备份损坏的日志文件"""
        try:
            if os.path.exists(self.log_path):
                backup_path = f"{self.log_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(self.log_path, backup_path)
                self._safe_log_info(f"已备份损坏的日志文件到: {backup_path}")
        except Exception as e:
            self._safe_log_error(f"备份损坏日志文件失败: {e}")

    def _create_new_log_file(self):
        """创建新的日志文件"""
        try:
            initial_log = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # 毫秒精度
                "type": "SYSTEM",
                "message": "日志系统已重新初始化"
            }
            self._atomic_write_logs([initial_log])
        except Exception as e:
            self._safe_log_error(f"创建新日志文件失败: {e}")

    def _atomic_write_logs(self, logs):
        """使用原子操作写入日志文件"""
        if not logs:
            return False
            
        with self._write_lock:
            try:
                # 确保所有日志条目都是有效的UTF-8字符串
                cleaned_logs = []
                for log in logs:
                    cleaned_log = {}
                    for key, value in log.items():
                        if isinstance(value, str):
                            # 清理无效的UTF-8字符
                            try:
                                cleaned_log[key] = value.encode('utf-8', errors='replace').decode('utf-8')
                            except:
                                cleaned_log[key] = str(value)
                        else:
                            cleaned_log[key] = value
                    cleaned_logs.append(cleaned_log)
                
                # 获取日志文件所在目录
                log_dir = os.path.dirname(self.log_path)
                
                # 创建临时文件在同一目录下
                with tempfile.NamedTemporaryFile(
                    mode='w', 
                    encoding='utf-8', 
                    dir=log_dir,
                    suffix='.tmp',
                    prefix='logs_',
                    delete=False
                ) as temp_file:
                    temp_path = temp_file.name
                    # 使用紧凑JSON格式减少写入时间
                    json.dump(cleaned_logs, temp_file, ensure_ascii=False, separators=(',', ':'))
                    temp_file.flush()
                    os.fsync(temp_file.fileno())  # 强制写入磁盘
                
                # 原子替换：在Unix系统上rename是原子操作
                os.rename(temp_path, self.log_path)
                return True
                
            except Exception as e:
                # 清理临时文件
                try:
                    if 'temp_path' in locals() and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass
                
                self._safe_log_error(f"原子写入日志文件失败: {e}")
                
                # 回退到直接写入
                try:
                    with open(self.log_path, 'w', encoding='utf-8') as f:
                        json.dump(cleaned_logs, f, ensure_ascii=False, separators=(',', ':'))
                    return True
                except Exception as fallback_e:
                    self._safe_log_error(f"回退写入日志文件也失败: {fallback_e}")
                    return False

    # 保持向后兼容
    def _write_logs(self, logs):
        """向后兼容的写入方法"""
        return self._atomic_write_logs(logs)

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

        try:
            # 清理输入的消息，确保是有效的UTF-8字符串
            if isinstance(message, str):
                message = message.encode('utf-8', errors='replace').decode('utf-8')
            else:
                message = str(message)
            
            if isinstance(event_type, str):
                event_type = event_type.encode('utf-8', errors='replace').decode('utf-8')
            else:
                event_type = str(event_type)
        except:
            # 如果清理失败，使用安全的默认值
            message = "日志消息包含无效字符"
            event_type = "SYSTEM"

        translated_message = self._translate(message)
        self._safe_log_info(f"[{event_type}] {translated_message}")
        
        with self._lock:
            # 避免嵌套锁调用，直接读取日志
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                else:
                    logs = []
            except (json.JSONDecodeError, IOError, UnicodeDecodeError):
                # 如果读取失败，从恢复机制获取日志
                logs = self.get_logs()
            
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # 毫秒精度
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

        try:
            # 清理输入的消息，确保是有效的UTF-8字符串
            if isinstance(formatted_message, str):
                formatted_message = formatted_message.encode('utf-8', errors='replace').decode('utf-8')
            else:
                formatted_message = str(formatted_message)
            
            if isinstance(event_type, str):
                event_type = event_type.encode('utf-8', errors='replace').decode('utf-8')
            else:
                event_type = str(event_type)
        except:
            # 如果清理失败，使用安全的默认值
            formatted_message = "日志消息包含无效字符"
            event_type = "SYSTEM"

        self._safe_log_info(f"[{event_type}] {formatted_message}")
        
        with self._lock:
            # 避免嵌套锁调用，直接读取日志
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                else:
                    logs = []
            except (json.JSONDecodeError, IOError, UnicodeDecodeError):
                # 如果读取失败，从恢复机制获取日志
                logs = self.get_logs()
            
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # 毫秒精度
                "type": event_type,
                "message": formatted_message
            }
            
            logs.insert(0, log_entry)
            
            trimmed_logs = logs[:self.max_entries]
            
            # 使用原子写入
            if not self._atomic_write_logs(trimmed_logs):
                self._safe_log_error(f"保存日志文件失败")

log_manager = LogManager() 