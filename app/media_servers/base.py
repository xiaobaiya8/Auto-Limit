from abc import ABC, abstractmethod

class MediaServerBase(ABC):
    """
    媒体服务器插件的抽象基类。
    所有媒体服务器模块都必须继承此类并实现其方法。
    """
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def get_active_sessions(self):
        """
        获取当前活跃的、非暂停的播放会话。
        :return: 包含会话信息的列表，每个会话包含以下字段：
                 - session_id: 会话ID
                 - user_name: 用户名
                 - item_name: 媒体项目名称
                 - client_ip: 客户端IP地址（可选）
                 - device_name: 设备名称（可选）
                 如果获取失败，返回 None。
        """
        pass

    @abstractmethod
    def test_connection(self):
        """
        测试与媒体服务器的连接。
        :return: (bool, str) -> (连接是否成功, 消息)
        """
        pass

    def get_network_speeds(self):
        """
        获取当前播放的网络速度信息（可选实现）。
        注意：不同媒体服务器的能力不同：
        - Plex: 可以获取真实的网络传输速度（Session.bandwidth属性）
        - Emby/Jellyfin: 只能获取媒体文件的编码比特率，非实时网络速度
        :return: {'total_bitrate': float, 'sessions': [{'user_name': str, 'bitrate': float}]} 或 None
        """
        return None 