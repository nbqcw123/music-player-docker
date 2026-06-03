# v0.3.2 (2026-06-03)

## 群辉 NAS 支持 + 版本管理

### 新增
- 🏠 **群辉 NAS (Synology) 支持** — 新增 `synology/` 目录，含专用 Dockerfile、docker-compose.yml、安装说明
- 📦 **版本管理** — 默认构建最新版本，支持通过 git tag 指定版本构建
- 📝 **统一 README** — 整合飞牛/群辉/通用 Docker 三种部署方式

### 文档
- 群辉安装说明：SSH / Container Manager 图形界面 / git clone 三种方式
- 指定版本构建说明（`git checkout v0.3.1`）
- 版本管理章节加入 README

---

# v0.3.1 (2026-06-03)

## 版本号修复 + 文档更新

### 修复
- 🐛 **修复版本号 API 返回值** — `GET /` 之前硬编码为 `"0.2.0-spa"`，现在正确返回 `"0.3.1"`
- 🐛 **修复 Docker 构建缓存问题** — 添加 `BUILD_TS` ARG 强制缓存失效，添加 `__pycache__` 清理步骤
- 🐛 **启动命令改为 `python -B`** — 禁止生成 .pyc 字节码缓存

### 文档
- 📝 README 全面更新至 v0.3.1
- 📝 新增 `--no-cache` 构建说明（解决 NAS 上版本号不正确问题）
- 📝 新增飞牛 NAS 专用构建命令
- 📝 更新日志整合到 README

---

# v0.3.0 (2026-06-03)

## 搜索修复 + 新音乐源

### 修复
- 修复网易云搜索API（旧API已失效，改用 `api/cloudsearch/pc`）
- 修复B站搜索API（改用 `x/web-interface/wbi/search/type`）
- 修复所有音源JSON解析（aiohttp 需要 `content_type=None` 处理非标准 Content-Type）
- 播放控制条默认隐藏，播放时才显示

### 新增音乐源
- 🐧 **QQ音乐** - 搜索+播放
- 🎵 **酷狗音乐** - 搜索+播放
- 保留：网易云、B站、YouTube

### 移除
- SoundCloud（国内访问不稳定）
- FMA（服务已关闭）

### 优化
- 推荐列表改为并发加载（网易云+QQ+酷狗+B站），每个源8秒超时
- 搜索单源超时从20s降至8s

---

# v0.2.0-spa (2026-06-03)

## SPA 完整重构

### 新增
- 🏗️ 完整单页应用（SPA）架构，多视图路由切换（首页/搜索/历史/正在播放）
- 🎛️ 播放模式切换：列表循环 / 随机播放 / 单曲循环
- 📜 播放历史记录（localStorage 持久化，最多100条）
- 💿 正在播放视图：大封面展示 + 旋转动画 + 歌词占位
- ⌨️ 键盘快捷键：空格播放/暂停、左右快进/快退、上下调音量、M静音、S聚焦搜索
- 🎯 播放列表支持删除单曲
- 🔔 Toast 消息提示
- 📱 PWA meta 标签支持
- 🎨 全新 UI：渐变色、动画过渡、更好的响应式布局

### 优化
- 搜索框集成到顶部导航，全局可用
- 音源标签支持滚动，移动端友好
- 进度条悬停放大 + 拖拽圆点

---

# v0.1.0-dev (2026-06-02)

## 初始开发版本

### 新增
- 🎵 多音源自搜索：YouTube / Bilibili / 网易云音乐 / SoundCloud / FMA
- 🎧 支持无损格式 (FLAC/APE/WAV) 和有损格式 (MP3/AAC/OGG/M4A)
- 📱 深色科技风自适应网页界面
- 🔥 各平台首页推荐列表
- 📋 侧边栏播放列表管理
- 🐳 Docker / Docker Compose 一键部署
- 🔌 完整 REST API

### 技术栈
- 后端：Python 3.11 + FastAPI + yt-dlp + aiohttp
- 前端：原生 HTML/CSS/JS (无框架依赖)
- 部署：Docker + docker-compose

### 注意事项
- 开发版本，功能持续完善中
- 部分音源可能受网络环境限制

---

# v0.3.2 (2026-06-03)

## 网易云搜索+播放修复

### 调研
- 分析了 myfreemp3.com.cn 和 tonzhon.com 的播放方式
- myfreemp3 使用 musicapi.leanapp.cn（已挂）
- tonzhon 使用自托管 MKOnlineMusicPlayer API

### 修复
- 🔍 **网易云搜索**：改用 tonzhon.com API（稳定可用）
- 🎵 **网易云播放**：改用 music-api.gdstudio.xyz API
- ✅ 搜索结果正常返回，播放链接有效

### 已知限制
- QQ音乐/酷狗音乐播放地址需要认证，暂不可用
- B站播放需要 cookie，暂不可用
- YouTube 国内不可用
- 网盘功能（百度网盘/阿里云盘/夸克）需要配置 token/cookie

---

# v0.3.2 (2026-06-03) [群辉NAS支持]

### 新增
- 🏠 群辉 NAS 安装支持
- 📦 版本管理说明
