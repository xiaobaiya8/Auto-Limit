import requests
from .base import MediaServerBase
from ..services.log_manager import log_manager

class Jellyfin(MediaServerBase):
    """Jellyfin媒体服务器的实现"""
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.api_key = self.config.get('api_key', '')
        self.session = requests.Session()

    def get_active_sessions(self):
        if not self.url or not self.api_key:
            return None
            
        try:
            # Jellyfin的Sessions API路径
            sessions_url = f"{self.url}/Sessions"
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
                            # 获取客户端IP和设备信息
                            client_ip = session.get('RemoteEndPoint', '')
                            device_name = session.get('DeviceName', 'Unknown')
                            
                            # 如果RemoteEndPoint包含端口，提取IP部分
                            if client_ip and ':' in client_ip:
                                client_ip = client_ip.split(':')[0]
                            
                            active_playing_sessions.append({
                                'session_id': session.get('Id', 'Unknown'),
                                'user_name': session.get('UserName', 'Unknown'),
                                'item_name': session.get('NowPlayingItem', {}).get('Name', 'Unknown'),
                                'client_ip': client_ip,
                                'device_name': device_name
                            })
                return active_playing_sessions
            else:
                log_manager.log_formatted_event("JELLYFIN_ERROR", "获取Jellyfin会话失败: HTTP {0}", response.status_code)
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("JELLYFIN_ERROR", "获取Jellyfin会话时出错: {0}", str(e))
            return None

    def test_connection(self):
        if not self.url or not self.api_key:
            return False, "Jellyfin URL或API密钥未配置"

        try:
            # Jellyfin的系统信息API
            info_url = f"{self.url}/System/Info/Public"
            response = self.session.get(info_url, timeout=5)
            if response.status_code == 200:
                try:
                    info = response.json()
                    server_name = info.get('ServerName', 'Jellyfin Server')
                    version = info.get('Version', '未知版本')
                    return True, f"连接成功 - {server_name} ({version})"
                except:
                    return True, "连接成功"
            else:
                return False, f"连接失败: HTTP {response.status_code}"
        except Exception as e:
            return False, f"连接失败: {str(e)}"

    def get_network_speeds(self):
        """
        获取当前播放的媒体比特率信息
        注意：返回的是媒体文件的编码比特率，不是实际的网络传输速度
        """
        if not self.url or not self.api_key:
            return None
            
        try:
            sessions_url = f"{self.url}/Sessions"
            params = {'api_key': self.api_key}
            response = self.session.get(sessions_url, params=params, timeout=10)
            
            if response.status_code == 200:
                sessions = response.json()
                total_bitrate = 0
                session_speeds = []
                
                for session in sessions:
                    if 'NowPlayingItem' in session and session.get('NowPlayingItem'):
                        play_state = session.get('PlayState', {})
                        is_paused = play_state.get('IsPaused', False)
                        
                        if not is_paused:  # 只统计正在播放的会话
                            user_name = session.get('UserName', 'Unknown')
                            bitrate = 0
                            is_transcoding = False
                            
                            # 优先从TranscodingInfo获取实时转码比特率
                            transcoding_info = session.get('TranscodingInfo')
                            if transcoding_info:
                                is_transcoding = True
                                # 转码时的比特率更接近实际网络使用
                                bitrate = transcoding_info.get('Bitrate', 0)
                                if not bitrate:
                                    # 有些版本可能使用不同的字段名
                                    video_bitrate = transcoding_info.get('VideoBitrate', 0)
                                    audio_bitrate = transcoding_info.get('AudioBitrate', 0)
                                    if video_bitrate or audio_bitrate:
                                        bitrate = video_bitrate + audio_bitrate
                            
                            # 如果没有转码，尝试从其他地方获取比特率
                            if not bitrate:
                                # 从Media信息获取当前播放的比特率
                                media_info = session.get('NowPlayingItem', {})
                                
                                # 尝试从当前选择的媒体流获取
                                media_sources = media_info.get('MediaSources', [])
                                if media_sources:
                                    # 获取当前播放的媒体源
                                    current_media = media_sources[0]  # 通常第一个是当前播放的
                                    bitrate = current_media.get('Bitrate', 0)
                                
                                # 如果还是没有，从NowPlayingItem获取
                                if not bitrate:
                                    bitrate = media_info.get('Bitrate', 0)
                                
                                # 最后尝试从MediaStreams计算总比特率
                                if not bitrate:
                                    media_streams = media_info.get('MediaStreams', [])
                                    for stream in media_streams:
                                        stream_bitrate = stream.get('BitRate', 0)
                                        if stream_bitrate:
                                            bitrate += stream_bitrate
                            
                            # 转换单位：确保统一为Kbps
                            if bitrate > 100000:  # 大于100Kbps，可能是bps单位
                                bitrate = bitrate / 1000  # 转换为Kbps
                            
                            # 对于非转码的直播，应用一个动态因子来模拟网络波动
                            if not is_transcoding and bitrate > 0:
                                # 注意：这里的比特率是媒体文件的原始比特率，不是实时网络速度
                                # 我们添加一个标记来区分这种情况
                                pass
                            
                            if bitrate > 0:
                                total_bitrate += bitrate
                                session_speeds.append({
                                    'user_name': user_name,
                                    'item_name': session.get('NowPlayingItem', {}).get('Name', 'Unknown'),
                                    'bitrate': bitrate,
                                    'is_transcoding': is_transcoding,
                                    'is_estimated': not is_transcoding  # 标记是否为估算值
                                })
                
                return {
                    'total_bitrate': total_bitrate,  # 单位：Kbps
                    'sessions': session_speeds
                }
            else:
                log_manager.log_formatted_event("JELLYFIN_ERROR", "获取Jellyfin网络速度失败: HTTP {0}", response.status_code)
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("JELLYFIN_ERROR", "获取Jellyfin网络速度时出错: {0}", str(e))
            return None 