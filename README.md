# 🎵 Music Player Docker

> **v0.3.1** | 在线音乐播放器 - 多源搜索 / SPA 界面 / 国内音源优化

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 特性

- 🔍 **多源搜索** - 网易云 / QQ音乐 / 酷狗 / B站 / YouTube，按需搜索不预加载
- 🎵 **SPA 界面** - 单页应用，多视图路由（首页/搜索/历史/正在播放）
- 🎧 **格式支持** - FLAC / APE / WAV (无损) + MP3 / AAC / OGG / M4A (有损)
- 📱 **自适应界面** - 深色科技风，完美适配手机/平板/桌面
- 🔥 **推荐列表** - 各平台热门音乐推荐，并发加载
- 📋 **播放列表** - 侧边栏播放列表管理
- 🎛️ **播放模式** - 列表循环 / 随机播放 / 单曲循环
- 📜 **播放历史** - localStorage 持久化，最多100条
- ⌨️ **键盘快捷键** - 空格播放/暂停、左右快进/快退、M静音、S聚焦搜索
- 🐳 **Docker 部署** - 一键启动，开箱即用
- 🏠 **飞牛 NAS** - 专为飞牛 NAS 优化，支持本地构建

## 🚀 快速开始

### ⚠️ 国内用户（推荐源码构建）

由于 Docker Hub 在国内访问不稳定，**推荐从 GitHub 源码构建**：

```bash
# 1. 克隆项目
git clone https://github.com/nbqcw123/music-player-docker.git
cd music-player-docker

# 2. 构建镜像（约 3-5 分钟，首次构建后后续可去掉 --no-cache）
docker build --no-cache -t music-player:dev .

# 3. 运行容器
docker run -d -p 8080:8080 --name music-player music-player:dev

# 4. 访问 http://你的NAS地址:8080/player
```

> **注意**：首次构建必须加 `--no-cache`，否则可能使用旧缓存导致版本号不正确。后续更新只需 `docker build -t music-player:dev .` 即可。

### 飞牛 NAS 安装

详见 [`fnos/安装说明.md`](fnos/安装说明.md)，支持飞牛 Docker 管理界面导入和 SSH 命令行两种方式。

飞牛 NAS 专用构建：
```bash
cd music-player-docker/fnos
docker build --no-cache -t music-player:dev .
```

### Docker Compose（国际用户）

```bash
git clone https://github.com/nbqcw123/music-player-docker.git
cd music-player-docker
docker-compose up -d
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
6. **视图切换** - 左侧导航切换首页/搜索/历史/正在播放
7. **键盘快捷键** - 空格(播放/暂停)、←→(快进/快退)、M(静音)、S(搜索)

## 🎯 支持的音乐源

| 音源 | 标识 | 格式 | 说明 |
|------|------|------|------|
| 网易云音乐 | `netease` | MP3/FLAC | 国内主流音乐平台 |
| QQ音乐 | `qq` | MP3/FLAC | 腾讯音乐平台 |
| 酷狗音乐 | `kugou` | MP3/FLAC | 酷狗音乐平台 |
| Bilibili | `bilibili` | M4A/FLAC | 国内视频平台音乐区 |
| YouTube | `youtube` | M4A/MP3 | 全球最大音视频平台 |

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查（返回版本号） |
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
├── fnos/
│   ├── main.py           # 飞牛 NAS 专用主应用
│   ├── Dockerfile        # 飞牛 NAS 专用 Dockerfile
│   └── 安装说明.md       # 飞牛 NAS 安装指南
├── Dockerfile            # Docker 构建文件
├── docker-compose.yml    # Docker Compose 配置
├── CHANGELOG.md          # 更新日志
└── README.md             # 本文件
```

## 📜 更新日志

### v0.3.1 (2026-06-03)
- 🐛 修复版本号 API 返回值（之前硬编码为 0.2.0-spa）
- 🐛 修复 Docker 构建缓存导致旧版本问题（添加 --no-cache 说明）
- 📝 更新 README 至最新版本

### v0.3.0 (2026-06-03)
- 🐛 修复网易云搜索API（改用 `api/cloudsearch/pc`）
- 🐛 修复B站搜索API（改用 `x/web-interface/wbi/search/type`）
- 🐛 修复所有音源JSON解析（aiohttp `content_type=None`）
- 🎵 新增 QQ音乐、酷狗音乐源
- ❌ 移除 SoundCloud、FMA（国内访问不稳定/服务关闭）
- ⚡ 推荐列表并发加载，每源8秒超时
- ⚡ 搜索单源超时从20s降至8s
- 🎨 播放控制条默认隐藏，播放时才显示

### v0.2.0-spa (2026-06-03)
- 🏗️ 完整 SPA 架构重构，多视图路由
- 🎛️ 播放模式切换（列表循环/随机/单曲）
- 📜 播放历史记录（localStorage）
- 💿 正在播放视图（大封面+旋转动画）
- ⌨️ 键盘快捷键
- 📱 PWA meta 标签

### v0.1.0-dev (2026-06-02)
- 初始开发版本

## ⚠️ 注意事项

- 本项目仅供学习和个人使用
- 部分音源可能受网络环境限制
- 国内用户首次构建请加 `--no-cache`

## 📜 License

MIT License
