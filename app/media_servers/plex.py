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
                                
                                # 获取媒体文件比特率信息
                                media_bitrate = None
                                try:
                                    # 尝试从Media元素获取比特率
                                    media_element = media.find('Media')
                                    if media_element is not None:
                                        bitrate_str = media_element.get('bitrate', '')
                                        if bitrate_str:
                                            media_bitrate = int(bitrate_str)  # 单位：Kbps
                                    
                                    # 如果Media元素没有，尝试从Part元素获取
                                    if media_bitrate is None:
                                        part_element = media.find('.//Part')
                                        if part_element is not None:
                                            bitrate_str = part_element.get('bitrate', '')
                                            if bitrate_str:
                                                media_bitrate = int(bitrate_str)
                                except (ValueError, AttributeError):
                                    media_bitrate = None
                                
                                active_playing_sessions.append({
                                    'session_id': session_key,
                                    'user_name': user_title,
                                    'item_name': media_title,
                                    'media_bitrate': media_bitrate
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
        获取当前实际的网络传输速度信息
        使用Plex的statistics/bandwidth API获取真实的字节传输统计！
        """
        if not self.url or not self.token:
            return None
            
        try:
            # 首先获取活跃会话以匹配用户和媒体信息
            active_sessions = self.get_active_sessions()
            if not active_sessions:
                return {
                    'total_bitrate': 0,
                    'sessions': []
                }
            
            # 获取最近6秒的带宽统计数据
            bandwidth_url = f"{self.url}/statistics/bandwidth"
            params = {
                'timespan': 6,  # 6秒时间窗口
                'X-Plex-Token': self.token
            }
            
            # 为bandwidth API创建专用的请求头（接受JSON）
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Auto-Limit/1.0'
            }
            
            # 使用独立的requests.get调用，避免session的XML Accept头冲突
            response = requests.get(bandwidth_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    # 调试：记录响应内容的前100个字符
                    response_preview = response.text[:100] if response.text else "空响应"
                    log_manager.log_formatted_event("PLEX_DEBUG", "Plex带宽API响应预览: {0}", response_preview)
                    
                    data = response.json()
                    media_container = data.get('MediaContainer', {})
                    bandwidth_stats = media_container.get('StatisticsBandwidth', [])
                    devices = media_container.get('Device', [])
                    accounts = media_container.get('Account', [])
                    
                    log_manager.log_formatted_event("PLEX_DEBUG", "获取到带宽统计数据: {0}条, 设备: {1}个, 账户: {2}个", 
                                                   len(bandwidth_stats), len(devices), len(accounts))
                    
                    # 创建设备和账户映射
                    device_map = {device['id']: device for device in devices}
                    account_map = {account['id']: account for account in accounts}
                    
                    # 计算每个设备的实时带宽（KB/s）
                    current_time = int(__import__('time').time())
                    device_bandwidth = {}
                    
                    # 只看最近10秒的数据来计算当前速度
                    recent_stats = [stat for stat in bandwidth_stats 
                                  if current_time - stat.get('at', 0) <= 10]
                    
                    log_manager.log_formatted_event("PLEX_DEBUG", "最近10秒内的带宽数据: {0}条", len(recent_stats))
                    
                    for stat in recent_stats:
                        device_id = stat.get('deviceID')
                        account_id = stat.get('accountID')
                        bytes_count = stat.get('bytes', 0)
                        timespan = stat.get('timespan', 6)
                        
                        if device_id and bytes_count > 0:
                            # 计算KB/s (bytes / timespan / 1024)
                            kbps = bytes_count / timespan / 1024
                            
                            if device_id not in device_bandwidth:
                                device_bandwidth[device_id] = {
                                    'total_kbps': 0,
                                    'account_id': account_id,
                                    'sample_count': 0
                                }
                            
                            device_bandwidth[device_id]['total_kbps'] += kbps
                            device_bandwidth[device_id]['sample_count'] += 1
                    
                    # 按用户合并传输数据（合并同一用户的多个数据流）
                    user_bandwidth = {}
                    
                    for device_id, stats in device_bandwidth.items():
                        if stats['sample_count'] > 0:
                            avg_kbps = stats['total_kbps'] / stats['sample_count']
                            account_id = stats['account_id']
                            
                            # 获取设备和用户信息
                            device_info = device_map.get(device_id, {})
                            account_info = account_map.get(account_id, {})
                            
                            device_name = device_info.get('name', 'Unknown Device')
                            user_name = account_info.get('name', 'Unknown User')
                            
                            # 尝试匹配到活跃会话
                            matched_session = None
                            for session in active_sessions:
                                if session.get('user_name') == user_name:
                                    matched_session = session
                                    break
                            
                            if avg_kbps > 0.1:  # 过滤掉很小的传输
                                if user_name not in user_bandwidth:
                                    user_bandwidth[user_name] = {
                                        'total_kbps': 0,
                                        'max_kbps': 0,
                                        'device_name': device_name,
                                        'matched_session': matched_session,
                                        'device_count': 0
                                    }
                                
                                # 累加同一用户的所有传输
                                user_bandwidth[user_name]['total_kbps'] += avg_kbps
                                user_bandwidth[user_name]['max_kbps'] = max(user_bandwidth[user_name]['max_kbps'], avg_kbps)
                                user_bandwidth[user_name]['device_count'] += 1
                                
                                # 如果这是更大的传输，更新设备信息
                                if avg_kbps > user_bandwidth[user_name]['max_kbps'] * 0.8:
                                    user_bandwidth[user_name]['device_name'] = device_name
                    
                    # 创建合并后的会话列表
                    session_speeds = []
                    total_bandwidth = 0
                    
                    for user_name, user_data in user_bandwidth.items():
                        # 对于播放会话，我们只关心主要的传输流（通常是最大的那个）
                        # 使用最大传输速度，而不是累加所有传输
                        main_bitrate = user_data['max_kbps']
                        
                        # 如果有多个设备，但其中一个明显更大，那就是主传输
                        if user_data['device_count'] > 1:
                            # 如果最大传输远大于其他传输，只保留主传输
                            if main_bitrate > 100:  # 大于100KB/s的传输才算主传输
                                log_manager.log_formatted_event("PLEX_DEBUG", "用户 {0} 有多个传输设备，使用主传输: {1:.2f} KB/s", 
                                                               user_name, main_bitrate)
                            else:
                                # 如果都是小传输，就累加
                                main_bitrate = user_data['total_kbps']
                        
                        total_bandwidth += main_bitrate
                        
                        # 获取媒体比特率信息（从活跃会话）
                        media_bitrate = None
                        if user_data['matched_session']:
                            media_bitrate = user_data['matched_session'].get('media_bitrate')
                        
                        session_speeds.append({
                            'user_name': user_name,
                            'item_name': user_data['matched_session'].get('item_name', 'Unknown') if user_data['matched_session'] else user_data['device_name'],
                            'bitrate': main_bitrate,  # 实际传输速度 KB/s
                            'media_bitrate': media_bitrate,  # 媒体文件比特率（从活跃会话获取）
                            'is_transcoding': False,  # 带宽统计无法直接判断转码
                            'is_estimated': False,  # 这是真实测量的传输速度
                            'device_name': user_data['device_name'],
                            'transfer_type': 'real_bandwidth'  # 标记这是真实带宽数据
                        })
                    
                    log_manager.log_formatted_event("PLEX_DEBUG", "处理完成: 总带宽 {0:.2f} KB/s, 会话数 {1}", 
                                                   total_bandwidth, len(session_speeds))
                    
                    return {
                        'total_bitrate': total_bandwidth,  # 单位：KB/s，实际传输带宽
                        'sessions': session_speeds
                    }
                    
                except (ValueError, KeyError) as e:
                    log_manager.log_formatted_event("PLEX_ERROR", "解析Plex带宽统计失败: {0}", str(e))
                    # 记录响应内容用于调试
                    log_manager.log_formatted_event("PLEX_DEBUG", "原始响应: {0}", response.text[:500])
                    return None
            else:
                log_manager.log_formatted_event("PLEX_ERROR", "获取Plex带宽统计失败: HTTP {0}", response.status_code)
                # 记录响应内容用于调试
                log_manager.log_formatted_event("PLEX_DEBUG", "错误响应: {0}", response.text[:200])
                return None
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("PLEX_ERROR", "获取Plex带宽统计时出错: {0}", str(e))
            return None 