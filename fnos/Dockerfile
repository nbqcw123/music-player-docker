# 使用 DaoCloud 镜像加速
FROM m.daocloud.io/docker.io/library/python:3.11-slim

LABEL maintainer="Music Player Docker"
LABEL version="0.3.1"
LABEL description="在线音乐播放器 - 多源搜索/SPA界面/国内音源 v0.3.1"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

# 使用清华 apt 镜像加速
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 使用清华 pip 镜像加速
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    fastapi==0.111.0 \
    uvicorn[standard]==0.30.1 \
    aiohttp==3.9.5 \
    yt-dlp==2024.5.27 \
    python-multipart==0.0.9 \
    pydantic==2.7.4 \
    lxml==5.2.2 \
    beautifulsoup4==4.12.3 \
    feedparser==6.0.11 \
    aiodns==3.2.0 \
    Brotli==1.1.0 \
    certifi==2024.6.2

COPY main.py .

RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; find . -name "*.pyc" -delete 2>/dev/null; true

RUN mkdir -p /tmp/music_cache

EXPOSE 8080

CMD ["python", "-B", "main.py"]
