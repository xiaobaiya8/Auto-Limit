import requests
import json
import base64
from .base import DownloaderBase
from ..services.log_manager import log_manager

class Transmission(DownloaderBase):
    """Transmission下载器的实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        self.session = requests.Session()
        self.session_id = None
        
        # 设置基本认证
        if self.username and self.password:
            auth_string = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            self.session.headers.update({
                'Authorization': f'Basic {auth_string}'
            })

    def _get_session_id(self):
        """获取Transmission会话ID"""
        try:
            # 先发送一个请求来获取X-Transmission-Session-Id
            rpc_url = f"{self.url}/transmission/rpc"
            response = self.session.post(rpc_url, timeout=10)
            
            if response.status_code == 409:
                # 409状态码表示需要会话ID
                session_id = response.headers.get('X-Transmission-Session-Id')
                if session_id:
                    self.session_id = session_id
                    self.session.headers.update({
                        'X-Transmission-Session-Id': session_id
                    })
                    return True
            elif response.status_code == 200:
                # 某些版本可能不需要会话ID
                return True
                
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "获取Transmission会话ID失败: HTTP {0}", response.status_code)
            return False
            
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "获取Transmission会话ID时出错: {0}", str(e))
            return False

    def _make_rpc_request(self, method, arguments=None):
        """发送RPC请求到Transmission"""
        if not self._get_session_id():
            return None
            
        try:
            rpc_url = f"{self.url}/transmission/rpc"
            
            rpc_data = {
                "method": method,
                "arguments": arguments or {}
            }
            
            response = self.session.post(
                rpc_url, 
                json=rpc_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    log_manager.log_event("TRANSMISSION_ERROR", "Transmission响应不是有效的JSON")
                    return None
            else:
                log_manager.log_formatted_event("TRANSMISSION_ERROR", "Transmission RPC请求失败: HTTP {0}", response.status_code)
                return None
                
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "Transmission RPC请求时出错: {0}", str(e))
            return None

    def set_speed_limits(self, download_limit_kb, upload_limit_kb):
        """设置速度限制"""
        try:
            # Transmission的速度限制单位是KB/s
            arguments = {}
            
            if download_limit_kb >= 0:
                if download_limit_kb == 0:
                    # 无限制
                    arguments["speed-limit-down-enabled"] = False
                else:
                    arguments["speed-limit-down-enabled"] = True
                    arguments["speed-limit-down"] = int(download_limit_kb)
            
            if upload_limit_kb >= 0:
                if upload_limit_kb == 0:
                    # 无限制
                    arguments["speed-limit-up-enabled"] = False
                else:
                    arguments["speed-limit-up-enabled"] = True
                    arguments["speed-limit-up"] = int(upload_limit_kb)
            
            response = self._make_rpc_request("session-set", arguments)
            
            if response and response.get("result") == "success":
                # 不再记录成功日志，由调度器统一记录
                return True
            else:
                log_manager.log_formatted_event("TRANSMISSION_ERROR", "Transmission速率限制设置失败: {0}", response)
                return False
                
        except Exception as e:
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "Transmission设置速率限制时出错: {0}", str(e))
            return False

    def test_connection(self):
        """测试连接"""
        if not self.url:
            return False, "Transmission URL未配置"
        
        try:
            # 尝试获取会话信息来测试连接
            response = self._make_rpc_request("session-get")
            
            if response and response.get("result") == "success":
                version = response.get("arguments", {}).get("version", "未知版本")
                return True, f"连接成功 (版本: {version})"
            else:
                return False, "连接失败，请检查URL和认证信息"
                
        except Exception as e:
            return False, f"连接测试失败: {str(e)}"

    def get_session_stats(self):
        """获取会话统计信息（可选功能）"""
        try:
            response = self._make_rpc_request("session-stats")
            if response and response.get("result") == "success":
                return response.get("arguments", {})
            return None
        except Exception as e:
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "获取Transmission统计信息时出错: {0}", str(e))
            return None

    def get_current_speeds(self):
        """获取当前实际下载和上传速度"""
        try:
            # 获取会话统计信息
            response = self._make_rpc_request("session-stats")
            
            if response and response.get("result") == "success":
                stats = response.get("arguments", {})
                current_stats = stats.get("current-stats", {})
                
                # Transmission返回的速度单位是字节/秒，需要转换为KB/s
                return {
                    'download_speed': current_stats.get('downloadSpeed', 0) / 1024,  # 转换为KB/s
                    'upload_speed': current_stats.get('uploadSpeed', 0) / 1024       # 转换为KB/s
                }
            else:
                log_manager.log_formatted_event("TRANSMISSION_ERROR", "获取Transmission速度信息失败: {0}", response)
                return None
                
        except Exception as e:
            log_manager.log_formatted_event("TRANSMISSION_ERROR", "获取Transmission速度信息时出错: {0}", str(e))
            return None 