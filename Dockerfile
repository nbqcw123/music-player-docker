FROM m.daocloud.io/docker.io/library/python:3.11-slim

LABEL maintainer="Music Player Docker"
LABEL version="0.3.1"
LABEL description="在线音乐播放器 - 多源搜索/SPA界面/国内音源 v0.3.1"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 用 ARG 强制使后续层缓存失效
ARG BUILD_TS=now
RUN echo "Build: $BUILD_TS" > /app/.buildinfo

COPY backend/ .

RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; find . -name "*.pyc" -delete 2>/dev/null; true

RUN mkdir -p /tmp/music_cache

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

CMD ["python", "-B", "main.py"]
