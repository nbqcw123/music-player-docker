# 🎵 Music Player Docker

> **开发版本 v0.1.0-dev** | 在线音乐播放器 - 多源搜索 / 无损格式 / 自适应网页

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 特性

- 🔍 **按需搜索** - 只在需要时搜索，不预加载
- 🎵 **多源选择** - YouTube / Bilibili / 网易云音乐 / SoundCloud / FMA
- 🎧 **格式支持** - FLAC / APE / WAV (无损) + MP3 / AAC / OGG / M4A (有损)
- 📱 **自适应界面** - 深色科技风，完美适配手机/平板/桌面
- 🔥 **推荐列表** - 首页展示各平台热门音乐推荐
- 📋 **播放列表** - 侧边栏播放列表管理
- 🐳 **Docker 部署** - 一键启动，开箱即用

## 🚀 快速开始

### Docker Compose (推荐)

```bash
git clone https://github.com/YOUR_USERNAME/music-player-docker.git
cd music-player-docker
docker-compose up -d
```

访问 http://localhost:8080/player

### Docker 直接运行

```bash
docker build -t music-player:dev .
docker run -d -p 8080:8080 --name music-player music-player:dev
```

### 本地开发

```bash
cd backend
pip install -r requirements.txt
python main.py
```

## 📖 使用说明

1. **浏览推荐** - 打开页面即可看到各平台热门音乐推荐
2. **搜索音乐** - 输入关键词搜索，支持歌曲名/歌手/专辑
3. **切换音源** - 点击顶部音源标签切换搜索来源
4. **播放控制** - 底部播放栏支持播放/暂停/上/下一首/进度拖拽/音量
5. **播放列表** - 点击右侧 📋 按钮打开播放列表

## 🎯 支持的音乐源

| 音源 | 标识 | 格式 | 说明 |
|------|------|------|------|
| YouTube | `youtube` | M4A/MP3 | 全球最大音视频平台 |
| Bilibili | `bilibili` | M4A/FLAC | 国内视频平台音乐区 |
| 网易云音乐 | `netease` | MP3/FLAC | 国内主流音乐平台 |
| SoundCloud | `soundcloud` | MP3/OGG | 独立音乐人平台 |
| Free Music Archive | `fma` | MP3 | 免费音乐档案 |

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/player` | 播放器页面 |
| GET | `/api/sources` | 列出所有音源 |
| GET | `/api/search?q=关键词&source=all` | 搜索音乐 |
| GET | `/api/stream?source=youtube&id=xxx` | 获取播放流 |
| GET | `/api/recommendations` | 获取推荐列表 |
| GET | `/api/proxy?url=xxx` | 音频流代理 |

## 📁 项目结构

```
music-player-docker/
├── backend/
│   ├── main.py           # FastAPI 主应用
│   └── requirements.txt  # Python 依赖
├── Dockerfile            # Docker 构建文件
├── docker-compose.yml    # Docker Compose 配置
└── README.md             # 本文件
```

## ⚠️ 注意事项

- 本项目仅供学习和个人使用
- 部分音源可能受网络环境限制
- 开发版本 (v0.1.0-dev)，功能持续完善中

## 📜 License

MIT License
