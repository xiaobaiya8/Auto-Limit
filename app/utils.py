import ipaddress
import re
from typing import List, Union


def is_private_ip(ip_str: str) -> bool:
    """
    判断IP地址是否为内网地址
    支持IPv4和IPv6
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        # 无效的IP地址
        return False


def is_ip_in_whitelist(ip_str: str, whitelist: List[str]) -> bool:
    """
    判断IP地址是否在白名单中
    支持单个IP、IP范围(CIDR)、域名模式匹配
    """
    if not whitelist:
        return False
    
    try:
        ip = ipaddress.ip_address(ip_str)
        
        for whitelist_item in whitelist:
            whitelist_item = whitelist_item.strip()
            if not whitelist_item:
                continue
                
            try:
                # 尝试CIDR匹配
                if '/' in whitelist_item:
                    network = ipaddress.ip_network(whitelist_item, strict=False)
                    if ip in network:
                        return True
                else:
                    # 尝试单个IP匹配
                    whitelist_ip = ipaddress.ip_address(whitelist_item)
                    if ip == whitelist_ip:
                        return True
            except ValueError:
                # 可能是域名或其他格式，尝试字符串匹配
                if whitelist_item in ip_str:
                    return True
    except ValueError:
        # 输入的IP地址无效，尝试字符串匹配
        for whitelist_item in whitelist:
            whitelist_item = whitelist_item.strip()
            if whitelist_item and whitelist_item in ip_str:
                return True
    
    return False


def is_user_in_whitelist(username: str, whitelist: List[str]) -> bool:
    """
    判断用户名是否在白名单中
    支持完全匹配和通配符匹配
    """
    if not whitelist or not username:
        return False
    
    username = username.strip().lower()
    
    for whitelist_user in whitelist:
        whitelist_user = whitelist_user.strip().lower()
        if not whitelist_user:
            continue
        
        # 完全匹配
        if username == whitelist_user:
            return True
        
        # 通配符匹配
        if '*' in whitelist_user:
            pattern = whitelist_user.replace('*', '.*')
            if re.match(f'^{pattern}$', username):
                return True
    
    return False


def parse_whitelist_text(text: str) -> List[str]:
    """
    解析白名单文本，支持多种分隔符
    """
    if not text:
        return []
    
    # 支持换行、逗号、分号分隔
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            # 支持逗号和分号分隔
            for item in re.split(r'[,;]', line):
                item = item.strip()
                if item:
                    items.append(item)
    
    return items


def should_skip_speed_limit(session_info: dict, server_config: dict) -> bool:
    """
    判断是否应该跳过限速
    根据服务器配置和会话信息决定
    """
    # 如果没有启用本地播放跳过功能，不跳过
    if not server_config.get('skip_local_playback', False):
        return False
    
    client_ip = session_info.get('client_ip', '')
    username = session_info.get('user_name', '')
    
    # 检查IP白名单
    ip_whitelist = parse_whitelist_text(server_config.get('ip_whitelist', ''))
    if is_ip_in_whitelist(client_ip, ip_whitelist):
        return True
    
    # 检查用户白名单
    user_whitelist = parse_whitelist_text(server_config.get('user_whitelist', ''))
    if is_user_in_whitelist(username, user_whitelist):
        return True
    
    # 检查是否为内网IP（如果启用了跳过本地播放）
    if is_private_ip(client_ip):
        return True
    
    return False 