import requests
import xml.etree.ElementTree as ET
from .base import MediaServerBase
from ..services.log_manager import log_manager

class Plex(MediaServerBase):
    """Plex媒体服务器的实现"""
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.token = self.config.get('token', '')
        self.session = requests.Session()
        # 设置请求头
        self.session.headers.update({
            'X-Plex-Token': self.token,
            'Accept': 'application/xml',
            'User-Agent': 'Auto-Limit/1.0'
        })

    def get_active_sessions(self):
        if not self.url or not self.token:
            return None
            
        try:
            sessions_url = f"{self.url}/status/sessions"
            response = self.session.get(sessions_url, timeout=10)
            
            if response.status_code == 200:
                try:
                    # 解析XML响应
                    root = ET.fromstring(response.text)
                    active_playing_sessions = []
                    
                    # 查找所有的Video和Track元素（正在播放的媒体）
                    for media in root.findall('.//*[@sessionKey]'):
                        player = media.find('Player')
                        user = media.find('User')
                        
                        # 检查是否在播放且未暂停
                        if player is not None and user is not None:
                            state = player.get('state', '')
                            if state == 'playing':  # 只有playing状态才算活跃
                                session_key = media.get('sessionKey', 'Unknown')
                                user_title = user.get('title', 'Unknown')
                                media_title = media.get('title', 'Unknown')
                                
                                active_playing_sessions.append({
                                    'session_id': session_key,
                                    'user_name': user_title,
                                    'item_name': media_title
                                })
                    
                    return active_playing_sessions
                except ET.ParseError as e:
                    log_manager.log_formatted_event("PLEX_ERROR", "解析Plex会话XML失败: {0}", str(e))
                    return None
            else:
                log_manager.log_formatted_event("PLEX_ERROR", "获取Plex会话失败: HTTP {0}", response.status_code)
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("PLEX_ERROR", "获取Plex会话时出错: {0}", str(e))
            return None

    def test_connection(self):
        if not self.url or not self.token:
            return False, "Plex URL或Token未配置"

        try:
            # 测试连接并获取服务器信息
            info_url = f"{self.url}"
            response = self.session.get(info_url, timeout=5)
            
            if response.status_code == 200:
                try:
                    # 解析XML响应
                    root = ET.fromstring(response.text)
                    server_name = root.get('friendlyName', 'Plex Media Server')
                    version = root.get('version', '未知版本')
                    return True, f"连接成功 - {server_name} ({version})"
                except ET.ParseError:
                    return True, "连接成功"
            elif response.status_code == 401:
                return False, "认证失败，请检查X-Plex-Token是否正确"
            else:
                return False, f"连接失败: HTTP {response.status_code}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"

    def get_network_speeds(self):
        """
        获取当前播放的媒体比特率信息
        注意：返回的是媒体文件的编码比特率，不是实际的网络传输速度
        """
        if not self.url or not self.token:
            return None
            
        try:
            sessions_url = f"{self.url}/status/sessions"
            response = self.session.get(sessions_url, timeout=10)
            
            if response.status_code == 200:
                try:
                    # 解析XML响应
                    root = ET.fromstring(response.text)
                    total_bitrate = 0
                    session_speeds = []
                    
                    # 查找所有的Video和Track元素（正在播放的媒体）
                    for media in root.findall('.//*[@sessionKey]'):
                        player = media.find('Player')
                        user = media.find('User')
                        
                        # 检查是否在播放且未暂停
                        if player is not None and user is not None:
                            state = player.get('state', '')
                            if state == 'playing':  # 只有playing状态才算活跃
                                user_title = user.get('title', 'Unknown')
                                media_title = media.get('title', 'Unknown')
                                bitrate = 0
                                is_transcoding = False
                                
                                # 尝试获取转码信息
                                transcode_session = media.find('TranscodeSession')
                                if transcode_session is not None:
                                    is_transcoding = True
                                    # 从转码会话获取比特率
                                    video_bitrate = transcode_session.get('videoBitrate', '')
                                    audio_bitrate = transcode_session.get('audioBitrate', '')
                                    
                                    try:
                                        if video_bitrate:
                                            bitrate += int(video_bitrate)
                                        if audio_bitrate:
                                            bitrate += int(audio_bitrate)
                                    except ValueError:
                                        pass
                                
                                # 如果没有转码信息，尝试从媒体信息获取
                                if not bitrate:
                                    # 从Media元素获取比特率
                                    media_elem = media.find('Media')
                                    if media_elem is not None:
                                        media_bitrate = media_elem.get('bitrate', '')
                                        try:
                                            if media_bitrate:
                                                bitrate = int(media_bitrate)
                                        except ValueError:
                                            pass
                                
                                # 如果还没有比特率，尝试从Part元素获取
                                if not bitrate:
                                    part_elem = media.find('.//Part')
                                    if part_elem is not None:
                                        part_bitrate = part_elem.get('bitrate', '')
                                        try:
                                            if part_bitrate:
                                                bitrate = int(part_bitrate)
                                        except ValueError:
                                            pass
                                
                                # Plex的比特率单位通常是Kbps
                                if bitrate > 0:
                                    total_bitrate += bitrate
                                    session_speeds.append({
                                        'user_name': user_title,
                                        'item_name': media_title,
                                        'bitrate': bitrate,
                                        'is_transcoding': is_transcoding,
                                        'is_estimated': not is_transcoding  # 标记是否为估算值
                                    })
                    
                    return {
                        'total_bitrate': total_bitrate,  # 单位：Kbps
                        'sessions': session_speeds
                    }
                except ET.ParseError as e:
                    log_manager.log_formatted_event("PLEX_ERROR", "解析Plex网络速度XML失败: {0}", str(e))
                    return None
            else:
                log_manager.log_formatted_event("PLEX_ERROR", "获取Plex网络速度失败: HTTP {0}", response.status_code)
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("PLEX_ERROR", "获取Plex网络速度时出错: {0}", str(e))
            return None 