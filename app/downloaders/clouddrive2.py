import requests
import json
import struct
from typing import Dict, Any, Optional
from .base import DownloaderBase
from ..services.log_manager import log_manager

class CloudDrive2(DownloaderBase):
    """CloudDrive2下载器的实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        # 从配置中读取保存的token
        self.token = self.config.get('saved_token')
        self.session = requests.Session()
        
        # 设置默认headers
        self.session.headers.update({
            'Content-Type': 'application/grpc-web',
            'grpc-accept-encoding': 'identity,gzip,deflate',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-user-agent': 'grpc-dotnet/2.67.0, (.NET 7.0.20; CLR 7.0.20; net7.0; wasm)'
        })
    
    def _encode_varint(self, value: int) -> bytes:
        """编码varint"""
        result = b''
        while value >= 0x80:
            result += bytes([value & 0x7F | 0x80])
            value >>= 7
        result += bytes([value & 0x7F])
        return result
    
    def _decode_varint(self, data: bytes, pos: int) -> tuple:
        """解码varint"""
        result = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                break
            shift += 7
        return result, pos
    
    def _encode_protobuf_message(self, message_dict: Dict[str, Any]) -> bytes:
        """简单的protobuf编码"""
        def encode_field(field_num: int, value: Any) -> bytes:
            if isinstance(value, str):
                # String类型 (wire type 2)
                encoded_value = value.encode('utf-8')
                length = len(encoded_value)
                key = (field_num << 3) | 2
                return self._encode_varint(key) + self._encode_varint(length) + encoded_value
            elif isinstance(value, bool):
                # Bool类型 (wire type 0)
                key = (field_num << 3) | 0
                return self._encode_varint(key) + self._encode_varint(1 if value else 0)
            elif isinstance(value, (int, float)):
                # 数字类型
                if isinstance(value, float):
                    key = (field_num << 3) | 1
                    return self._encode_varint(key) + struct.pack('<d', value)
                else:
                    key = (field_num << 3) | 0
                    return self._encode_varint(key) + self._encode_varint(value)
            return b''
        
        result = b''
        for field_num, value in message_dict.items():
            if value is not None:
                result += encode_field(int(field_num), value)
        return result
    
    def _decode_protobuf_response(self, data: bytes) -> Dict[str, Any]:
        """简单的protobuf解码"""
        result = {}
        pos = 0
        
        while pos < len(data):
            # 读取key
            key, pos = self._decode_varint(data, pos)
            if pos >= len(data):
                break
                
            field_num = key >> 3
            wire_type = key & 0x07
            
            if wire_type == 0:  # Varint
                value, pos = self._decode_varint(data, pos)
                result[field_num] = value
            elif wire_type == 1:  # 64-bit
                if pos + 8 > len(data):
                    break
                value = struct.unpack('<d', data[pos:pos+8])[0]
                pos += 8
                result[field_num] = value
            elif wire_type == 2:  # Length-delimited
                length, pos = self._decode_varint(data, pos)
                if pos + length > len(data):
                    break
                value = data[pos:pos+length]
                try:
                    result[field_num] = value.decode('utf-8')
                except:
                    result[field_num] = value
                pos += length
            else:
                break
        
        return result
    
    def _make_grpc_request(self, service_method: str, message_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送gRPC请求"""
        url = f"{self.url}/clouddrive.CloudDriveFileSrv/{service_method}"
        
        # 编码消息
        if message_dict:
            message_data = self._encode_protobuf_message(message_dict)
        else:
            message_data = b''
        
        # gRPC-Web格式：5字节头部 + 消息数据
        grpc_data = b'\x00' + struct.pack('>I', len(message_data)) + message_data
        
        headers = dict(self.session.headers)
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            response = self.session.post(url, data=grpc_data, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析gRPC-Web响应
            response_data = response.content
            if len(response_data) < 5:
                return {}
            
            # 跳过5字节头部
            message_data = response_data[5:]
            return self._decode_protobuf_response(message_data)
            
        except requests.exceptions.RequestException as e:
            # 检查是否是401错误（token过期）
            try:
                if hasattr(e, 'response') and e.response and e.response.status_code == 401 and service_method != 'GetToken':
                    log_manager.log_event("CLOUDDRIVE2", f"CloudDrive2 token已过期，需要重新登录")
                    # 清除过期的token
                    self.token = None
                    self._save_token_to_config(None)
                elif 'response' in locals() and response.status_code == 401 and service_method != 'GetToken':
                    log_manager.log_event("CLOUDDRIVE2", f"CloudDrive2 token已过期，需要重新登录")
                    # 清除过期的token
                    self.token = None
                    self._save_token_to_config(None)
            except:
                pass
            
            log_manager.log_event("CLOUDDRIVE2_ERROR", f"gRPC请求失败: {str(e)}")
            return {}
    
    def _save_token_to_config(self, token):
        """保存token到配置文件"""
        try:
            from ..services.config_manager import config_manager
            
            # 获取当前配置
            settings = config_manager.get_settings()
            
            # 查找当前实例并更新token
            instance_id = self.config.get('id')
            if instance_id:
                for downloader in settings.get('downloaders', []):
                    if downloader.get('id') == instance_id:
                        if token:
                            downloader['saved_token'] = token
                        else:
                            # 清除过期的token
                            downloader.pop('saved_token', None)
                        break
                
                # 保存配置（静默保存，不记录日志）
                config_manager.save_settings(settings)
            
        except Exception as e:
            log_manager.log_event("CLOUDDRIVE2_ERROR", f"保存CloudDrive2 token时出错: {str(e)}")

    def login(self):
        """登录获取Token"""
        if not self.url or not self.username or not self.password:
            return False
            
        try:
            message = {
                '1': self.username,  # userName
                '2': self.password   # password
            }
            
            response = self._make_grpc_request('GetToken', message)
            
            if response.get(1) == 1:  # success field
                old_token = self.token
                new_token = response.get(3)  # token field
                self.token = new_token
                
                # 保存token到配置文件
                self._save_token_to_config(new_token)
                
                if old_token:
                    log_manager.log_event("CLOUDDRIVE2", f"CloudDrive2重新登录成功")
                else:
                    log_manager.log_event("CLOUDDRIVE2", f"CloudDrive2登录成功")
                return True
            else:
                error_msg = response.get(2, '未知错误')
                log_manager.log_event("CLOUDDRIVE2_ERROR", f"CloudDrive2登录失败: {error_msg}")
                return False
                
        except Exception as e:
            log_manager.log_event("CLOUDDRIVE2_ERROR", f"CloudDrive2登录异常: {str(e)}")
            return False
    
    def set_speed_limits(self, download_limit_kb, upload_limit_kb):
        """设置速度限制"""
        # 检查token状态
        if not self.token:
            # 无token，需要登录
            if not self.login():
                return False
        
        def _try_set_speed_with_retry():
            """尝试设置速度，失败时重新登录重试一次"""
            success = True
            
            # 设置下载速度限制
            if download_limit_kb >= 0:
                download_message = {
                    '11': float(download_limit_kb)  # maxDownloadSpeedKBytesPerSecond
                }
                download_response = self._make_grpc_request('SetSystemSettings', download_message)
                if not download_response and download_response != {}:
                    success = False
            
            # 设置上传速度限制
            if upload_limit_kb >= 0:
                upload_message = {
                    '12': float(upload_limit_kb)  # maxUploadSpeedKBytesPerSecond
                }
                upload_response = self._make_grpc_request('SetSystemSettings', upload_message)
                if not upload_response and upload_response != {}:
                    success = False
            
            return success
        
        try:
            # 第一次尝试（使用现有token）
            success = _try_set_speed_with_retry()
            
            # 如果失败，可能是token过期，重新登录后再试一次
            if not success:
                # 清除当前token，强制重新登录
                self.token = None
                if self.login():
                    success = _try_set_speed_with_retry()
            
            if success:
                # 不再记录成功日志，由调度器统一记录
                return True
            else:
                log_manager.log_event("CLOUDDRIVE2_ERROR", f"CloudDrive2速率限制设置失败")
                return False
                
        except Exception as e:
            log_manager.log_event("CLOUDDRIVE2_ERROR", f"CloudDrive2设置速率限制时出错: {str(e)}")
            return False
    
    def test_connection(self):
        """测试连接"""
        if not self.url or not self.username or not self.password:
            return False, "CloudDrive2 URL、用户名或密码未配置"
        
        if self.login():
            # 尝试获取系统信息来验证连接
            try:
                system_info = self._make_grpc_request('GetSystemInfo')
                if system_info or system_info == {}:
                    return True, "连接成功"
                else:
                    return False, "连接失败，无法获取系统信息"
            except Exception as e:
                return False, f"连接测试失败: {str(e)}"
        else:
            return False, "连接失败，请检查URL、用户名和密码" 