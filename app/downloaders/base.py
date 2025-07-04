from abc import ABC, abstractmethod

class DownloaderBase(ABC):
    """
    下载器插件的抽象基类。
    所有下载器模块都必须继承此类并实现其方法。
    """
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def set_speed_limits(self, download_limit_kb, upload_limit_kb):
        """
        设置下载和上传速率限制。
        :param download_limit_kb: 下载速率 (KB/s)，0为无限制。
        :param upload_limit_kb: 上传速率 (KB/s)，0为无限制。
        :return: bool -> 是否成功
        """
        pass

    @abstractmethod
    def test_connection(self):
        """
        测试与下载器的连接。
        :return: (bool, str) -> (连接是否成功, 消息)
        """
        pass

    @abstractmethod
    def get_current_speeds(self):
        """
        获取当前实际下载和上传速度。
        :return: dict -> {'download_speed': KB/s, 'upload_speed': KB/s} 或 None
        """
        pass 