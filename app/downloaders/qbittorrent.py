import requests
import json
from .base import DownloaderBase
from ..services.log_manager import log_manager

class Qbittorrent(DownloaderBase):
    """qBittorrent下载器的实现"""
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        self.session = requests.Session()

    def login(self):
        if not self.url or not self.username:
            return False
            
        try:
            login_url = f"{self.url}/api/v2/auth/login"
            data = {'username': self.username, 'password': self.password}
            response = self.session.post(login_url, data=data, timeout=10)
            if response.status_code == 200 and response.text == "Ok.":
                return True
            else:
                log_manager.log_event("QB_ERROR", f"qBittorrent登录失败: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            log_manager.log_event("QB_ERROR", f"qBittorrent连接错误: {str(e)}")
            return False

    def set_speed_limits(self, download_limit_kb, upload_limit_kb):
        if not self.login():
            return False
        try:
            preferences_url = f"{self.url}/api/v2/app/setPreferences"
            data = {'json': json.dumps({
                'dl_limit': download_limit_kb * 1024 if download_limit_kb > 0 else 0,
                'up_limit': upload_limit_kb * 1024 if upload_limit_kb > 0 else 0
            })}
            response = self.session.post(preferences_url, data=data)
            if response.status_code == 200:
                return True
            else:
                log_manager.log_event("QB_ERROR", f"速率限制设置失败: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            log_manager.log_event("QB_ERROR", f"设置速率限制时出错: {str(e)}")
            return False

    def test_connection(self):
        if not self.url or not self.username:
            return False, "qBittorrent URL或用户名未配置"
        
        if self.login():
            return True, "连接成功"
        else:
            return False, "连接失败，请检查URL、用户名和密码" 