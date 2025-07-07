import requests
import json
import time
import urllib.parse
from .base import DownloaderBase
from ..services.log_manager import log_manager
from flask_babel import gettext as _

class Sabnzbd(DownloaderBase):
    """SABnzbd下载器的实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.url = self.config.get('url', '').rstrip('/')
        self.api_key = self.config.get('api_key')
        self.session = requests.Session()
        
        # 最大线路速度配置（KB/s），SABnzbd必需此配置
        self.max_bandwidth_kb = self.config.get('max_bandwidth_kb', 0)
        
        # 如果没有配置最大带宽，设置一个默认值
        if self.max_bandwidth_kb <= 0:
            self.max_bandwidth_kb = 50 * 1024  # 默认50MB/s
            log_manager.log_formatted_event("SABNZBD", _("SABnzbd未配置最大带宽，使用默认值: {0} KB/s"), self.max_bandwidth_kb)

    def _make_api_request(self, params, add_timestamp=True):
        """发送API请求到SABnzbd"""
        if not self.url or not self.api_key:
            return None
            
        try:
            # 构建请求参数，精确匹配Web端格式
            api_params = {
                'apikey': self.api_key,
                'output': 'json'
            }
            api_params.update(params)
            
            # 添加时间戳参数（与Web端保持一致）
            if add_timestamp:
                api_params['_'] = str(int(time.time() * 1000))
            
            # 发送请求
            api_url = f"{self.url}/api"
            response = self.session.get(api_url, params=api_params, timeout=10)
            
            if response.status_code == 200:
                # 对于config API，成功响应可能是空字符串或简单的JSON
                response_text = response.text.strip()
                if response_text:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        # 如果响应包含特定内容，可能表示成功
                        if 'ok' in response_text.lower() or len(response_text) == 0:
                            return {'status': True, 'message': 'success'}
                        return {'status': False, 'error': response_text}
                else:
                    # 空响应可能表示成功
                    return {'status': True, 'message': 'empty_success'}
            else:
                log_manager.log_formatted_event("SABNZBD_ERROR", _("SABnzbd API请求失败: HTTP {0}"), response.status_code)
                return None
                
        except requests.exceptions.RequestException as e:
            log_manager.log_formatted_event("SABNZBD_ERROR", _("SABnzbd API请求时出错: {0}"), str(e))
            return None

    def _set_max_bandwidth(self, max_bandwidth_kb):
        """设置SABnzbd的最大带宽"""
        try:
            # 转换为合适的单位
            if max_bandwidth_kb >= 1024:
                # 使用MB单位
                bandwidth_value = int(max_bandwidth_kb / 1024)
                bandwidth_unit = 'M'
                bandwidth_str = f"{bandwidth_value}M"
            else:
                # 使用KB单位
                bandwidth_value = int(max_bandwidth_kb)
                bandwidth_unit = 'K'
                bandwidth_str = f"{bandwidth_value}K"
            
            # 构建POST数据，基于您提供的参数
            post_data = {
                'apikey': self.api_key,
                'ajax': '1',
                'output': 'json',
                'host': '::',
                'port': '8080',
                'web_dir': 'Glitter - Auto',
                'language': 'zh_CN',
                'https_port': '',
                'https_cert': 'server.cert',
                'https_key': 'server.key',
                'https_chain': '',
                'username': '',
                'password': '',
                'inet_exposure': '0',
                'auto_browser': '1',
                'check_new_rel': '1',
                'enable_https_verification': '1',
                'socks5_proxy_url': '',
                'bandwidth_max_value': str(bandwidth_value),
                'bandwidth_max_dropdown': bandwidth_unit,
                'bandwidth_max': bandwidth_str,
                'bandwidth_perc': '100',
                'cache_limit': '1G'
            }
            
            # 发送POST请求到配置端点
            config_url = f"{self.url}/config/general/saveGeneral"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(config_url, data=post_data, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('value', {}).get('success') == True:
                        log_manager.log_formatted_event("SABNZBD", _("SABnzbd最大带宽设置成功: {0}"), bandwidth_str)
                        return True
                    else:
                        log_manager.log_formatted_event("SABNZBD_ERROR", _("SABnzbd最大带宽设置失败: {0}"), str(result))
                        return False
                except json.JSONDecodeError:
                    log_manager.log_event("SABNZBD_ERROR", _("SABnzbd最大带宽设置响应不是有效JSON"))
                    return False
            else:
                log_manager.log_formatted_event("SABNZBD_ERROR", _("SABnzbd最大带宽设置请求失败: HTTP {0}"), response.status_code)
                return False
                
        except Exception as e:
            log_manager.log_formatted_event("SABNZBD_ERROR", _("设置SABnzbd最大带宽时出错: {0}"), str(e))
            return False

    def _kb_to_percentage(self, target_kb):
        """将KB/s速度转换为百分比（用于显示参考）"""
        if self.max_bandwidth_kb <= 0 or target_kb <= 0:
            return 0
        
        percentage = int((target_kb / self.max_bandwidth_kb) * 100)
        return max(1, min(100, percentage))

    def set_speed_limits(self, download_limit, upload_limit):
        """设置下载和上传速度限制
        
        Args:
            download_limit: 下载限制百分比 (1-100)
            upload_limit: 上传限制 (SABnzbd不支持，忽略)
        """
        try:
            success = True
            
            # 确保最大带宽已设置
            if self.max_bandwidth_kb:
                if not self._set_max_bandwidth(self.max_bandwidth_kb):
                    success = False
            
            # 设置下载限速（百分比）
            if download_limit is not None and download_limit > 0:
                # 直接使用百分比值，不进行计算
                percentage = int(download_limit)
                
                # 设置限速
                params = {
                    'mode': 'config',
                    'name': 'speedlimit',
                    'value': str(percentage)
                }
                
                response = self._make_api_request(params)
                if response:
                    # 验证设置
                    if self._verify_speed_setting(percentage):
                        success = True
                    else:
                        log_manager.log_formatted_event("SABNZBD_ERROR", _("SABnzbd限速验证失败，期望: {0}%"), percentage)
                        success = False
                else:
                    log_manager.log_event("SABNZBD_ERROR", _("SABnzbd限速设置请求失败"))
                    success = False
            
            return success
            
        except Exception as e:
            log_manager.log_formatted_event("SABNZBD_ERROR", _("设置SABnzbd速度限制时出错: {0}"), str(e))
            return False

    def _verify_speed_setting(self, expected_percentage):
        """验证速度设置是否生效"""
        try:
            # 获取当前状态
            queue_response = self._make_api_request({'mode': 'queue'}, add_timestamp=False)
            
            if queue_response and 'queue' in queue_response:
                queue_info = queue_response['queue']
                current_limit_str = queue_info.get('speedlimit', '').strip()
                
                if current_limit_str:
                    try:
                        current_limit = int(float(current_limit_str))
                        
                        # 对100%的特殊处理（可能显示为100或0）
                        if expected_percentage == 100:
                            if current_limit == 100 or current_limit == 0:
                                return True
                        else:
                            # 允许±2的误差范围
                            if abs(current_limit - expected_percentage) <= 2:
                                return True
                            else:
                                log_manager.log_formatted_event("SABNZBD_ERROR", _("限速验证失败: 期望{0}%, 实际{1}%"), expected_percentage, current_limit)
                    except (ValueError, TypeError):
                        log_manager.log_formatted_event("SABNZBD_ERROR", _("无法解析当前限速值: {0}"), current_limit_str)
                        
            return False
            
        except Exception as e:
            log_manager.log_formatted_event("SABNZBD_ERROR", _("验证SABnzbd速度设置时出错: {0}"), str(e))
            return False

    def test_connection(self):
        """测试与SABnzbd的连接"""
        if not self.url or not self.api_key:
            return False, _("SABnzbd URL或API密钥未配置")
        
        # 检查最大带宽配置
        if self.max_bandwidth_kb <= 0:
            return False, _("请配置SABnzbd的最大线路速度")
        
        try:
            # 获取版本信息来测试连接
            response = self._make_api_request({'mode': 'version'})
            
            if response and isinstance(response, dict):
                version = response.get('version', _('未知版本'))
                return True, _("连接成功 (版本: {0}, 最大带宽: {1} KB/s)").format(version, self.max_bandwidth_kb)
            else:
                return False, _("连接失败，请检查URL和API密钥")
                
        except Exception as e:
            return False, _("连接测试失败: {0}").format(str(e))

    def get_current_speeds(self):
        """获取当前下载和上传速度"""
        try:
            queue_response = self._make_api_request({'mode': 'queue'}, add_timestamp=False)
            
            if queue_response and 'queue' in queue_response:
                queue_info = queue_response['queue']
                
                # 获取实际下载速度（KB/s）
                kbpersec_str = queue_info.get('kbpersec', '0')
                try:
                    download_speed = float(kbpersec_str)
                except (ValueError, TypeError):
                    download_speed = 0.0
                
                # 获取当前限速百分比
                speedlimit_str = queue_info.get('speedlimit', '0')
                try:
                    current_limit_percentage = int(float(speedlimit_str))
                except (ValueError, TypeError):
                    current_limit_percentage = 0
                
                return {
                    'download_speed': download_speed,
                    'upload_speed': 0,  # SABnzbd不支持上传
                    'current_limit_percentage': current_limit_percentage  # 添加这个字段供前端显示
                }
            else:
                return {'download_speed': 0, 'upload_speed': 0, 'current_limit_percentage': 0}
                
        except Exception as e:
            log_manager.log_formatted_event("SABNZBD_ERROR", _("获取SABnzbd速度信息时出错: {0}"), str(e))
            return {'download_speed': 0, 'upload_speed': 0, 'current_limit_percentage': 0} 