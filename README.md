# 🎵 Music Player Docker

> **v0.3.3** | 在线音乐播放器 - 多源搜索 / SPA 界面 / 国内音源优化

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 特性

- 🔍 **全局搜索** - 自动搜索所有源（网易云/QQ/酷狗/B站/网盘），合并去重，用户不感知来源
- ✅ **搜索预检测** - 自动检测链接可用性，只显示能播放的歌曲
- 🎵 **SPA 界面** - 单页应用，多视图路由（首页/搜索/正在播放/播放列表）
- 🎧 **格式支持** - FLAC / APE / WAV (无损) + MP3 / AAC / OGG / M4A (有损)
- 📱 **自适应界面** - 深色科技风，完美适配手机/平板/桌面
- 🔥 **推荐列表** - 各平台热门音乐推荐，并发加载
- 📜 **歌词显示** - 正在播放页面展示滚动歌词
- ⬇️ **下载功能** - 播放栏和搜索结果均支持下载
- 🎛️ **播放模式** - 列表循环 / 随机播放 / 单曲循环
- ⌨️ **键盘快捷键** - 空格播放/暂停、左右快进/快退、上下调音量、M静音
- 🐳 **Docker 部署** - 一键启动，开箱即用
- 🏠 **NAS 支持** - 飞牛 NAS / 群辉 NAS 均支持
- 💾 **网盘音乐** - 支持百度网盘/阿里云盘/夸克网盘（需配置token）

## 🚀 快速开始

### 通用 Docker 部署（最新版本）

```bash
# 1. 拉取最新代码
git clone https://github.com/nbqcw123/music-player-docker.git
cd music-player-docker

# 2. 构建镜像（首次加 --no-cache）
docker build --no-cache -t music-player:latest .

# 3. 运行容器
docker run -d -p 8080:8080 --name music-player music-player:latest

# 4. 访问 http://localhost:8080/player
```

### 指定版本部署

```bash
git clone https://github.com/nbqcw123/music-player-docker.git
cd music-player-docker
git checkout v0.3.3

docker build --no-cache -t music-player:0.3.3 .
docker run -d -p 8080:8080 --name music-player music-player:0.3.3
```

### Docker Compose

```bash
docker compose up -d
```

---

## 🏠 NAS 安装指南

### 飞牛 NAS (FnOS)

详见 [`fnos/安装说明.md`](fnos/安装说明.md)

```bash
cd fnos
docker build --no-cache -t music-player:latest .
docker compose up -d
```

### 群辉 NAS (Synology)

详见 [`synology/安装说明.md`](synology/安装说明.md)

```bash
# SSH 登录群辉后
cd /volume1/docker/music-player
sudo docker compose build --no-cache
sudo docker compose up -d
```

---

## 📖 使用说明

1. **浏览推荐** - 打开页面即可看到各平台热门音乐推荐
2. **搜索音乐** - 输入关键词全局搜索，自动过滤不可播放的歌曲
3. **播放控制** - 底部播放栏支持播放/暂停/上/下一首/进度拖拽/音量
4. **歌词显示** - 点击"正在播放"查看歌词
5. **下载歌曲** - 点击播放栏或搜索结果旁的下载按钮
6. **键盘快捷键** - 空格(播放/暂停)、←→(快进/快退)、↑↓(音量)、M(静音)

## 🎯 支持的音乐源

| 音源 | 标识 | 格式 | 说明 |
|------|------|------|------|
| 网易云音乐 | `netease` | MP3/FLAC | 国内主流音乐平台 |
| QQ音乐 | `qq` | M4A/FLAC | 腾讯音乐平台 |
| 酷狗音乐 | `kugou` | MP3/FLAC | 酷狗音乐平台 |
| Bilibili | `bilibili` | M4A | B站视频音频提取 |
| YouTube | `youtube` | M4A/MP3 | 国内不可用 |
| 百度网盘 | `baidupan` | 原始格式 | 需配置 BAIDUPAN_ACCESS_TOKEN |
| 阿里云盘 | `aliyun` | 原始格式 | 需配置 ALIYUN_REFRESH_TOKEN |
| 夸克网盘 | `quark` | 原始格式 | 需配置 QUARK_COOKIE |

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查（返回版本号） |
| GET | `/player` | 播放器页面 |
| GET | `/api/sources` | 列出所有音源 |
| GET | `/api/search?q=关键词&source=all&check=true` | 搜索音乐（check预检测可用性） |
| GET | `/api/stream?source=xxx&id=xxx` | 获取播放流 |
| GET | `/api/check?url=xxx` | 检测链接可用性 |
| GET | `/api/proxy?url=xxx` | 音频流代理（自动设置Referer） |
| GET | `/api/lyric?source=xxx&id=xxx` | 获取歌词 |
| GET | `/api/recommendations` | 获取推荐列表 |

## 📁 项目结构

```
music-player-docker/
├── fnos/                   # 飞牛 NAS 部署
│   ├── main.py             # 主应用（FastAPI + SPA）
│   ├── Dockerfile          # 飞牛 NAS 专用 Dockerfile
│   ├── docker-compose.yml  # 飞牛 NAS Docker Compose
│   └── 安装说明.md         # 飞牛 NAS 安装指南
├── synology/               # 群辉 NAS 部署
│   ├── Dockerfile          # 群辉 NAS 专用 Dockerfile
│   ├── docker-compose.yml  # 群辉 NAS Docker Compose
│   └── 安装说明.md         # 群辉 NAS 安装指南
├── CHANGELOG.md            # 更新日志
└── README.md               # 本文件
```

## 📜 更新日志

### v0.3.3 (2026-06-04)
- 🎬 **B站播放修复** — 改用B站API直接获取DASH音频流，替代yt-dlp（解决防盗链）
- 🔗 **Proxy动态Referer** — 根据URL域名自动设置对应Referer
- ✅ **搜索预检测** — 搜索后自动并发检测前30首链接可用性，只返回能播放的歌曲

### v0.3.2 (2026-06-03)
- 🏠 新增群辉 NAS 安装支持
- 📦 版本管理说明

### v0.3.1 (2026-06-03)
- 🐛 修复版本号 API 返回值
- 🐛 修复 Docker 构建缓存问题

### v0.3.0 (2026-06-03)
- 🎵 新增 QQ音乐、酷狗音乐源
- 🐛 修复网易云/B站搜索API
- ⚡ 推荐列表并发加载

### v0.2.0-spa (2026-06-03)
- 🏗️ 完整 SPA 架构重构
- 🎛️ 播放模式切换、历史记录、歌词界面
- ⌨️ 键盘快捷键、PWA支持

### v0.1.0-dev (2026-06-02)
- 初始开发版本

## ⚠️ 注意事项

- 本项目仅供学习和个人使用
- 部分音源可能受网络环境限制
- 国内用户首次构建请加 `--no-cache`
- 搜索预检测默认开启，搜索后只显示能播放的歌曲

## 📜 License

MIT License
