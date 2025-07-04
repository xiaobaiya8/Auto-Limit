#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloudDrive2 Python客户端
用于连接CloudDrive2服务器并进行各种操作，包括设置上传速度
"""

import requests
import json
import base64
import struct
from typing import Optional, Dict, Any
from datetime import datetime

class CloudDriveClient:
    def __init__(self, server_url: str = "https://cd2.baiya.co"):
        """
        初始化CloudDrive客户端
        
        Args:
            server_url: CloudDrive服务器地址
        """
        self.server_url = server_url.rstrip('/')
        self.token = None
        self.session = requests.Session()
        
        # 设置默认headers
        self.session.headers.update({
            'Content-Type': 'application/grpc-web',
            'grpc-accept-encoding': 'identity,gzip,deflate',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'x-user-agent': 'grpc-dotnet/2.67.0, (.NET 7.0.20; CLR 7.0.20; net7.0; wasm)'
        })
    
    def _encode_protobuf_message(self, message_dict: Dict[str, Any]) -> bytes:
        """
        简单的protobuf编码（仅支持基本类型）
        这是一个简化版本，实际使用中建议使用protobuf库
        """
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
                # 数字类型 (wire type 0 for int, wire type 1 for double)
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
    
    def _encode_varint(self, value: int) -> bytes:
        """编码varint"""
        result = b''
        while value >= 0x80:
            result += bytes([value & 0x7F | 0x80])
            value >>= 7
        result += bytes([value & 0x7F])
        return result
    
    def _decode_protobuf_response(self, data: bytes) -> Dict[str, Any]:
        """
        简单的protobuf解码
        这是一个简化版本，实际使用中建议使用protobuf库
        """
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
    
    def _make_grpc_request(self, service_method: str, message_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        发送gRPC请求
        
        Args:
            service_method: 服务方法名
            message_dict: 消息字典
            
        Returns:
            响应字典
        """
        url = f"{self.server_url}/clouddrive.CloudDriveFileSrv/{service_method}"
        
        # 编码消息
        if message_dict:
            message_data = self._encode_protobuf_message(message_dict)
        else:
            message_data = b''
        
        # gRPC-Web格式：5字节头部 + 消息数据
        # 头部：1字节压缩标志 + 4字节消息长度（big-endian）
        grpc_data = b'\x00' + struct.pack('>I', len(message_data)) + message_data
        
        headers = dict(self.session.headers)
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        try:
            response = self.session.post(url, data=grpc_data, headers=headers)
            response.raise_for_status()
            
            # 解析gRPC-Web响应
            response_data = response.content
            if len(response_data) < 5:
                return {}
            
            # 跳过5字节头部
            message_data = response_data[5:]
            return self._decode_protobuf_response(message_data)
            
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return {}
    
    def get_token(self, username: str, password: str) -> bool:
        """
        获取JWT Token
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            是否成功获取token
        """
        message = {
            '1': username,  # userName
            '2': password   # password
        }
        
        response = self._make_grpc_request('GetToken', message)
        
        if response.get(1) == 1:  # success field
            self.token = response.get(3)  # token field
            print(f"登录成功，Token: {self.token}")
            return True
        else:
            error_msg = response.get(2, '未知错误')
            print(f"登录失败: {error_msg}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        
        Returns:
            系统信息字典
        """
        response = self._make_grpc_request('GetSystemInfo')
        return response
    
    def get_system_settings(self) -> Dict[str, Any]:
        """
        获取系统设置
        
        Returns:
            系统设置字典
        """
        response = self._make_grpc_request('GetSystemSettings')
        return response
    
    def set_upload_speed(self, speed_kbps: float) -> bool:
        """
        设置上传速度限制
        
        Args:
            speed_kbps: 上传速度限制（KB/s），0表示无限制
            
        Returns:
            是否设置成功
        """
        # 构建SystemSettings消息
        # 根据proto文件，maxUploadSpeedKBytesPerSecond是字段12
        message = {
            '12': speed_kbps  # maxUploadSpeedKBytesPerSecond
        }
        
        response = self._make_grpc_request('SetSystemSettings', message)
        
        # SetSystemSettings返回Empty消息，通常只有字段0（表示消息结束）
        # 如果有响应且没有错误字段，认为设置成功
        if response and 0 in response:
            print(f"上传速度设置成功: {speed_kbps} KB/s")
            return True
        elif not response:
            print(f"上传速度设置成功: {speed_kbps} KB/s")
            return True
        else:
            print(f"上传速度设置失败: {response}")
            return False
    
    def set_download_speed(self, speed_kbps: float) -> bool:
        """
        设置下载速度限制
        
        Args:
            speed_kbps: 下载速度限制（KB/s），0表示无限制
            
        Returns:
            是否设置成功
        """
        # 构建SystemSettings消息
        # 根据proto文件，maxDownloadSpeedKBytesPerSecond是字段11
        message = {
            '11': speed_kbps  # maxDownloadSpeedKBytesPerSecond
        }
        
        response = self._make_grpc_request('SetSystemSettings', message)
        
        # SetSystemSettings返回Empty消息，通常只有字段0（表示消息结束）
        # 如果有响应且没有错误字段，认为设置成功
        if response and 0 in response:
            print(f"下载速度设置成功: {speed_kbps} KB/s")
            return True
        elif not response:
            print(f"下载速度设置成功: {speed_kbps} KB/s")
            return True
        else:
            print(f"下载速度设置失败: {response}")
            return False
    
    def get_upload_file_list(self) -> Dict[str, Any]:
        """
        获取上传文件列表
        
        Returns:
            上传文件列表
        """
        response = self._make_grpc_request('GetUploadFileList')
        return response
    
    def get_account_status(self) -> Dict[str, Any]:
        """
        获取账户状态
        
        Returns:
            账户状态信息
        """
        response = self._make_grpc_request('GetAccountStatus')
        return response


def main():
    """主函数，演示如何使用CloudDrive客户端"""
    # 创建客户端
    client = CloudDriveClient("https://cd2.baiya.co")
    
    # 登录
    username = "baiya611@gmail.com"
    password = "Clouddrive123456.."
    
    print("正在登录...")
    if not client.get_token(username, password):
        print("登录失败，程序退出")
        return
    
    # 获取系统信息
    print("\n获取系统信息...")
    system_info = client.get_system_info()
    print(f"系统信息: {system_info}")
    
    # 获取当前系统设置
    print("\n获取当前系统设置...")
    settings = client.get_system_settings()
    print(f"当前系统设置: {settings}")
    
    # 设置上传速度为5000 KB/s
    print("\n设置上传速度为5000 KB/s...")
    client.set_upload_speed(0.0)
    
    # 设置下载速度为1000 KB/s
    print("\n设置下载速度为1000 KB/s...")
    client.set_download_speed(0.0)
    
    # 验证设置是否生效
    print("\n验证设置是否生效...")
    new_settings = client.get_system_settings()
    current_upload_speed = new_settings.get(12, 0)
    current_download_speed = new_settings.get(11, 0)
    print(f"当前上传速度限制: {current_upload_speed} KB/s")
    print(f"当前下载速度限制: {current_download_speed} KB/s")
    
    # 获取账户状态
    print("\n获取账户状态...")
    account_status = client.get_account_status()
    print(f"账户状态: {account_status}")
    
    # 获取上传文件列表
    print("\n获取上传文件列表...")
    upload_list = client.get_upload_file_list()
    print(f"上传文件列表: {upload_list}")
    
    print("\n操作完成！")


if __name__ == "__main__":
    main() 