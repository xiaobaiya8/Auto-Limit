import requests
from .base import MediaServerBase
from ..services.log_manager import log_manager

class Emby(MediaServerBase):
    """Emby媒体服务器的实现"""
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.api_key = self.config.get('api_key', '')
        self.session = requests.Session()

    def get_active_sessions(self):
        if not self.url or not self.api_key:
            return None
            
        try:
            sessions_url = f"{self.url}/emby/Sessions"
            params = {'api_key': self.api_key}
            response = self.session.get(sessions_url, params=params, timeout=10)
            
            if response.status_code == 200:
                sessions = response.json()
                active_playing_sessions = []
                for session in sessions:
                    if 'NowPlayingItem' in session and session.get('NowPlayingItem'):
                        play_state = session.get('PlayState', {})
                        is_paused = play_state.get('IsPaused', False)
                        if not is_paused:
                            active_playing_sessions.append({
                                'session_id': session.get('Id', 'Unknown'),
                                'user_name': session.get('UserName', 'Unknown'),
                                'item_name': session.get('NowPlayingItem', {}).get('Name', 'Unknown')
                            })
                return active_playing_sessions
            else:
                log_manager.log_event("EMBY_ERROR", f"获取Emby会话失败: HTTP {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_event("EMBY_ERROR", f"获取Emby会话时出错: {str(e)}")
            return None

    def test_connection(self):
        if not self.url or not self.api_key:
            return False, "Emby URL或API密钥未配置"

        try:
            info_url = f"{self.url}/emby/System/Info/Public"
            response = self.session.get(info_url, timeout=5)
            if response.status_code == 200:
                return True, "连接成功"
            else:
                return False, f"连接失败: HTTP {response.status_code}"
        except Exception as e:
            return False, f"连接失败: {str(e)}" 