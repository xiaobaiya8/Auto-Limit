import json
import os
from flask import current_app
import uuid

class ConfigManager:
    """
    负责管理应用配置的类，所有配置读写通过此类进行。
    """
    def __init__(self):
        self.config_path = None

    def init_app(self, app):
        """用Flask app实例来初始化"""
        self.config_path = os.path.join(app.config['DATA_DIR'], 'config.json')

    def get_settings(self):
        """从JSON文件加载配置，并处理旧格式到新格式的迁移"""
        if self.config_path is None:
            raise RuntimeError("ConfigManager has not been initialized. Call init_app(app) first.")
        
        # 新的默认配置结构，支持多实例
        defaults = {
            "media_servers": [],
            "downloaders": [],
            "rates": {
                "default_download_limit": 0,
                "default_upload_limit": 0,
                "backup_download_limit": 1024,
                "backup_upload_limit": 512
            },
            "scheduler": {
                "poll_interval": 15
            }
        }

        settings = defaults
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # 检查是否需要迁移
                if self._needs_migration(settings):
                    settings = self._migrate_config(settings)
                    self.save_settings(settings)
                
                # 合并默认值以处理未来可能增加的顶级键
                for key, value in defaults.items():
                    if key not in settings:
                        settings[key] = value

        except (json.JSONDecodeError, IOError) as e:
            current_app.logger.error(f"读取配置文件失败，将使用默认配置: {e}")
            return defaults
        
        return settings
    
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

    def save_settings(self, settings):
        """保存配置到JSON文件"""
        if self.config_path is None:
            raise RuntimeError("ConfigManager has not been initialized. Call init_app(app) first.")

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            current_app.logger.info("配置已成功保存")
            return True
        except IOError as e:
            current_app.logger.error(f"保存配置文件失败: {e}")
            return False

config_manager = ConfigManager() 