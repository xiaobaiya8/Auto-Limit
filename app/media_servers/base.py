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
        :return: 包含会话信息的列表，例如 [{'user_name': 'test', 'item_name': 'Test Movie'}]
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