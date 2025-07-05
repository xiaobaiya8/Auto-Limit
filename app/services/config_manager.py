import json
import os
from flask import current_app
import uuid
from threading import Lock

class ConfigManager:
    """
    负责管理应用配置的类，所有配置读写通过此类进行。
    """
    def __init__(self):
        self.config_path = None
        self.settings = {}
        self.lock = Lock()
        self.app = None

    def init_app(self, app):
        """用Flask app实例来初始化"""
        self.app = app
        self.config_path = os.path.join(app.config['DATA_DIR'], 'config.json')
        self.load_settings()

    def get_default_settings(self):
        """返回默认配置"""
        return {
            'media_servers': [],
            'downloaders': [],
            'rates': {
                'default_download_limit': 0,
                'default_upload_limit': 0,
                'backup_download_limit': 1024,
                'backup_upload_limit': 512
            },
            'scheduler': {
                'poll_interval': 15
            },
            'ui': {
                'language': 'zh'  # 添加UI语言设置
            }
        }

    def load_settings(self):
        """从JSON文件加载配置"""
        if self.config_path is None:
            raise RuntimeError("ConfigManager has not been initialized. Call init_app(app) first.")
        
        with self.lock:
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        loaded_settings = json.load(f)
                        # 合并默认设置和加载的设置
                        self.settings = self.get_default_settings()
                        self._merge_settings(self.settings, loaded_settings)
                else:
                    self.settings = self.get_default_settings()
                    self.save_settings(self.settings)
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置文件失败: {e}")
                self.settings = self.get_default_settings()

    def _merge_settings(self, default, loaded):
        """递归合并设置"""
        for key, value in loaded.items():
            if key in default:
                if isinstance(value, dict) and isinstance(default[key], dict):
                    self._merge_settings(default[key], value)
                else:
                    default[key] = value
            else:
                default[key] = value

    def get_settings(self):
        """获取当前配置"""
        with self.lock:
            return self.settings.copy()

    def save_settings(self, new_settings):
        """保存配置到JSON文件"""
        if self.config_path is None:
            raise RuntimeError("ConfigManager has not been initialized. Call init_app(app) first.")
        
        with self.lock:
            self.settings = new_settings
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=4, ensure_ascii=False)
            except IOError as e:
                print(f"保存配置文件失败: {e}")

    def get_language(self):
        """获取当前UI语言设置"""
        with self.lock:
            return self.settings.get('ui', {}).get('language', 'zh')

    def set_language(self, language):
        """设置UI语言"""
        with self.lock:
            if 'ui' not in self.settings:
                self.settings['ui'] = {}
            self.settings['ui']['language'] = language
            # 立即保存到文件
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.settings, f, indent=4, ensure_ascii=False)
            except IOError as e:
                print(f"保存语言设置失败: {e}")

    def _needs_migration(self, settings):
        """检查配置是否是需要迁移的旧格式（基于字典）"""
        return isinstance(settings.get("media_servers"), dict) or \
               isinstance(settings.get("downloaders"), dict)

    def _migrate_config(self, old_settings):
        """将旧的基于字典的配置迁移到新的基于列表的配置"""
        current_app.logger.info("检测到旧版配置文件，正在执行自动迁移...")
        new_settings = {
            "media_servers": [],
            "downloaders": [],
            "rates": old_settings.get("rates", {}),
            "scheduler": old_settings.get("scheduler", {})
        }

        # 迁移媒体服务器
        if isinstance(old_settings.get("media_servers"), dict):
            for server_type, config in old_settings["media_servers"].items():
                if config.get("enabled"):  # 只迁移启用的
                    new_instance = config.copy()
                    new_instance["id"] = str(uuid.uuid4())
                    new_instance["name"] = f"My {server_type.capitalize()}" # 自动生成一个名字
                    new_instance["type"] = server_type
                    # 添加轮询间隔设置，从全局scheduler设置迁移
                    scheduler_settings = old_settings.get('scheduler', {})
                    new_instance["poll_interval"] = scheduler_settings.get('poll_interval', 15)
                    new_settings["media_servers"].append(new_instance)

        # 迁移下载器
        if isinstance(old_settings.get("downloaders"), dict):
            for downloader_type, config in old_settings["downloaders"].items():
                if config.get("enabled"):
                    new_instance = config.copy()
                    new_instance["id"] = str(uuid.uuid4())
                    new_instance["name"] = f"My {downloader_type.capitalize()}"
                    new_instance["type"] = downloader_type
                    # 添加限速设置，从全局rates迁移
                    rates = old_settings.get('rates', {})
                    new_instance["default_download_limit"] = rates.get('default_download_limit', 0)
                    new_instance["default_upload_limit"] = rates.get('default_upload_limit', 0)
                    new_instance["backup_download_limit"] = rates.get('backup_download_limit', 1024)
                    new_instance["backup_upload_limit"] = rates.get('backup_upload_limit', 512)
                    new_settings["downloaders"].append(new_instance)
        
        current_app.logger.info("配置迁移完成。")
        return new_settings

config_manager = ConfigManager() 