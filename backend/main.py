"""
Music Player Docker - Main Application
开发版本: v0.1.0-dev
"""
import asyncio
import json
import hashlib
import re
import os
from typing import Optional
from urllib.parse import quote, urlparse, parse_qs

import aiohttp
import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(
    title="Music Player Docker",
    description="在线音乐播放器 - 支持多源搜索、无损格式、自适应界面",
    version="0.1.0-dev"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 配置 ───────────────────────────────────────────────
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/music_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# yt-dlp 基础配置
YDL_OPTS_BASE = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "noplaylist": True,
    "socket_timeout": 15,
}

# ─── 数据模型 ───────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    source: str = "all"
    limit: int = 20

class PlayRequest(BaseModel):
    url: str
    source: str = "auto"

# ─── 音乐源搜索引擎 ─────────────────────────────────────

class MusicSourceBase:
    """音乐源基类"""
    name: str = "base"
    display_name: str = "Base"

    async def search(self, query: str, limit: int = 20) -> list:
        raise NotImplementedError

    async def get_stream(self, url_or_id: str) -> dict:
        raise NotImplementedError


class YouTubeSource(MusicSourceBase):
    """YouTube / YouTube Music 源"""
    name = "youtube"
    display_name = "YouTube"

    async def search(self, query: str, limit: int = 20) -> list:
        opts = {
            **YDL_OPTS_BASE,
            "default_search": "ytsearch",
            "extract_flat": True,
        }
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                entries = info.get("entries", []) if info else []
                for entry in entries:
                    if not entry:
                        continue
                    results.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("channel", entry.get("uploader", "Unknown")),
                        "duration": entry.get("duration", 0),
                        "thumbnail": entry.get("thumbnail", ""),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        "source": self.name,
                        "source_name": self.display_name,
                        "format": "m4a/mp3",
                        "quality": "audio",
                    })
        except Exception as e:
            print(f"[YouTube] Search error: {e}")
        return results

    async def get_stream(self, video_id: str) -> dict:
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            **YDL_OPTS_BASE,
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info.get("url", "")
                if not audio_url:
                    formats = info.get("formats", [])
                    audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                    if audio_formats:
                        audio_formats.sort(key=lambda x: x.get("abr", 0) or 0, reverse=True)
                        audio_url = audio_formats[0].get("url", "")
                return {
                    "stream_url": audio_url,
                    "title": info.get("title", ""),
                    "artist": info.get("channel", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "format": "m4a",
                }
        except Exception as e:
            print(f"[YouTube] Stream error: {e}")
            return {}


class BilibiliSource(MusicSourceBase):
    """B站音频/音乐源"""
    name = "bilibili"
    display_name = "Bilibili"

    async def search(self, query: str, limit: int = 20) -> list:
        opts = {
            **YDL_OPTS_BASE,
            "default_search": "bilisearch",
            "extract_flat": True,
        }
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"bilisearch{limit}:{query}", download=False)
                entries = info.get("entries", []) if info else []
                for entry in entries:
                    if not entry:
                        continue
                    bvid = entry.get("id", "")
                    results.append({
                        "id": bvid,
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("channel", entry.get("uploader", "Unknown")),
                        "duration": entry.get("duration", 0),
                        "thumbnail": entry.get("thumbnail", ""),
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "source": self.name,
                        "source_name": self.display_name,
                        "format": "m4a/flac",
                        "quality": "audio",
                    })
        except Exception as e:
            print(f"[Bilibili] Search error: {e}")
        return results

    async def get_stream(self, bvid: str) -> dict:
        url = f"https://www.bilibili.com/video/{bvid}"
        opts = {
            **YDL_OPTS_BASE,
            "format": "bestaudio/best",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info.get("url", "")
                if not audio_url:
                    formats = info.get("formats", [])
                    audio_formats = [f for f in formats if f.get("acodec") != "none"]
                    if audio_formats:
                        audio_formats.sort(key=lambda x: tbr if (tbr := (f.get("tbr", 0) or 0)) else 0, reverse=True)
                        audio_url = audio_formats[0].get("url", "")
                return {
                    "stream_url": audio_url,
                    "title": info.get("title", ""),
                    "artist": info.get("channel", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "format": "m4a",
                }
        except Exception as e:
            print(f"[Bilibili] Stream error: {e}")
            return {}


class NetEaseSource(MusicSourceBase):
    """网易云音乐源 (公开API)"""
    name = "netease"
    display_name = "网易云音乐"

    BASE_URL = "https://music.163.com"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            # 使用网易云搜索API
            search_url = f"https://music.163.com/api/search/get/web"
            params = {
                "s": query,
                "type": 1,  # 单曲
                "offset": 0,
                "limit": limit,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(search_url, data=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        songs = data.get("result", {}).get("songs", [])
                        for song in songs:
                            artists = ", ".join(a.get("name", "") for a in song.get("artists", []))
                            album = song.get("album", {})
                            results.append({
                                "id": str(song.get("id", "")),
                                "title": song.get("name", "Unknown"),
                                "artist": artists or "Unknown",
                                "duration": (song.get("duration", 0) or 0) // 1000,
                                "thumbnail": album.get("picUrl", ""),
                                "album": album.get("name", ""),
                                "url": f"https://music.163.com/song?id={song.get('id', '')}",
                                "source": self.name,
                                "source_name": self.display_name,
                                "format": "mp3/flac",
                                "quality": "标准/无损",
                            })
        except Exception as e:
            print(f"[NetEase] Search error: {e}")
        return results

    async def get_stream(self, song_id: str) -> dict:
        """获取网易云音乐播放链接"""
        try:
            # 使用公开接口获取播放URL
            url = f"https://music.163.com/api/song/enhance/player/url"
            params = {"ids": f"[{song_id}]", "br": 320000}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://music.163.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        song_data = data.get("data", [{}])[0]
                        stream_url = song_data.get("url", "")
                        return {
                            "stream_url": stream_url,
                            "title": "",
                            "artist": "",
                            "duration": song_data.get("time", 0) // 1000 if song_data.get("time") else 0,
                            "format": song_data.get("type", "mp3"),
                            "bitrate": song_data.get("br", 0),
                        }
        except Exception as e:
            print(f"[NetEase] Stream error: {e}")
            return {}


class SoundCloudSource(MusicSourceBase):
    """SoundCloud 源"""
    name = "soundcloud"
    display_name = "SoundCloud"

    async def search(self, query: str, limit: int = 20) -> list:
        opts = {
            **YDL_OPTS_BASE,
            "default_search": "scsearch",
            "extract_flat": True,
        }
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
                entries = info.get("entries", []) if info else []
                for entry in entries:
                    if not entry:
                        continue
                    results.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Unknown"),
                        "artist": entry.get("channel", entry.get("uploader", "Unknown")),
                        "duration": entry.get("duration", 0),
                        "thumbnail": entry.get("thumbnail", ""),
                        "url": entry.get("webpage_url", f"https://soundcloud.com/{entry.get('id', '')}"),
                        "source": self.name,
                        "source_name": self.display_name,
                        "format": "mp3/ogg",
                        "quality": "audio",
                    })
        except Exception as e:
            print(f"[SoundCloud] Search error: {e}")
        return results

    async def get_stream(self, track_id: str) -> dict:
        opts = {
            **YDL_OPTS_BASE,
            "format": "bestaudio/best",
        }
        url = f"https://soundcloud.com/{track_id}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "stream_url": info.get("url", ""),
                    "title": info.get("title", ""),
                    "artist": info.get("uploader", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "format": "mp3",
                }
        except Exception as e:
            print(f"[SoundCloud] Stream error: {e}")
            return {}


class FreeMusicArchiveSource(MusicSourceBase):
    """Free Music Archive 源"""
    name = "fma"
    display_name = "Free Music Archive"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://freemusicarchive.org/api/get/songs.json"
            params = {
                "api_key": "FMA_KEY_NOT_REQUIRED",
                "limit": limit,
                "q": query,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        songs = data.get("dataset", [])
                        for song in songs:
                            results.append({
                                "id": str(song.get("song_id", "")),
                                "title": song.get("song_title", "Unknown"),
                                "artist": song.get("artist_name", "Unknown"),
                                "duration": 0,
                                "thumbnail": song.get("song_image_file", ""),
                                "url": song.get("song_url", ""),
                                "stream_url": song.get("song_url", ""),
                                "source": self.name,
                                "source_name": self.display_name,
                                "format": "mp3",
                                "quality": "free",
                            })
        except Exception as e:
            print(f"[FMA] Search error: {e}")
        return results

    async def get_stream(self, song_id: str) -> dict:
        return {}


# ─── 音乐源管理器 ───────────────────────────────────────

SOURCES = {
    "youtube": YouTubeSource(),
    "bilibili": BilibiliSource(),
    "netease": NetEaseSource(),
    "soundcloud": SoundCloudSource(),
    "fma": FreeMusicArchiveSource(),
}


class SourceManager:
    """音乐源管理器"""

    @staticmethod
    async def search_all(query: str, sources: list = None, limit: int = 20) -> dict:
        """多源并发搜索"""
        if sources is None:
            sources = list(SOURCES.keys())

        tasks = {}
        for src_name in sources:
            if src_name in SOURCES:
                src = SOURCES[src_name]
                tasks[src_name] = asyncio.create_task(src.search(query, limit))

        results = {}
        for src_name, task in tasks.items():
            try:
                src_results = await asyncio.wait_for(task, timeout=20)
                results[src_name] = src_results
            except asyncio.TimeoutError:
                results[src_name] = []
            except Exception as e:
                print(f"[SourceManager] {src_name} error: {e}")
                results[src_name] = []

        return results

    @staticmethod
    async def get_stream(source: str, track_id: str) -> dict:
        """获取播放流"""
        if source in SOURCES:
            return await SOURCES[source].get_stream(track_id)
        return {}


source_manager = SourceManager()

# ─── 推荐列表 ───────────────────────────────────────────

async def get_recommendations() -> dict:
    """获取各平台推荐列表"""
    recommendations = {}

    # 网易云热歌榜
    try:
        netease = NetEaseSource()
        hot = await netease.search("热门歌曲 2024 2025", limit=10)
        recommendations["netease_hot"] = {
            "title": "🔥 网易云热歌榜",
            "source": "netease",
            "items": hot[:10],
        }
    except Exception as e:
        print(f"[Recommend] NetEase error: {e}")
        recommendations["netease_hot"] = {"title": "🔥 网易云热歌榜", "source": "netease", "items": []}

    # YouTube Music 推荐
    try:
        youtube = YouTubeSource()
        yt_pop = await youtube.search("popular music 2025", limit=10)
        recommendations["youtube_popular"] = {
            "title": "🎵 YouTube 热门音乐",
            "source": "youtube",
            "items": yt_pop[:10],
        }
    except Exception as e:
        print(f"[Recommend] YouTube error: {e}")
        recommendations["youtube_popular"] = {"title": "🎵 YouTube 热门音乐", "source": "youtube", "items": []}

    # B站音乐推荐
    try:
        bili = BilibiliSource()
        bili_music = await bili.search("音乐推荐 无损", limit=10)
        recommendations["bilibili_music"] = {
            "title": "🎶 B站音乐精选",
            "source": "bilibili",
            "items": bili_music[:10],
        }
    except Exception as e:
        print(f"[Recommend] Bilibili error: {e}")
        recommendations["bilibili_music"] = {"title": "🎶 B站音乐精选", "source": "bilibili", "items": []}

    # SoundCloud 推荐
    try:
        sc = SoundCloudSource()
        sc_pop = await sc.search("trending music", limit=10)
        recommendations["soundcloud_trending"] = {
            "title": "🎧 SoundCloud 趋势",
            "source": "soundcloud",
            "items": sc_pop[:10],
        }
    except Exception as e:
        print(f"[Recommend] SoundCloud error: {e}")
        recommendations["soundcloud_trending"] = {"title": "🎧 SoundCloud 趋势", "source": "soundcloud", "items": []}

    return recommendations


# ─── API 路由 ───────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "app": "Music Player Docker", "version": "0.1.0-dev"}


@app.get("/api/sources")
async def list_sources():
    """列出所有可用音乐源"""
    return {
        "sources": [
            {"key": k, "name": v.display_name}
            for k, v in SOURCES.items()
        ]
    }


@app.get("/api/search")
async def search_music(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    source: str = Query("all", description="音乐源: all/youtube/bilibili/netease/soundcloud/fma"),
    limit: int = Query(20, ge=1, le=50),
):
    """搜索音乐"""
    if source == "all":
        sources = list(SOURCES.keys())
    else:
        sources = [source]

    results = await source_manager.search_all(q, sources, limit)
    return {"query": q, "results": results}


@app.get("/api/stream")
async def get_stream_url(
    source: str = Query(..., description="音乐源"),
    id: str = Query(..., description="音乐ID或URL"),
):
    """获取音乐播放流地址"""
    stream_info = await source_manager.get_stream(source, id)
    if not stream_info or not stream_info.get("stream_url"):
        raise HTTPException(status_code=404, detail="无法获取播放地址")
    return stream_info


@app.get("/api/recommendations")
async def recommendations():
    """获取推荐列表"""
    recs = await get_recommendations()
    return recs


@app.get("/api/proxy")
async def proxy_stream(url: str = Query(..., description="音频流URL")):
    """代理音频流（解决跨域问题）"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.youtube.com/",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                content_type = resp.headers.get("Content-Type", "audio/mpeg")
                async def stream_generator():
                    async for chunk in resp.content.iter_chunked(8192):
                        yield chunk
                return StreamingResponse(
                    stream_generator(),
                    media_type=content_type,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "no-cache",
                    }
                )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"代理请求失败: {str(e)}")


# ─── 前端页面 ───────────────────────────────────────────

@app.get("/player", response_class=HTMLResponse)
async def player_page():
    """播放器主页面"""
    return get_player_html()


def get_player_html() -> str:
    """返回播放器HTML页面"""
    return PLAYER_HTML


PLAYER_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>🎵 Music Player Docker</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a28;--bg4:#222236;
  --accent:#6c5ce7;--accent2:#a29bfe;--accent3:#74b9ff;
  --text:#e0e0e8;--text2:#9090a8;--text3:#606078;
  --success:#00b894;--warning:#fdcb6e;--danger:#ff6b6b;
  --radius:12px;--radius-sm:8px;--radius-lg:16px;
}
html,body{height:100%;overflow:hidden}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  background:var(--bg);color:var(--text);display:flex;flex-direction:column;
}

/* ── Header ── */
.header{
  background:linear-gradient(135deg,var(--bg2),var(--bg3));
  padding:12px 20px;display:flex;align-items:center;gap:16px;
  border-bottom:1px solid rgba(108,92,231,.15);flex-shrink:0;z-index:10;
}
.logo{font-size:1.3em;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent3));-webkit-background-clip:text;-webkit-text-fill-color:transparent;white-space:nowrap}
.search-box{flex:1;max-width:600px;display:flex;gap:8px;margin:0 auto}
.search-box input{
  flex:1;background:var(--bg3);border:1px solid rgba(108,92,231,.2);
  color:var(--text);padding:10px 16px;border-radius:var(--radius);
  font-size:.95em;outline:none;transition:.2s;
}
.search-box input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(108,92,231,.15)}
.search-box button{
  background:linear-gradient(135deg,var(--accent),#8b5cf6);color:#fff;border:none;
  padding:10px 20px;border-radius:var(--radius);cursor:pointer;font-weight:600;
  transition:.2s;white-space:nowrap;
}
.search-box button:hover{transform:translateY(-1px);box-shadow:0 4px 15px rgba(108,92,231,.3)}
.search-box button:disabled{opacity:.5;cursor:not-allowed;transform:none}

/* ── Source Tabs ── */
.source-tabs{
  display:flex;gap:6px;padding:8px 20px;background:var(--bg2);
  border-bottom:1px solid rgba(108,92,231,.1);overflow-x:auto;flex-shrink:0;
}
.source-tab{
  padding:6px 14px;border-radius:20px;border:1px solid rgba(108,92,231,.2);
  background:transparent;color:var(--text2);cursor:pointer;font-size:.85em;
  transition:.2s;white-space:nowrap;
}
.source-tab:hover{border-color:var(--accent);color:var(--text)}
.source-tab.active{background:linear-gradient(135deg,var(--accent),#8b5cf6);color:#fff;border-color:transparent}

/* ── Main Content ── */
.main{flex:1;display:flex;overflow:hidden}
.content{flex:1;overflow-y:auto;padding:16px 20px}

/* ── Section ── */
.section{margin-bottom:28px}
.section-title{
  font-size:1.1em;font-weight:600;margin-bottom:12px;
  display:flex;align-items:center;gap:8px;
}

/* ── Track Card ── */
.track-list{display:grid;gap:8px}
.track-card{
  display:flex;align-items:center;gap:12px;padding:10px 14px;
  background:var(--bg2);border-radius:var(--radius);cursor:pointer;
  transition:.2s;border:1px solid transparent;
}
.track-card:hover{background:var(--bg3);border-color:rgba(108,92,231,.2);transform:translateX(4px)}
.track-card.playing{border-color:var(--accent);background:rgba(108,92,231,.1)}
.track-thumb{
  width:48px;height:48px;border-radius:var(--radius-sm);object-fit:cover;
  background:var(--bg4);flex-shrink:0;
}
.track-info{flex:1;min-width:0}
.track-title{font-weight:500;font-size:.95em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track-meta{font-size:.8em;color:var(--text2);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track-duration{font-size:.8em;color:var(--text3);flex-shrink:0;margin-left:8px}
.track-source{
  font-size:.7em;padding:2px 8px;border-radius:10px;background:rgba(108,92,231,.15);
  color:var(--accent2);flex-shrink:0;
}

/* ── Recommendation Grid ── */
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.rec-card{
  background:var(--bg2);border-radius:var(--radius-lg);padding:16px;
  border:1px solid rgba(108,92,231,.1);transition:.2s;
}
.rec-card:hover{border-color:rgba(108,92,231,.3);transform:translateY(-2px)}
.rec-card-title{font-weight:600;margin-bottom:10px;font-size:.95em}
.rec-tracks{display:flex;flex-direction:column;gap:6px}
.rec-track{
  display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:var(--radius-sm);
  cursor:pointer;transition:.15s;font-size:.85em;
}
.rec-track:hover{background:var(--bg3)}
.rec-track-num{width:20px;text-align:center;color:var(--text3);font-size:.8em;flex-shrink:0}
.rec-track-info{flex:1;min-width:0}
.rec-track-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rec-track-artist{font-size:.8em;color:var(--text3)}
.rec-track-thumb{width:32px;height:32px;border-radius:4px;object-fit:cover;background:var(--bg4);flex-shrink:0}

/* ── Player Bar ── */
.player-bar{
  background:linear-gradient(180deg,var(--bg2),var(--bg3));
  border-top:1px solid rgba(108,92,231,.2);padding:10px 20px;
  display:flex;align-items:center;gap:16px;flex-shrink:0;z-index:20;
}
.player-track-info{display:flex;align-items:center;gap:10px;flex:1;min-width:0}
.player-thumb{
  width:44px;height:44px;border-radius:var(--radius-sm);object-fit:cover;
  background:var(--bg4);flex-shrink:0;
}
.player-text{flex:1;min-width:0}
.player-title{font-weight:500;font-size:.9em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.player-artist{font-size:.75em;color:var(--text2)}
.player-controls{display:flex;align-items:center;gap:12px}
.ctrl-btn{
  background:none;border:none;color:var(--text);cursor:pointer;
  font-size:1.3em;padding:6px;border-radius:50%;transition:.2s;
}
.ctrl-btn:hover{background:rgba(108,92,231,.15)}
.ctrl-btn.play{font-size:1.6em;color:var(--accent)}
.player-progress{flex:2;max-width:400px}
.progress-bar{
  width:100%;height:4px;background:var(--bg4);border-radius:2px;
  cursor:pointer;position:relative;
}
.progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent3));border-radius:2px;width:0%;transition:.1s}
.progress-bar:hover{height:6px}
.time-display{font-size:.75em;color:var(--text3);display:flex;justify-content:space-between;margin-top:4px}
.player-volume{display:flex;align-items:center;gap:6px}
.player-volume input{width:80px;accent-color:var(--accent)}

/* ── Playlist Sidebar ── */
.playlist-toggle{
  position:fixed;right:0;top:50%;transform:translateY(-50%);
  background:var(--bg3);border:1px solid rgba(108,92,231,.2);
  color:var(--text);padding:10px 6px;border-radius:var(--radius) 0 0 var(--radius);
  cursor:pointer;z-index:30;transition:.2s;font-size:.85em;
}
.playlist-toggle:hover{background:var(--bg4)}
.playlist-sidebar{
  position:fixed;right:-320px;top:0;bottom:0;width:300px;
  background:var(--bg2);border-left:1px solid rgba(108,92,231,.15);
  z-index:25;transition:.3s;display:flex;flex-direction:column;
}
.playlist-sidebar.open{right:0}
.playlist-header{padding:16px;border-bottom:1px solid rgba(108,92,231,.1);display:flex;justify-content:space-between;align-items:center}
.playlist-header h3{font-size:1em}
.playlist-close{background:none;border:none;color:var(--text2);cursor:pointer;font-size:1.2em}
.playlist-items{flex:1;overflow-y:auto;padding:8px}
.playlist-item{
  display:flex;align-items:center;gap:8px;padding:8px;border-radius:var(--radius-sm);
  cursor:pointer;transition:.15s;font-size:.85em;
}
.playlist-item:hover{background:var(--bg3)}
.playlist-item.active{background:rgba(108,92,231,.15)}
.playlist-item-thumb{width:36px;height:36px;border-radius:4px;object-fit:cover;background:var(--bg4);flex-shrink:0}
.playlist-item-info{flex:1;min-width:0}
.playlist-item-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.playlist-item-artist{font-size:.8em;color:var(--text3)}

/* ── Loading & Empty ── */
.loading{display:flex;align-items:center;justify-content:center;padding:40px;color:var(--text2)}
.spinner{width:24px;height:24px;border:2px solid var(--bg4);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-right:10px}
@keyframes spin{to{transform:rotate(360deg)}}
.empty{text-align:center;padding:40px;color:var(--text3)}
.error-msg{color:var(--danger);padding:12px;text-align:center;font-size:.9em}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text3)}

/* ── Responsive ── */
@media(max-width:768px){
  .header{padding:10px 12px;flex-wrap:wrap}
  .logo{font-size:1.1em}
  .search-box{order:3;max-width:100%;width:100%;margin-top:8px}
  .source-tabs{padding:6px 12px}
  .content{padding:12px}
  .rec-grid{grid-template-columns:1fr}
  .player-bar{padding:8px 12px;gap:8px}
  .player-progress{display:none}
  .player-volume{display:none}
  .player-track-info{flex:none;max-width:160px}
  .playlist-sidebar{width:280px}
}
@media(max-width:480px){
  .track-card{padding:8px 10px}
  .track-thumb{width:40px;height:40px}
  .track-source{display:none}
}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="logo">🎵 Music Player</div>
  <div class="search-box">
    <input type="text" id="searchInput" placeholder="搜索歌曲、歌手、专辑..." onkeydown="if(event.key==='Enter')doSearch()">
    <button id="searchBtn" onclick="doSearch()">🔍 搜索</button>
  </div>
</div>

<!-- Source Tabs -->
<div class="source-tabs" id="sourceTabs">
  <div class="source-tab active" data-source="all" onclick="switchSource('all',this)">🌐 全部</div>
  <div class="source-tab" data-source="youtube" onclick="switchSource('youtube',this)">📺 YouTube</div>
  <div class="source-tab" data-source="bilibili" onclick="switchSource('bilibili',this)">📹 Bilibili</div>
  <div class="source-tab" data-source="netease" onclick="switchSource('netease',this)">☁️ 网易云</div>
  <div class="source-tab" data-source="soundcloud" onclick="switchSource('soundcloud',this)">🎧 SoundCloud</div>
  <div class="source-tab" data-source="fma" onclick="switchSource('fma',this)">🎼 FMA</div>
</div>

<!-- Main -->
<div class="main">
  <div class="content" id="content">
    <div class="loading" id="loading"><div class="spinner"></div>正在加载推荐列表...</div>
  </div>
</div>

<!-- Playlist Sidebar -->
<div class="playlist-toggle" id="playlistToggle" onclick="togglePlaylist()">📋</div>
<div class="playlist-sidebar" id="playlistSidebar">
  <div class="playlist-header">
    <h3>📋 播放列表 (<span id="playlistCount">0</span>)</h3>
    <button class="playlist-close" onclick="togglePlaylist()">✕</button>
  </div>
  <div class="playlist-items" id="playlistItems">
    <div class="empty">播放列表为空</div>
  </div>
</div>

<!-- Player Bar -->
<div class="player-bar" id="playerBar" style="display:none">
  <div class="player-track-info">
    <img class="player-thumb" id="playerThumb" src="" alt="">
    <div class="player-text">
      <div class="player-title" id="playerTitle">未播放</div>
      <div class="player-artist" id="playerArtist">-</div>
    </div>
  </div>
  <div class="player-controls">
    <button class="ctrl-btn" onclick="prevTrack()">⏮</button>
    <button class="ctrl-btn play" id="playBtn" onclick="togglePlay()">▶</button>
    <button class="ctrl-btn" onclick="nextTrack()">⏭</button>
  </div>
  <div class="player-progress">
    <div class="progress-bar" id="progressBar" onclick="seek(event)">
      <div class="progress-fill" id="progressFill"></div>
    </div>
    <div class="time-display">
      <span id="currentTime">0:00</span>
      <span id="totalTime">0:00</span>
    </div>
  </div>
  <div class="player-volume">
    <span>🔊</span>
    <input type="range" id="volumeSlider" min="0" max="100" value="80" oninput="setVolume(this.value)">
  </div>
</div>

<script>
// ── State ──
let currentSource='all';
let playlist=[];
let currentTrackIndex=-1;
let isPlaying=false;
let audio=null;
let recommendations={};

// ── Init ──
document.addEventListener('DOMContentLoaded',()=>{
  loadRecommendations();
  audio=new Audio();
  audio.preload='auto';
  audio.volume=0.8;
  audio.addEventListener('timeupdate',updateProgress);
  audio.addEventListener('ended',nextTrack);
  audio.addEventListener('error',(e)=>{
    console.error('Audio error:',e);
    showError('播放失败，请尝试其他音源');
  });
  audio.addEventListener('loadeddata',()=>{
    document.getElementById('playBtn').textContent='⏸';
    isPlaying=true;
  });
});

// ── Search ──
async function doSearch(){
  const q=document.getElementById('searchInput').value.trim();
  if(!q)return;
  const btn=document.getElementById('searchBtn');
  btn.disabled=true;btn.textContent='搜索中...';
  const content=document.getElementById('content');
  content.innerHTML='<div class="loading"><div class="spinner"></div>正在搜索 '+q+' ...</div>';
  try{
    const res=await fetch(`/api/search?q=${encodeURIComponent(q)}&source=${currentSource}&limit=20`);
    const data=await res.json();
    renderSearchResults(data);
  }catch(e){
    content.innerHTML='<div class="error-msg">搜索失败: '+e.message+'</div>';
  }
  btn.disabled=false;btn.textContent='🔍 搜索';
}

function switchSource(source,el){
  currentSource=source;
  document.querySelectorAll('.source-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

function renderSearchResults(data){
  const content=document.getElementById('content');
  let html='';
  const results=data.results||{};
  let totalCount=0;
  for(const[src,items] of Object.entries(results)){
    if(!items||items.length===0)continue;
    totalCount+=items.length;
    html+=`<div class="section"><div class="section-title">📀 ${items[0]?.source_name||src} (${items.length})</div>`;
    html+='<div class="track-list">';
    items.forEach((track,i)=>{
      html+=renderTrackCard(track,src);
    });
    html+='</div></div>';
  }
  if(totalCount===0){
    content.innerHTML='<div class="empty">😔 未找到相关结果，请尝试其他关键词或音源</div>';
  }else{
    content.innerHTML=html;
  }
}

function renderTrackCard(track,source){
  const dur=formatDuration(track.duration);
  const thumb=track.thumbnail||'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect fill="%23222236" width="48" height="48" rx="8"/><text x="24" y="30" text-anchor="middle" fill="%236c5ce7" font-size="20">🎵</text></svg>';
  return `<div class="track-card" onclick="playTrack('${source}','${track.id}','${escAttr(track.title)}','${escAttr(track.artist)}','${track.thumbnail||''}','${track.url||''}',${track.duration||0})">
    <img class="track-thumb" src="${thumb}" alt="" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 48 48%22><rect fill=%22%23222236%22 width=%2248%22 height=%2248%22 rx=%228%22/><text x=%2224%22 y=%2230%22 text-anchor=%22middle%22 fill=%22%236c5ce7%22 font-size=%2220%22>🎵</text></svg>'">
    <div class="track-info">
      <div class="track-title">${escHtml(track.title)}</div>
      <div class="track-meta">${escHtml(track.artist)}${track.album?' · '+escHtml(track.album):''}</div>
    </div>
    <span class="track-source">${track.format||'audio'}</span>
    <span class="track-duration">${dur}</span>
  </div>`;
}

// ── Recommendations ──
async function loadRecommendations(){
  try{
    const res=await fetch('/api/recommendations');
    recommendations=await res.json();
    renderRecommendations();
  }catch(e){
    document.getElementById('content').innerHTML='<div class="error-msg">加载推荐失败: '+e.message+'</div>';
  }
}

function renderRecommendations(){
  const content=document.getElementById('content');
  let html='';
  for(const[key,rec] of Object.entries(recommendations)){
    if(!rec.items||rec.items.length===0)continue;
    html+=`<div class="rec-card">
      <div class="rec-card-title">${rec.title}</div>
      <div class="rec-tracks">`;
    rec.items.forEach((track,i)=>{
      const thumb=track.thumbnail||'';
      html+=`<div class="rec-track" onclick="playTrack('${rec.source}','${track.id}','${escAttr(track.title)}','${escAttr(track.artist)}','${thumb}','${track.url||''}',${track.duration||0})">
        <span class="rec-track-num">${i+1}</span>
        ${thumb?`<img class="rec-track-thumb" src="${thumb}" alt="" loading="lazy">`:'<div class="rec-track-thumb"></div>'}
        <div class="rec-track-info">
          <div class="rec-track-title">${escHtml(track.title)}</div>
          <div class="rec-track-artist">${escHtml(track.artist)}</div>
        </div>
      </div>`;
    });
    html+='</div></div>';
  }
  content.innerHTML=`<div class="rec-grid">${html}</div>`;
}

// ── Playback ──
async function playTrack(source,id,title,artist,thumb,url,duration){
  const playerBar=document.getElementById('playerBar');
  playerBar.style.display='flex';
  document.getElementById('playerTitle').textContent=title;
  document.getElementById('playerArtist').textContent=artist;
  document.getElementById('playerThumb').src=thumb||'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 44 44"><rect fill="%23222236" width="44" height="44" rx="8"/><text x="22" y="28" text-anchor="middle" fill="%236c5ce7" font-size="18">🎵</text></svg>';
  document.getElementById('playBtn').textContent='⏳';
  isPlaying=false;

  // Add to playlist
  const track={source,id,title,artist,thumb,url,duration};
  const existingIdx=playlist.findIndex(t=>t.id===id&&t.source===source);
  if(existingIdx>=0){
    currentTrackIndex=existingIdx;
  }else{
    playlist.push(track);
    currentTrackIndex=playlist.length-1;
    updatePlaylistUI();
  }

  // Get stream URL
  try{
    const res=await fetch(`/api/stream?source=${source}&id=${encodeURIComponent(id)}`);
    if(!res.ok)throw new Error('无法获取播放地址');
    const data=await res.json();
    let streamUrl=data.stream_url;
    if(!streamUrl)throw new Error('播放地址为空');

    // Use proxy for cross-origin
    if(streamUrl.startsWith('http')){
      streamUrl=`/api/proxy?url=${encodeURIComponent(streamUrl)}`;
    }

    audio.src=streamUrl;
    audio.play().catch(e=>{
      console.error('Play error:',e);
      showError('播放失败: '+e.message);
      document.getElementById('playBtn').textContent='▶';
    });
  }catch(e){
    console.error('Stream error:',e);
    showError('获取播放地址失败: '+e.message+'，请尝试其他音源');
    document.getElementById('playBtn').textContent='▶';
  }
}

function togglePlay(){
  if(!audio.src)return;
  if(audio.paused){
    audio.play();
    document.getElementById('playBtn').textContent='⏸';
    isPlaying=true;
  }else{
    audio.pause();
    document.getElementById('playBtn').textContent='▶';
    isPlaying=false;
  }
}

function prevTrack(){
  if(currentTrackIndex>0){
    currentTrackIndex--;
    playCurrent();
  }
}

function nextTrack(){
  if(currentTrackIndex<playlist.length-1){
    currentTrackIndex++;
    playCurrent();
  }
}

function playCurrent(){
  if(currentTrackIndex<0||currentTrackIndex>=playlist.length)return;
  const t=playlist[currentTrackIndex];
  playTrack(t.source,t.id,t.title,t.artist,t.thumb,t.url,t.duration);
}

function seek(e){
  if(!audio.duration)return;
  const bar=e.currentTarget;
  const rect=bar.getBoundingClientRect();
  const pct=(e.clientX-rect.left)/rect.width;
  audio.currentTime=pct*audio.duration;
}

function updateProgress(){
  if(!audio.duration)return;
  const pct=(audio.currentTime/audio.duration)*100;
  document.getElementById('progressFill').style.width=pct+'%';
  document.getElementById('currentTime').textContent=formatDuration(audio.currentTime);
  document.getElementById('totalTime').textContent=formatDuration(audio.duration);
}

function setVolume(val){
  audio.volume=val/100;
}

// ── Playlist ──
function togglePlaylist(){
  document.getElementById('playlistSidebar').classList.toggle('open');
}

function updatePlaylistUI(){
  const container=document.getElementById('playlistItems');
  document.getElementById('playlistCount').textContent=playlist.length;
  if(playlist.length===0){
    container.innerHTML='<div class="empty">播放列表为空</div>';
    return;
  }
  let html='';
  playlist.forEach((t,i)=>{
    const active=i===currentTrackIndex?' active':'';
    html+=`<div class="playlist-item${active}" onclick="playByIndex(${i})">
      <div class="playlist-item-thumb" style="background:url(${t.thumbnail||''}) center/cover,var(--bg4);border-radius:4px;width:36px;height:36px;flex-shrink:0"></div>
      <div class="playlist-item-info">
        <div class="playlist-item-title">${escHtml(t.title)}</div>
        <div class="playlist-item-artist">${escHtml(t.artist)}</div>
      </div>
    </div>`;
  });
  container.innerHTML=html;
}

function playByIndex(i){
  currentTrackIndex=i;
  playCurrent();
  updatePlaylistUI();
}

// ── Helpers ──
function formatDuration(sec){
  if(!sec||sec<=0)return'-:--';
  sec=Math.floor(sec);
  const m=Math.floor(sec/60);
  const s=sec%60;
  return m+':'+(s<10?'0':'')+s;
}

function escHtml(s){
  if(!s)return'';
  const d=document.createElement('div');
  d.textContent=s;
  return d.innerHTML;
}

function escAttr(s){
  if(!s)return'';
  return s.replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/[\r\n]/g,' ');
}

function showError(msg){
  const content=document.getElementById('content');
  const existing=content.querySelector('.error-msg');
  if(existing)existing.remove();
  const div=document.createElement('div');
  div.className='error-msg';
  div.style.cssText='position:fixed;top:70px;left:50%;transform:translateX(-50%);background:rgba(255,107,107,.15);color:#ff6b6b;padding:10px 20px;border-radius:8px;z-index:100;font-size:.9em;animation:fadeIn .3s';
  div.textContent=msg;
  document.body.appendChild(div);
  setTimeout(()=>div.remove(),4000);
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
