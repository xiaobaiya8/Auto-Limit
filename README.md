# Auto-Limit - 智能下载限速管理工具

[![GitHub stars](https://img.shields.io/github/stars/xiaobaiya8/Auto-Limit?style=flat-square)](https://github.com/xiaobaiya8/Auto-Limit)
[![GitHub forks](https://img.shields.io/github/forks/xiaobaiya8/Auto-Limit?style=flat-square)](https://github.com/xiaobaiya8/Auto-Limit)
[![GitHub issues](https://img.shields.io/github/issues/xiaobaiya8/Auto-Limit?style=flat-square)](https://github.com/xiaobaiya8/Auto-Limit)
[![Docker Pulls](https://img.shields.io/docker/pulls/xiaobaiya000/auto-limit?style=flat-square)](https://hub.docker.com/r/xiaobaiya000/auto-limit)
[![Docker Image Size](https://img.shields.io/docker/image-size/xiaobaiya000/auto-limit/latest?style=flat-square)](https://hub.docker.com/r/xiaobaiya000/auto-limit)
[![Docker Image Version](https://img.shields.io/docker/v/xiaobaiya000/auto-limit?style=flat-square)](https://hub.docker.com/r/xiaobaiya000/auto-limit)
[![License](https://img.shields.io/github/license/xiaobaiya8/Auto-Limit?style=flat-square&cache=none)](https://github.com/xiaobaiya8/Auto-Limit/blob/main/LICENSE)

> **🎉 版本 1.1.0 重大更新**
> - ✨ 新增 **Jellyfin** 和 **Plex** 媒体服务器支持
> - 🔐 添加**安全认证系统**，首次使用需设置管理员账号
> - 🌐 完善**多语言支持**，界面和日志全面中英文双语
> - 🐛 修复多项稳定性问题，提升用户体验

[English](#english) | [中文](#中文)

---

## 中文

### 🎯 什么是 Auto-Limit？

Auto-Limit 是一个专为 **NAS 用户** 和 **家庭媒体服务器** 设计的智能下载限速管理工具。当家人在观看 Emby、Jellyfin 等媒体服务器上的电影时，自动降低 qBittorrent、Transmission 等下载器的速度，确保观影体验流畅不卡顿。

### 🌟 核心功能

- **🎬 智能检测播放状态** - 自动监控 Emby/Jellyfin/Plex 的播放活动
- **⚡ 自动限速切换** - 播放时自动降速，停止播放时恢复正常速度
- **📊 实时速度监控** - 显示下载器实时上传下载速度和媒体服务器比特率
- **🔧 简单易用配置** - Web 界面配置，无需命令行操作
- **🔐 安全认证系统** - 首次使用设置管理员账号，保护系统安全
- **🐳 Docker 一键部署** - 支持 Docker 和 Docker Compose 快速部署
- **📱 响应式界面** - 支持手机、平板、电脑访问
- **🔄 多实例支持** - 同时管理多个下载器和媒体服务器
- **🌐 多语言支持** - 支持中英文界面和日志

### 🎮 支持的软件

#### 媒体服务器
- **Emby** - 完整支持播放检测和比特率监控
- **Jellyfin** - 完整支持播放检测和比特率监控
- **Plex** - 完整支持播放检测和网络速度监控

#### 下载器
- **qBittorrent** - 完整支持限速和实时速度监控
- **Transmission** - 完整支持限速和实时速度监控
- **CloudDrive2** - 支持限速和实时速度监控


**快速运行命令**:
```bash
docker run -d --name autolimit-controller -p 9190:9190 xiaobaiya000/auto-limit:latest
```

启动后访问 `http://localhost:9190`，首次使用需要设置管理员账号密码。

### 🚀 快速开始

#### 方法一：Docker Compose 启动（推荐）

```yaml
version: '3.8'
services:
  auto-limit:
    image: xiaobaiya000/auto-limit:latest
    container_name: auto-limit
    ports:
      - "9190:9190"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

启动后访问 `http://localhost:9190` 进行首次设置。

#### 方法二：Docker 运行

```bash
docker run -d \
  --name auto-limit \
  -p 9190:9190 \
  -v auto-limit-data:/app/data \
  xiaobaiya000/auto-limit:latest
```

#### 方法三：源码运行

```bash
# 克隆项目
git clone https://github.com/xiaobaiya8/Auto-Limit.git
cd Auto-Limit

# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py
```

### ⚙️ 配置指南

#### 1. 添加媒体服务器

1. 在 Web 界面点击"配置"
2. 添加媒体服务器：
   
   **Emby 配置**：
   - **名称**：自定义名称（如：客厅 Emby）
   - **地址**：`http://你的NAS地址:8096`
   - **API 密钥**：在 Emby 控制台 → API 密钥中生成
   - **轮询间隔**：建议 15 秒
   
   **Jellyfin 配置**：
   - **名称**：自定义名称（如：主 Jellyfin）
   - **地址**：`http://你的NAS地址:8096`
   - **API 密钥**：在 Jellyfin 控制台 → API 密钥中生成
   - **轮询间隔**：建议 15 秒
   
   **Plex 配置**：
   - **名称**：自定义名称（如：家庭 Plex）
   - **地址**：`http://你的NAS地址:32400`
   - **API 密钥**：在 Plex 设置 → 常规 → 令牌中获取
   - **轮询间隔**：建议 15 秒

#### 2. 添加下载器

1. 添加 qBittorrent：
   - **名称**：自定义名称（如：主下载器）
   - **地址**：`http://你的NAS地址:8080`
   - **用户名/密码**：qBittorrent 的登录账号
   - **默认限速**：正常下载速度（如：下载 0 KB/s，上传 1024 KB/s）
   - **播放时限速**：观影时的限制速度（如：下载 1024 KB/s，上传 512 KB/s）

#### 3. 开始使用

配置完成后，Auto-Limit 会自动：
- 监控 Emby 的播放状态
- 当有人开始观看时，自动降低下载速度
- 当播放停止时，恢复正常下载速度

### 📊 界面预览

主界面显示：
- **播放状态概览** - 当前是否有人在观看
- **媒体服务器状态** - 显示活跃播放和比特率信息
- **下载器状态** - 显示当前限速模式和实时速度
- **全局速度统计** - 所有下载器的总速度

### 🛠️ 故障排除

#### 常见问题

**Q: 为什么检测不到 Emby 播放状态？**
A: 检查 API 密钥是否正确，确保 Emby 地址可以访问

**Q: qBittorrent 连接失败？**
A: 确认 qBittorrent 开启了 Web UI，用户名密码正确，且为内网地址，外网地址需要关闭某些安全设定

**Q: 限速不生效？**
A: 检查下载器是否正在下载任务，无任务时限速不会显示效果


### 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/新功能`)
3. 提交更改 (`git commit -am '添加新功能'`)
4. 推送到分支 (`git push origin feature/新功能`)
5. 创建 Pull Request

### 📄 许可证

本项目采用 [MIT 许可证](LICENSE)

### 🙏 致谢

感谢以下开源项目：
- [Flask](https://flask.palletsprojects.com/) - Web 框架
- [Bootstrap](https://getbootstrap.com/) - UI 框架
- [qBittorrent](https://www.qbittorrent.org/) - BitTorrent 客户端
- [Emby](https://emby.media/) - 媒体服务器

---

## English

> **🎉 Version 1.1.0 Major Update**
> - ✨ Added **Jellyfin** and **Plex** media server support
> - 🔐 Added **secure authentication system**, admin account setup required on first use
> - 🌐 Enhanced **multi-language support**, comprehensive Chinese/English UI and logs
> - 🐛 Fixed multiple stability issues, improved user experience

### 🎯 What is Auto-Limit?

Auto-Limit is an intelligent download speed management tool designed specifically for **NAS users** and **home media server** enthusiasts. It automatically reduces the speed of downloaders like qBittorrent and Transmission when family members are watching movies on media servers like Emby or Jellyfin, ensuring smooth streaming without buffering.

### 🌟 Key Features

- **🎬 Smart Playback Detection** - Automatically monitors Emby/Jellyfin/Plex playback activities
- **⚡ Automatic Speed Switching** - Reduces speed during playback, restores normal speed when stopped
- **📊 Real-time Speed Monitoring** - Shows real-time upload/download speeds and media server bitrates
- **🔧 Easy Web Configuration** - Web interface setup, no command line required
- **🔐 Secure Authentication System** - First-time setup for admin account to protect system security
- **🐳 One-Click Docker Deployment** - Supports Docker and Docker Compose for quick deployment
- **📱 Responsive Interface** - Works on phones, tablets, and computers
- **🔄 Multi-Instance Support** - Manage multiple downloaders and media servers simultaneously
- **🌐 Multi-language Support** - Supports Chinese and English for both the UI and logs

### 🎮 Supported Software

#### Media Servers
- **Emby** - Full support for playback detection and bitrate monitoring
- **Jellyfin** - Full support for playback detection and bitrate monitoring
- **Plex** - Full support for playback detection and network speed monitoring

#### Downloaders
- **qBittorrent** - Full support for speed limiting and real-time monitoring
- **Transmission** - Full support for speed limiting and real-time monitoring
- **CloudDrive2** - Support for speed limiting and real-time monitoring

### 🐳 Docker Image

**Docker Hub Repository**: [xiaobaiya000/auto-limit](https://hub.docker.com/r/xiaobaiya000/auto-limit)

**Quick Run Command**:
```bash
docker run -d --name autolimit-controller -p 9190:9190 xiaobaiya000/auto-limit:latest
```

After startup, visit `http://localhost:9190` and set up an admin account on first use.

### 🚀 Quick Start

#### Method 1: Docker Compose Startup (Recommended)

```yaml
version: '3.8'
services:
  auto-limit:
    image: xiaobaiya000/auto-limit:latest
    container_name: auto-limit
    ports:
      - "9190:9190"
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

After startup, visit `http://localhost:9190` for initial setup.

#### Method 2: Docker Run

```bash
docker run -d \
  --name auto-limit \
  -p 9190:9190 \
  -v auto-limit-data:/app/data \
  xiaobaiya000/auto-limit:latest
```

#### Method 3: Source Code

```bash
# Clone project
git clone https://github.com/xiaobaiya8/Auto-Limit.git
cd Auto-Limit

# Install dependencies
pip install -r requirements.txt

# Start service
python run.py
```

### ⚙️ Configuration Guide

#### 1. Add Media Server

1. Click "Configuration" in the web interface
2. Add Media Server:
   
   **Emby Configuration**:
   - **Name**: Custom name (e.g., Living Room Emby)
   - **URL**: `http://your-nas-ip:8096`
   - **API Key**: Generate in Emby Dashboard → API Keys
   - **Poll Interval**: Recommended 15 seconds
   
   **Jellyfin Configuration**:
   - **Name**: Custom name (e.g., Main Jellyfin)
   - **URL**: `http://your-nas-ip:8096`
   - **API Key**: Generate in Jellyfin Dashboard → API Keys
   - **Poll Interval**: Recommended 15 seconds
   
   **Plex Configuration**:
   - **Name**: Custom name (e.g., Home Plex)
   - **URL**: `http://your-nas-ip:32400`
   - **API Key**: Get from Plex Settings → General → Token
   - **Poll Interval**: Recommended 15 seconds

#### 2. Add Downloader

1. Add qBittorrent:
   - **Name**: Custom name (e.g., Main Downloader)
   - **URL**: `http://your-nas-ip:8080`
   - **Username/Password**: qBittorrent login credentials
   - **Default Limits**: Normal download speeds (e.g., Download 0 KB/s, Upload 1024 KB/s)
   - **Playback Limits**: Speeds during streaming (e.g., Download 1024 KB/s, Upload 512 KB/s)

#### 3. Start Using

After configuration, Auto-Limit will automatically:
- Monitor Emby playback status
- Reduce download speeds when someone starts watching
- Restore normal speeds when playback stops

### 📊 Interface Preview

Main interface shows:
- **Playback Status Overview** - Whether someone is currently watching
- **Media Server Status** - Shows active playback and bitrate information
- **Downloader Status** - Shows current speed limit mode and real-time speeds
- **Global Speed Statistics** - Total speeds from all downloaders

### 🛠️ Troubleshooting

#### Common Issues

**Q: Why can't it detect Emby playback status?**
A: Check if the API key is correct and ensure Emby URL is accessible

**Q: qBittorrent connection failed?**
A: Confirm qBittorrent Web UI is enabled and credentials are correct, and use internal network address. For external addresses, certain security settings need to be disabled

**Q: Speed limiting not working?**
A: Check if downloader has active tasks, speed limits won't show effect without downloads

### 🤝 Contributing

Issues and Pull Requests are welcome!

1. Fork this project
2. Create feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create Pull Request

### 📄 License

This project is licensed under the [MIT License](LICENSE)

### 🙏 Acknowledgments

Thanks to these open source projects:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Bootstrap](https://getbootstrap.com/) - UI framework
- [qBittorrent](https://www.qbittorrent.org/) - BitTorrent client
- [Emby](https://emby.media/) - Media server

---

### 📞 联系我们 | Contact Us

- **GitHub Issues**: [Report bugs or request features](https://github.com/xiaobaiya8/Auto-Limit/issues)
- **Discussions**: [Join community discussions](https://github.com/xiaobaiya8/Auto-Limit/discussions)
- **Telegram 交流群**: [加入 Telegram 群组讨论](https://t.me/douban_rss)
- **Telegram Group**: [Join Telegram group for discussions](https://t.me/douban_rss)

### 🏷️ 标签 | Tags

`NAS` `媒体服务器` `下载管理` `限速` `Emby` `qBittorrent` `Transmission` `Docker` `家庭影院` `智能限速` `media-server` `download-manager` `speed-limit` `home-theater` `smart-throttling` 