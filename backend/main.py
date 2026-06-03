"""
Music Player Docker - Main Application
开发版本: v0.2.0-spa
完整SPA前端 + FastAPI后端
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

# ─── 网盘音乐模块 ───────────────────────────────────────
import hashlib as _hashlib

class NetDiskBase:
    """网盘基类"""
    name = "base"
    display_name = "Base"
    AUDIO_EXT = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.ape', '.wma'}

    async def search_music(self, keyword: str, limit: int = 20) -> list:
        raise NotImplementedError

    async def get_download_url(self, file_id: str) -> str:
        raise NotImplementedError


class BaiduPanSource(NetDiskBase):
    """百度网盘"""
    name = "baidupan"
    display_name = "百度网盘"

    def __init__(self, access_token: str = "", cookie: str = ""):
        self.access_token = access_token
        self.cookie = cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if cookie:
            self.headers["Cookie"] = cookie

    async def search_music(self, keyword: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://pan.baidu.com/rest/2.0/xpan/file"
            params = {
                "method": "search",
                "key": keyword,
                "dir": "/",
                "page": "1",
                "num": str(limit * 3),
                "recursion": "1",
                "access_token": self.access_token,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text(encoding="utf-8")
                    data = json.loads(text)
                    if data.get("errno") == 0:
                        for item in data.get("list", []):
                            name = item.get("server_filename", "")
                            ext = __import__("os").path.splitext(name)[1].lower()
                            if ext in self.AUDIO_EXT:
                                results.append({
                                    "id": str(item.get("fs_id", "")),
                                    "title": __import__("os").path.splitext(name)[0],
                                    "artist": "", "duration": 0, "thumbnail": "",
                                    "size": item.get("size", 0),
                                    "source": self.name, "source_name": self.display_name,
                                    "format": ext.lstrip("."), "quality": "原始",
                                })
                                if len(results) >= limit:
                                    break
                    else:
                        print(f"[BaiduPan] search errno={data.get('errno')}")
        except Exception as e:
            print(f"[BaiduPan] search error: {e}")
        return results

    async def get_download_url(self, file_id: str) -> str:
        try:
            url = "https://pan.baidu.com/rest/2.0/xpan/multimedia"
            params = {
                "method": "filemetas",
                "fsids": json.dumps([int(file_id)]),
                "dlink": "1",
                "access_token": self.access_token,
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = json.loads(await resp.text(encoding="utf-8"))
                    if data.get("errno") == 0:
                        items = data.get("info", [])
                        if items:
                            return items[0].get("dlink", "")
        except Exception as e:
            print(f"[BaiduPan] download error: {e}")
        return ""


class AliYunDriveSource(NetDiskBase):
    """阿里云盘"""
    name = "aliyun"
    display_name = "阿里云盘"

    def __init__(self, access_token: str = "", refresh_token: str = "", cookie: str = ""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.cookie = cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"
        if cookie:
            self.headers["Cookie"] = cookie

    async def search_music(self, keyword: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://api.aliyundrive.com/adrive/v3/file/list"
            payload = {
                "drive_id": "default",
                "limit": limit * 3,
                "order_by": "name ASC",
                "query": f'name match "{keyword}"',
                "type": "file",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json(content_type=None)
                    for item in data.get("items", []):
                        name = item.get("name", "")
                        ext = __import__("os").path.splitext(name)[1].lower()
                        if ext in self.AUDIO_EXT:
                            results.append({
                                "id": item.get("file_id", ""),
                                "title": __import__("os").path.splitext(name)[0],
                                "artist": "", "duration": 0, "thumbnail": "",
                                "size": item.get("size", 0),
                                "source": self.name, "source_name": self.display_name,
                                "format": ext.lstrip("."), "quality": "原始",
                            })
                            if len(results) >= limit:
                                break
        except Exception as e:
            print(f"[AliYun] search error: {e}")
        return results

    async def get_download_url(self, file_id: str) -> str:
        try:
            url = "https://api.aliyundrive.com/v2/file/get_download_url"
            payload = {"drive_id": "default", "file_id": file_id}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json(content_type=None)
                    return data.get("url", "")
        except Exception as e:
            print(f"[AliYun] download error: {e}")
        return ""


class QuarkPanSource(NetDiskBase):
    """夸克网盘"""
    name = "quark"
    display_name = "夸克网盘"

    def __init__(self, cookie: str = ""):
        self.cookie = cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }
        if cookie:
            self.headers["Cookie"] = cookie

    async def search_music(self, keyword: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://drive.quark.cn/1/clouddrive/file/search"
            payload = {"key": keyword, "pdir_fid": "0"}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json(content_type=None)
                    if data.get("code") == 0:
                        for item in data.get("data", {}).get("list", []):
                            name = item.get("file_name", "")
                            ext = __import__("os").path.splitext(name)[1].lower()
                            if ext in self.AUDIO_EXT:
                                results.append({
                                    "id": item.get("fid", ""),
                                    "title": __import__("os").path.splitext(name)[0],
                                    "artist": "", "duration": 0, "thumbnail": "",
                                    "size": item.get("size", 0),
                                    "source": self.name, "source_name": self.display_name,
                                    "format": ext.lstrip("."), "quality": "原始",
                                })
                                if len(results) >= limit:
                                    break
                    else:
                        print(f"[Quark] search code={data.get('code')}")
        except Exception as e:
            print(f"[Quark] search error: {e}")
        return results

    async def get_download_url(self, file_id: str) -> str:
        try:
            url = "https://drive.quark.cn/1/clouddrive/file/download"
            payload = {"fid": file_id, "pdir_fid": "0"}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json(content_type=None)
                    if data.get("code") == 0:
                        return data.get("data", {}).get("download_url", "")
        except Exception as e:
            print(f"[Quark] download error: {e}")
        return ""


# 网盘管理器实例（延迟初始化）
_netdisk_manager = None

def get_netdisk_manager():
    global _netdisk_manager
    if _netdisk_manager is None:
        _netdisk_manager = _init_netdisk_manager()
    return _netdisk_manager

def _init_netdisk_manager():
    """从环境变量/配置文件初始化网盘"""
    sources = {}
    
    # 百度网盘
    bd_token = os.getenv("BAIDUPAN_ACCESS_TOKEN", "")
    bd_cookie = os.getenv("BAIDUPAN_COOKIE", "")
    if bd_token or bd_cookie:
        sources["baidupan"] = BaiduPanSource(access_token=bd_token, cookie=bd_cookie)
    
    # 阿里云盘
    ali_token = os.getenv("ALIYUN_ACCESS_TOKEN", "")
    ali_refresh = os.getenv("ALIYUN_REFRESH_TOKEN", "")
    ali_cookie = os.getenv("ALIYUN_COOKIE", "")
    if ali_token or ali_refresh or ali_cookie:
        sources["aliyun"] = AliYunDriveSource(access_token=ali_token, refresh_token=ali_refresh, cookie=ali_cookie)
    
    # 夸克
    quark_cookie = os.getenv("QUARK_COOKIE", "")
    if quark_cookie:
        sources["quark"] = QuarkPanSource(cookie=quark_cookie)
    
    return sources


app = FastAPI(
    title="Music Player Docker",
    description="在线音乐播放器 - 支持多源搜索、无损格式、SPA界面",
    version="0.3.1"
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
    name: str = "base"
    display_name: str = "Base"

    async def search(self, query: str, limit: int = 20) -> list:
        raise NotImplementedError

    async def get_stream(self, url_or_id: str) -> dict:
        raise NotImplementedError

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class NetEaseSource(MusicSourceBase):
    """网易云音乐 - 使用 tonzhon 搜索API + GDStudio 播放URL"""
    name = "netease"
    display_name = "网易云音乐"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            # 使用 tonzhon 的搜索API（稳定可用）
            url = "https://tonzhon.com/api.php"
            payload = f"types=search&name={query}&source=netease"
            headers = {
                **COMMON_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://tonzhon.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        data = json.loads(text)
                        if isinstance(data, list):
                            for song in data[:limit]:
                                # artist 可能是嵌套列表
                                artist_raw = song.get("artist", "")
                                if isinstance(artist_raw, list):
                                    # 展平嵌套列表
                                    artists = []
                                    for a in artist_raw:
                                        if isinstance(a, list):
                                            artists.extend(a)
                                        else:
                                            artists.append(a)
                                    artist_str = ", ".join(str(x) for x in artists if x)
                                else:
                                    artist_str = str(artist_raw)
                                
                                results.append({
                                    "id": str(song.get("id", "")),
                                    "title": song.get("name", "Unknown"),
                                    "artist": artist_str or "Unknown",
                                    "duration": song.get("duration", 0),
                                    "thumbnail": f"https://p1.music.126.net/{song.get('pic_id', '')}.jpg" if song.get('pic_id') else "",
                                    "album": song.get("album", ""),
                                    "source": self.name,
                                    "source_name": self.display_name,
                                    "format": "mp3/flac",
                                    "quality": "标准/无损",
                                })
        except Exception as e:
            print(f"[NetEase] Search error: {e}")
        return results

    async def get_stream(self, song_id: str) -> dict:
        try:
            # 使用 GDStudio API 获取播放URL（稳定可用）
            url = f"https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id={song_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        data = json.loads(text)
                        stream_url = data.get("url", "")
                        if stream_url:
                            return {
                                "stream_url": stream_url,
                                "title": "",
                                "artist": "",
                                "duration": 0,
                                "format": data.get("type", "flac") or "mp3",
                                "bitrate": data.get("br", 0),
                            }
        except Exception as e:
            print(f"[NetEase] Stream error: {e}")
        return {}


class QQMusicSource(MusicSourceBase):
    """QQ音乐 - 使用shc搜索API"""
    name = "qq"
    display_name = "QQ音乐"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://shc.y.qq.com/soso/fcgi-bin/search_for_qq_cp"
            params = {
                "format": "json",
                "p": "1",
                "n": str(limit),
                "w": query,
                "cr": "1",
            }
            headers = {**COMMON_HEADERS, "Referer": "https://y.qq.com/"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        if not text or not text.strip():
                            return results
                        data = json.loads(text)
                        songs = data.get("data", {}).get("song", {}).get("list", [])
                        for song in songs:
                            singers = song.get("singer", [])
                            if isinstance(singers, list):
                                artists = ", ".join(s.get("name", "") for s in singers)
                            else:
                                artists = str(singers)
                            mid = song.get("songmid", "")
                            results.append({
                                "id": mid,
                                "title": song.get("songname", "Unknown"),
                                "artist": artists or "Unknown",
                                "duration": song.get("interval", 0),
                                "thumbnail": f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{song.get('albummid','')}.jpg",
                                "album": song.get("albumname", ""),
                                "url": f"https://y.qq.com/n/ryqq/songDetail/{mid}",
                                "source": self.name,
                                "source_name": self.display_name,
                                "format": "m4a/flac",
                                "quality": "标准/无损",
                            })
        except Exception as e:
            print(f"[QQ] Search error: {e}")
        return results

    async def get_stream(self, song_mid: str) -> dict:
        try:
            # 获取vkey播放URL - 使用简化API
            guid = "1234567890"
            url = "https://u.y.qq.com/cgi-bin/musicu.fcg"
            data_payload = {
                "req_0": {
                    "module": "vkey.GetVkeyServer",
                    "method": "CgiGetVkey",
                    "param": {
                        "guid": guid,
                        "songmid": [song_mid],
                        "songtype": [0],
                        "uin": "0",
                        "loginflag": 1,
                        "platform": "20",
                    },
                },
                "comm": {"uin": 0, "format": "json", "ct": 24, "cv": 0},
            }
            params = {
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "notice": "0",
                "platform": "yqq.json",
                "needNewCode": "0",
                "data": json.dumps(data_payload),
            }
            headers = {**COMMON_HEADERS, "Referer": "https://y.qq.com/"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json(encoding="utf-8", content_type=None)
                        info = data.get("req_0", {}).get("data", {}).get("midurlinfo", [{}])[0]
                        purl = info.get("purl", "")
                        if purl:
                            sip_list = data.get("req_0", {}).get("data", {}).get("sip", [])
                            base_url = sip_list[0] if sip_list else "http://ws.stream.qqmusic.qq.com/"
                            if not base_url.endswith("/"):
                                base_url += "/"
                            stream_url = f"{base_url}{purl}"
                            return {
                                "stream_url": stream_url,
                                "title": "",
                                "artist": "",
                                "format": "m4a",
                            }
        except Exception as e:
            print(f"[QQ] Stream error: {e}")
        return {}


class BilibiliSource(MusicSourceBase):
    """B站 - 使用wbi搜索API"""
    name = "bilibili"
    display_name = "Bilibili"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
            params = {
                "search_type": "video",
                "keyword": query,
                "page": "1",
                "page_size": str(limit),
                "order": "totalrank",
            }
            headers = {
                **COMMON_HEADERS,
                "Referer": "https://search.bilibili.com/all",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json(encoding="utf-8", content_type=None)
                        if data.get("code") == 0:
                            items = data.get("data", {}).get("result", [])
                            for item in items:
                                raw_title = item.get("title", "Unknown")
                                import re as _re
                                title = _re.sub(r'<[^>]+>', '', raw_title)
                                author = item.get("author", "Unknown")
                                duration_str = item.get("duration", "0")
                                dur_parts = duration_str.split(":")
                                dur_sec = int(dur_parts[0]) * 60 + int(dur_parts[1]) if len(dur_parts) == 2 else 0
                                bvid = item.get("bvid", "")
                                results.append({
                                    "id": bvid,
                                    "title": title,
                                    "artist": author,
                                    "duration": dur_sec,
                                    "thumbnail": f"https:{item.get('pic', '')}" if item.get('pic', '').startswith('//') else item.get('pic', ''),
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
        opts = {**YDL_OPTS_BASE, "format": "bestaudio/best"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info.get("url", "")
                if not audio_url:
                    formats = info.get("formats", [])
                    audio_formats = [f for f in formats if f.get("acodec") != "none"]
                    if audio_formats:
                        audio_formats.sort(key=lambda x: (x.get("tbr", 0) or 0), reverse=True)
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


class YouTubeSource(MusicSourceBase):
    name = "youtube"
    display_name = "YouTube"

    async def search(self, query: str, limit: int = 20) -> list:
        # YouTube 在国内不可用，快速返回空结果
        return []
        # 以下代码保留供代理环境使用
        opts = {**YDL_OPTS_BASE, "default_search": "ytsearch", "extract_flat": True}
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
        # YouTube 在国内不可用
        return {}
        # 以下代码保留供代理环境使用
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {**YDL_OPTS_BASE, "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"}
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


class CoolMicSource(MusicSourceBase):
    """酷狗音乐 - 使用移动端API"""
    name = "kugou"
    display_name = "酷狗音乐"

    async def search(self, query: str, limit: int = 20) -> list:
        results = []
        try:
            url = "https://mobilecdn.kugou.com/api/v3/search/song"
            params = {
                "format": "json",
                "keyword": query,
                "page": "1",
                "pagesize": str(limit),
                "showtype": "1",
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Referer": "https://www.kugou.com/",
            }
            # 酷狗移动端API有SSL证书问题，需要禁用验证
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10), ssl=ctx) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        if not text or not text.strip():
                            return results
                        data = json.loads(text)
                        info = data.get("data", {}).get("info", [])
                        for item in info:
                            results.append({
                                "id": str(item.get("hash", "")),
                                "title": item.get("songname", "Unknown"),
                                "artist": item.get("singername", "Unknown"),
                                "duration": int(item.get("duration", 0)),
                                "thumbnail": "",
                                "album": item.get("album_name", ""),
                                "source": self.name,
                                "source_name": self.display_name,
                                "format": "mp3/flac",
                                "quality": "标准/无损",
                            })
        except Exception as e:
            print(f"[Kugou] Search error: {e}")
        return results

    async def get_stream(self, file_hash: str) -> dict:
        try:
            url = "https://wwwapi.kugou.com/yy/index.php"
            params = {"r": "play/getdata", "hash": file_hash}
            headers = {**COMMON_HEADERS, "Referer": "https://www.kugou.com/"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        data = json.loads(text)
                        song_data = data.get("data", {})
                        play_url = song_data.get("play_url", "")
                        if play_url:
                            return {
                                "stream_url": play_url,
                                "title": song_data.get("song_name", ""),
                                "artist": song_data.get("author_name", ""),
                                "duration": (song_data.get("timelength", 0) or 0) // 1000,
                                "format": "mp3",
                            }
        except Exception as e:
            print(f"[Kugou] Stream error: {e}")
        return {}


# ─── 音乐源管理器 ───────────────────────────────────────
SOURCES = {
    "netease": NetEaseSource(),
    "qq": QQMusicSource(),
    "bilibili": BilibiliSource(),
    "kugou": CoolMicSource(),
    "youtube": YouTubeSource(),
}

# 网盘音源（动态添加）
def get_netdisk_sources():
    mgr = get_netdisk_manager()
    return {name: src for name, src in mgr.items()}


class SourceManager:
    @staticmethod
    async def search_all(query: str, sources: list = None, limit: int = 20, per_source_timeout: float = 8) -> dict:
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
                src_results = await asyncio.wait_for(task, timeout=per_source_timeout)
                results[src_name] = src_results
            except asyncio.TimeoutError:
                print(f"[SourceManager] {src_name} timeout after {per_source_timeout}s")
                results[src_name] = []
            except Exception as e:
                print(f"[SourceManager] {src_name} error: {e}")
                results[src_name] = []
        return results

    @staticmethod
    async def get_stream(source: str, track_id: str) -> dict:
        if source in SOURCES:
            return await SOURCES[source].get_stream(track_id)
        return {}


source_manager = SourceManager()

# ─── 推荐列表 ───────────────────────────────────────────
async def _fetch_rec(src_cls, query, limit, key, title, source_key):
    """单个推荐源，带8秒超时"""
    try:
        src = src_cls()
        items = await asyncio.wait_for(src.search(query, limit), timeout=8)
        return key, {"title": title, "source": source_key, "items": items[:limit]}
    except Exception as e:
        print(f"[Rec] {key} error: {e}")
        return key, {"title": title, "source": source_key, "items": []}

async def get_recommendations() -> dict:
    tasks = [
        _fetch_rec(NetEaseSource, "热门歌曲 2024 2025", 10, "netease_hot", "🔥 网易云热歌榜", "netease"),
        _fetch_rec(QQMusicSource, "热门歌曲 2025", 10, "qq_hot", "💚 QQ音乐热歌榜", "qq"),
        _fetch_rec(CoolMicSource, "热门歌曲 2025", 10, "kugou_hot", "🎵 酷狗音乐榜", "kugou"),
        _fetch_rec(BilibiliSource, "音乐推荐 无损", 10, "bilibili_music", "🎶 B站音乐精选", "bilibili"),
    ]
    results = await asyncio.gather(*tasks)
    return dict(results)

# ─── API 路由 ───────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "app": "Music Player Docker", "version": "0.3.1"}


@app.get("/api/sources")
async def list_sources():
    sources = [{"key": k, "name": v.display_name} for k, v in SOURCES.items()]
    # 添加已配置的网盘
    netdisk = get_netdisk_manager()
    for name, src in netdisk.items():
        sources.append({"key": src.name, "name": src.display_name})
    return {"sources": sources}


@app.get("/api/search")
async def search_music(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    source: str = Query("all", description="音乐源"),
    limit: int = Query(20, ge=1, le=50),
):
    """全局搜索：自动搜索所有可用源，合并去重"""
    all_results = {}
    
    # 在线音乐源
    if source == "all":
        sources = list(SOURCES.keys())
    else:
        sources = [source]
    
    online_results = await source_manager.search_all(q, sources, limit)
    all_results.update(online_results)
    
    # 网盘源
    netdisk = get_netdisk_manager()
    if netdisk:
        try:
            nd_results = await asyncio.wait_for(
                _search_netdisk(netdisk, q, limit),
                timeout=15
            )
            all_results.update(nd_results)
        except Exception as e:
            print(f"[Search] netdisk error: {e}")
    
    # 合并所有结果为一个列表（前端不显示来源）
    merged = []
    seen = set()
    for src, items in all_results.items():
        if not items:
            continue
        for t in items:
            # 用 title+artist 去重
            key = (t.get("title", "") + t.get("artist", "")).lower().replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            t["_source"] = src  # 内部标记来源，前端不用
            merged.append(t)
    
    return {"query": q, "results": {"all": merged}}

async def _search_netdisk(netdisk: dict, keyword: str, limit: int) -> dict:
    """搜索所有已配置网盘"""
    tasks = {}
    for name, src in netdisk.items():
        tasks[name] = asyncio.create_task(src.search_music(keyword, limit))
    results = {}
    for name, task in tasks.items():
        try:
            items = await asyncio.wait_for(task, timeout=12)
            results[name] = items
        except Exception as e:
            print(f"[NetDisk] {name} error: {e}")
            results[name] = []
    return results


@app.get("/api/stream")
async def get_stream_url(
    source: str = Query(..., description="音乐源"),
    id: str = Query(..., description="音乐ID或URL"),
):
    """全局播放：自动从对应源获取播放链接"""
    # 网盘播放
    netdisk = get_netdisk_manager()
    if source in netdisk:
        url = await netdisk[source].get_download_url(id)
        if url:
            return {"stream_url": url, "title": "", "artist": "", "format": "audio"}
        raise HTTPException(status_code=404, detail="无法获取网盘下载链接")
    
    # 在线音乐播放
    stream_info = await source_manager.get_stream(source, id)
    if not stream_info or not stream_info.get("stream_url"):
        # 如果直接获取失败，尝试用 GDStudio API（仅网易云）
        if source == "netease":
            try:
                gds_url = f"https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id={id}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(gds_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            text = await resp.text(encoding="utf-8")
                            gds_data = json.loads(text)
                            gds_stream = gds_data.get("url", "")
                            if gds_stream:
                                return {
                                    "stream_url": gds_stream,
                                    "title": "",
                                    "artist": "",
                                    "duration": 0,
                                    "format": gds_data.get("type", "flac") or "mp3",
                                    "bitrate": gds_data.get("br", 0),
                                }
            except Exception as e:
                print(f"[Stream] GDStudio fallback error: {e}")
        
        raise HTTPException(status_code=404, detail="无法获取播放地址，可能需要配置代理")
    
    return stream_info


@app.get("/api/recommendations")
async def recommendations():
    recs = await get_recommendations()
    return recs


@app.get("/api/proxy")
async def proxy_stream(url: str = Query(..., description="音频流URL")):
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
                    headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}
                )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"代理请求失败: {str(e)}")


# ─── SPA 前端 ───────────────────────────────────────────
@app.get("/player", response_class=HTMLResponse)
async def player_page():
    return SPA_HTML

SPA_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0a0a0f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>🎵 Music Player Docker</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎵</text></svg>">
<style>
:root{
  --bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a28;--bg4:#222236;--bg5:#2a2a3e;
  --accent:#6c5ce7;--accent-g:linear-gradient(135deg,#6c5ce7,#8b5cf6);
  --accent2:#a29bfe;--accent3:#74b9ff;
  --text:#e0e0e8;--text2:#9090a8;--text3:#606078;
  --success:#00b894;--warning:#fdcb6e;--danger:#ff6b6b;
  --radius:12px;--r-sm:8px;--r-lg:16px;--r-xl:20px;
  --shadow:0 4px 24px rgba(0,0,0,.4);--shadow-sm:0 2px 8px rgba(0,0,0,.3);
  --trans:.25s cubic-bezier(.4,0,.2,1);
}
*{margin:0;padding:0;box-sizing:border-box;outline:none}
html,body{height:100%;overflow:hidden;background:var(--bg);color:var(--text)}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;-webkit-font-smoothing:antialiased}
::selection{background:rgba(108,92,231,.3)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg5);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text3)}
a{color:var(--accent2);text-decoration:none}
button{cursor:pointer;border:none;background:none;color:inherit;font:inherit}
input{font:inherit}
img{-webkit-user-drag:none}

/* ═══ APP LAYOUT ═══ */
#app{display:flex;flex-direction:column;height:100vh;overflow:hidden}

/* ═══ TOP NAV ═══ */
.topnav{
  display:flex;align-items:center;gap:12px;padding:10px 20px;
  background:var(--bg2);border-bottom:1px solid rgba(108,92,231,.12);
  flex-shrink:0;z-index:50;height:56px;
}
.logo{font-size:1.25em;font-weight:800;background:var(--accent-g);-webkit-background-clip:text;-webkit-text-fill-color:transparent;white-space:nowrap;letter-spacing:-.5px}
.nav-links{display:flex;gap:4px;margin:0 auto}
.nav-link{
  padding:6px 14px;border-radius:20px;font-size:.85em;color:var(--text2);
  transition:var(--trans);position:relative;cursor:pointer;
}
.nav-link:hover{color:var(--text);background:rgba(108,92,231,.08)}
.nav-link.active{color:#fff;background:var(--accent-g)}
.nav-link .badge{
  position:absolute;top:-4px;right:-4px;background:var(--danger);color:#fff;
  font-size:.65em;padding:1px 5px;border-radius:10px;font-weight:700;
}
.search-wrap{flex:1;max-width:480px;display:flex;gap:8px}
.search-wrap input{
  flex:1;background:var(--bg3);border:1px solid rgba(108,92,231,.15);
  color:var(--text);padding:8px 14px;border-radius:var(--radius);
  font-size:.9em;transition:var(--trans);
}
.search-wrap input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(108,92,231,.12)}
.search-wrap button{
  background:var(--accent-g);color:#fff;padding:8px 18px;border-radius:var(--radius);
  font-weight:600;font-size:.85em;transition:var(--trans);white-space:nowrap;
}
.search-wrap button:hover{opacity:.9;transform:translateY(-1px)}
.search-wrap button:disabled{opacity:.45;cursor:not-allowed;transform:none}

/* ═══ SOURCE TABS ═══ */
.src-tabs{
  display:flex;gap:6px;padding:8px 20px;background:rgba(18,18,26,.8);
  border-bottom:1px solid rgba(108,92,231,.08);overflow-x:auto;flex-shrink:0;
  scrollbar-width:none;
}
.src-tabs::-webkit-scrollbar{display:none}
.src-tab{
  padding:5px 13px;border-radius:18px;border:1px solid rgba(108,92,231,.15);
  color:var(--text2);cursor:pointer;font-size:.82em;transition:var(--trans);white-space:nowrap;flex-shrink:0;
}
.src-tab:hover{border-color:var(--accent);color:var(--text)}
.src-tab.active{background:var(--accent-g);color:#fff;border-color:transparent}

/* ═══ VIEWS ═══ */
.views-container{flex:1;overflow:hidden;position:relative}
.view{
  position:absolute;inset:0;overflow-y:auto;padding:16px 20px;
  opacity:0;transform:translateY(8px);pointer-events:none;
  transition:opacity .25s ease,transform .25s ease;
}
.view.active{opacity:1;transform:translateY(0);pointer-events:auto}

/* ═══ HOME VIEW ═══ */
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.rec-card{
  background:var(--bg2);border-radius:var(--r-lg);padding:18px;
  border:1px solid rgba(108,92,231,.08);transition:var(--trans);
}
.rec-card:hover{border-color:rgba(108,92,231,.2);transform:translateY(-3px);box-shadow:var(--shadow)}
.rec-card-title{font-weight:700;margin-bottom:12px;font-size:.95em;display:flex;align-items:center;gap:8px}
.rec-card-title .src-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.rec-tracks{display:flex;flex-direction:column;gap:4px}
.rec-track{
  display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:var(--r-sm);
  cursor:pointer;transition:var(--trans);
}
.rec-track:hover{background:var(--bg3)}
.rec-track-num{width:18px;text-align:center;color:var(--text3);font-size:.75em;flex-shrink:0;font-weight:600}
.rec-thumb{
  width:34px;height:34px;border-radius:6px;object-fit:cover;background:var(--bg4);flex-shrink:0;
}
.rec-track-info{flex:1;min-width:0}
.rec-track-title{font-size:.85em;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rec-track-artist{font-size:.75em;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rec-play-btn{
  width:28px;height:28px;border-radius:50%;background:rgba(108,92,231,.15);
  color:var(--accent2);display:flex;align-items:center;justify-content:center;
  font-size:.7em;opacity:0;transition:var(--trans);flex-shrink:0;
}
.rec-track:hover .rec-play-btn{opacity:1}

/* ═══ SEARCH VIEW ═══ */
.search-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.search-header h2{font-size:1.1em}
.search-header .count{color:var(--text3);font-size:.85em}
.track-list{display:grid;gap:6px}
.track-card{
  display:flex;align-items:center;gap:12px;padding:10px 14px;
  background:var(--bg2);border-radius:var(--radius);cursor:pointer;
  transition:var(--trans);border:1px solid transparent;
}
.track-card:hover{background:var(--bg3);border-color:rgba(108,92,231,.15);transform:translateX(3px)}
.track-card.playing{border-color:var(--accent);background:rgba(108,92,231,.08)}
.track-thumb-48{
  width:48px;height:48px;border-radius:var(--r-sm);object-fit:cover;background:var(--bg4);flex-shrink:0;
}
.track-info{flex:1;min-width:0}
.track-title{font-weight:500;font-size:.92em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track-meta{font-size:.78em;color:var(--text2);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.track-source{
  font-size:.68em;padding:2px 8px;border-radius:8px;background:rgba(108,92,231,.12);
  color:var(--accent2);flex-shrink:0;
}
.track-dur{font-size:.78em;color:var(--text3);flex-shrink:0;margin-left:8px}
.track-index{width:28px;font-size:.75em;color:var(--text3);flex-shrink:0;text-align:center}

/* ═══ HISTORY VIEW ═══ */
.history-list{display:grid;gap:6px}
.history-clear{margin-left:auto;padding:4px 10px;border-radius:var(--r-sm);font-size:.78em;color:var(--text3);border:1px solid rgba(255,255,255,.06);transition:var(--trans)}
.history-clear:hover{color:var(--danger);border-color:rgba(255,107,107,.3)}

/* ═══ NOW PLAYING VIEW ═══ */
.np-view{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:24px;padding:40px 20px;min-height:100%}
.np-artwork{
  width:280px;height:280px;border-radius:var(--r-xl);object-fit:cover;background:var(--bg3);
  box-shadow:0 8px 40px rgba(108,92,231,.2);transition:var(--trans);
}
.np-artwork.spin{animation:spin 12s linear infinite;border-radius:50%}
@keyframes spin{to{transform:rotate(360deg)}}
.np-info{text-align:center;max-width:400px}
.np-title{font-size:1.3em;font-weight:700;margin-bottom:6px}
.np-artist{font-size:.95em;color:var(--text2)}
.np-lyrics{text-align:center;max-width:500px;min-height:80px;color:var(--text2);font-size:.9em;line-height:1.8;white-space:pre-wrap;opacity:.8}

/* ═══ PLAYLIST SIDEBAR ═══ */
.pl-sidebar{
  position:fixed;right:-340px;top:0;bottom:0;width:320px;
  background:var(--bg2);border-left:1px solid rgba(108,92,231,.12);
  z-index:60;transition:right .3s ease;display:flex;flex-direction:column;
}
.pl-sidebar.open{right:0;box-shadow:-8px 0 30px rgba(0,0,0,.4)}
.pl-header{
  padding:16px;border-bottom:1px solid rgba(108,92,231,.08);
  display:flex;justify-content:space-between;align-items:center;flex-shrink:0;
}
.pl-header h3{font-size:.95em;font-weight:600}
.pl-close{color:var(--text2);font-size:1.1em;padding:4px;transition:var(--trans)}
.pl-close:hover{color:var(--text)}
.pl-items{flex:1;overflow-y:auto;padding:8px}
.pl-item{
  display:flex;align-items:center;gap:10px;padding:8px;border-radius:var(--r-sm);
  cursor:pointer;transition:var(--trans);
}
.pl-item:hover{background:var(--bg3)}
.pl-item.active{background:rgba(108,92,231,.12)}
.pl-item-thumb{
  width:38px;height:38px;border-radius:6px;background:var(--bg4);flex-shrink:0;
  object-fit:cover;
}
.pl-item-info{flex:1;min-width:0}
.pl-item-title{font-size:.83em;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pl-item-artist{font-size:.73em;color:var(--text3)}
.pl-item-del{
  width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:.7em;color:var(--text3);opacity:0;transition:var(--trans);flex-shrink:0;
}
.pl-item-del:hover{background:rgba(255,107,107,.15);color:var(--danger)}
.pl-item:hover .pl-item-del{opacity:1}

/* ═══ PLAYER BAR ═══ */
.player-bar{
  background:linear-gradient(180deg,var(--bg2),var(--bg3));
  border-top:1px solid rgba(108,92,231,.15);padding:8px 20px;
  display:none!important;align-items:center;gap:14px;flex-shrink:0;z-index:55;
  min-height:64px;
}
.player-bar.visible{display:flex!important}
.pb-track{display:flex;align-items:center;gap:10px;min-width:180px;max-width:260px;flex-shrink:0}
.pb-thumb{
  width:44px;height:44px;border-radius:var(--r-sm);object-fit:cover;background:var(--bg4);flex-shrink:0;
}
.pb-text{flex:1;min-width:0}
.pb-title{font-weight:500;font-size:.85em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pb-artist{font-size:.72em;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* controls */
.pb-controls{display:flex;align-items:center;gap:10px;flex-shrink:0}
.pb-btn{
  width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  transition:var(--trans);font-size:.9em;color:var(--text2);
}
.pb-btn:hover{background:rgba(108,92,231,.12);color:var(--text)}
.pb-btn-play{
  width:42px;height:42px;background:var(--accent-g);color:#fff;font-size:1.05em;
  box-shadow:0 2px 12px rgba(108,92,231,.3);
}
.pb-btn-play:hover{opacity:.9;transform:scale(1.05);color:#fff}

/* progress */
.pb-progress{flex:1;display:flex;align-items:center;gap:10px;min-width:0}
.pb-time{font-size:.7em;color:var(--text3);flex-shrink:0;min-width:36px;text-align:center}
.progress{flex:1;height:4px;background:var(--bg4);border-radius:2px;cursor:pointer;position:relative;transition:var(--trans);min-width:0}
.progress:hover{height:7px}
.progress-fill{height:100%;background:var(--accent-g);border-radius:2px;width:0%;transition:width .1s linear;position:relative}
.progress-fill::after{
  content:'';position:absolute;right:-5px;top:50%;transform:translateY(-50%);
  width:10px;height:10px;border-radius:50%;background:#fff;opacity:0;transition:opacity .2s;
  box-shadow:0 1px 4px rgba(0,0,0,.3);
}
.progress:hover .progress-fill::after{opacity:1}

/* mode buttons */
.pb-modes{display:flex;align-items:center;gap:6px;flex-shrink:0}
.pb-mode{
  width:30px;height:30px;border-radius:6px;display:flex;align-items:center;justify-content:center;
  font-size:.75em;color:var(--text3);transition:var(--trans);
}
.pb-mode:hover{background:rgba(108,92,231,.1);color:var(--text2)}
.pb-mode.active{color:var(--accent2);background:rgba(108,92,231,.12)}

/* volume */
.pb-vol{display:flex;align-items:center;gap:6px;flex-shrink:0}
.pb-vol input{width:70px;accent-color:var(--accent)}
.vol-btn{font-size:.9em;color:var(--text2);padding:4px}
.vol-btn:hover{color:var(--text)}

/* playlist toggle */
.pl-toggle-btn{
  width:36px;height:36px;border-radius:6px;display:flex;align-items:center;justify-content:center;
  font-size:.9em;color:var(--text2);transition:var(--trans);flex-shrink:0;
}
.pl-toggle-btn:hover{background:rgba(108,92,231,.1);color:var(--text)}
.pl-toggle-badge{
  position:absolute;top:-2px;right:-2px;background:var(--accent);color:#fff;
  font-size:.6em;padding:1px 4px;border-radius:8px;font-weight:700;
}

/* ═══ LOADING / EMPTY / TOAST ═══ */
.loading{display:flex;align-items:center;justify-content:center;padding:50px;color:var(--text2);gap:10px;flex-direction:column}
.spinner{
  width:28px;height:28px;border:2.5px solid var(--bg4);border-top-color:var(--accent);
  border-radius:50%;animation:spin .7s linear infinite;
}
.empty{text-align:center;padding:50px;color:var(--text3);font-size:.9em}
.empty-icon{font-size:2.5em;margin-bottom:12px}
.toast{
  position:fixed;bottom:80px;left:50%;transform:translateX(-50%) translateY(10px);
  background:var(--bg3);color:var(--text);padding:10px 20px;border-radius:var(--radius);
  font-size:.85em;z-index:100;opacity:0;transition:all .3s;pointer-events:none;
  border:1px solid rgba(108,92,231,.15);box-shadow:var(--shadow);
}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.err{border-color:rgba(255,107,107,.3);color:var(--danger)}

/* ═══ ANIMATIONS ═══ */
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.fade-in{animation:fadeIn .3s ease forwards}
@keyframes pulse{0%,100%{opacity:1}50%{about:invalid property}.5}
.pulse{animation:pulse 1.5s ease infinite}

/* ═══ RESPONSIVE ═══ */
@media(max-width:1024px){
  .pb-vol{display:none}
  .pb-modes{display:none}
}
@media(max-width:768px){
  .topnav{padding:8px 12px;height:auto;flex-wrap:wrap}
  .logo{font-size:1.05em}
  .nav-links{order:3;width:100%;justify-content:center;margin:6px 0 0}
  .search-wrap{order:2;max-width:100%;margin:8px 0 0}
  .src-tabs{padding:6px 12px}
  .view{padding:12px}
  .rec-grid{grid-template-columns:1fr}
  .player-bar{padding:6px 12px;gap:8px}
  .pb-progress{display:none}
  .pb-title{max-width:100px}
  .pl-sidebar{width:300px}
  .np-artwork{width:200px;height:200px}
}
@media(max-width:480px){
  .nav-link{padding:4px 10px;font-size:.78em}
  .track-card{padding:8px 10px}
  .track-thumb-48{width:40px;height:40px}
  .track-source{display:none}
  .pb-track{min-width:80px}
  .pb-thumb{width:36px;height:36px}
}
</style>
</head>
<body>
<div id="app">

  <!-- TOP NAV -->
  <nav class="topnav">
    <div class="logo">🎵 Music Player <span id="versionBadge" style="font-size:.5em;font-weight:400;opacity:.6;vertical-align:middle;margin-left:4px">v0.3.1</span></div>
    <div class="nav-links">
      <button class="nav-link active" onclick="switchView('home',this)">🏠 首页</button>
      <button class="nav-link" onclick="switchView('search',this)">🔍 搜索</button>
      <button class="nav-link" onclick="switchView('history',this)">🕐 历史</button>
      <button class="nav-link" onclick="switchView('nowplaying',this)">💿 正在播放</button>
    </div>
    <div class="search-wrap">
      <input type="text" id="searchInput" placeholder="搜索歌曲、歌手、专辑..." onkeydown="if(event.key==='Enter')triggerSearch()">
      <button id="searchBtn" onclick="triggerSearch()">🔍 搜索</button>
    </div>
  </nav>

  <!-- 全局搜索提示 -->
  <div class="global-search-hint" style="text-align:center;padding:4px 12px;font-size:.78em;color:var(--text3);background:var(--bg2);border-bottom:1px solid rgba(108,92,231,.08)">
    🔍 全局搜索 · 自动匹配最优音源 · 支持网易云/QQ/酷狗/B站/网盘
  </div>

  <!-- VIEWS -->
  <div class="views-container">

    <!-- HOME -->
    <div class="view active" id="view-home">
      <div class="loading" id="homeLoading">
        <div class="spinner"></div><span>正在加载推荐...</span>
      </div>
      <div id="homeContent"></div>
    </div>

    <!-- SEARCH -->
    <div class="view" id="view-search">
      <div class="search-header">
        <h2 id="searchTitle">搜索结果</h2>
        <span class="count" id="searchCount"></span>
      </div>
      <div id="searchContent">
        <div class="empty"><div class="empty-icon">🔍</div>输入关键词开始搜索音乐</div>
      </div>
    </div>

    <!-- HISTORY -->
    <div class="view" id="view-history">
      <div class="search-header">
        <h2>🕐 播放历史</h2>
        <button class="history-clear" onclick="clearHistory()">清空历史</button>
      </div>
      <div id="historyContent">
        <div class="empty"><div class="empty-icon">🕐</div>暂无播放历史</div>
      </div>
    </div>

    <!-- NOW PLAYING -->
    <div class="view np-view" id="view-nowplaying">
      <img class="np-artwork" id="npArtwork" src="" alt="">
      <div class="np-info">
        <div class="np-title" id="npTitle">未播放</div>
        <div class="np-artist" id="npArtist">-</div>
      </div>
      <div class="np-lyrics" id="npLyrics">♪ ♪ ♪</div>
    </div>

  </div>

  <!-- PLAYLIST SIDEBAR -->
  <div class="pl-sidebar" id="plSidebar">
    <div class="pl-header">
      <h3>📋 播放列表 <span id="plCount" style="color:var(--text3);font-weight:400;font-size:.85em">(<span id="plCountN">0</span>)</span></h3>
      <button class="pl-close" onclick="togglePL()">✕</button>
    </div>
    <div class="pl-items" id="plItems"><div class="empty">播放列表为空</div></div>
  </div>

  <!-- PLAYER BAR -->
  <div class="player-bar" id="playerBar" style="display:none">
    <div class="pb-track">
      <img class="pb-thumb" id="pbThumb" src="" alt="">
      <div class="pb-text">
        <div class="pb-title" id="pbTitle">未播放</div>
        <div class="pb-artist" id="pbArtist">-</div>
      </div>
    </div>
    <div class="pb-controls">
      <button class="pb-btn" onclick="prevTrack()" title="上一首">⏮</button>
      <button class="pb-btn pb-btn-play" id="playBtn" onclick="togglePlay()" title="播放/暂停">▶</button>
      <button class="pb-btn" onclick="nextTrack()" title="下一首">⏭</button>
    </div>
    <div class="pb-progress">
      <span class="pb-time" id="curTime">0:00</span>
      <div class="progress" id="progressBar" onclick="seek(event)">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <span class="pb-time" id="totTime">0:00</span>
    </div>
    <div class="pb-modes">
      <button class="pb-mode active" id="modeBtn" onclick="cycleMode()" title="播放模式">🔁</button>
    </div>
    <div class="pb-vol">
      <button class="vol-btn" onclick="toggleMute()" id="volBtn">🔊</button>
      <input type="range" id="volSlider" min="0" max="100" value="80" oninput="setVol(this.value)">
    </div>
    <button class="pl-toggle-btn" onclick="togglePL()" style="relative" title="播放列表">
      📋<span class="pl-toggle-badge" id="plBadge" style="display:none">0</span>
    </button>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
// ═══════════════════════════════════════
//  STATE
// ═══════════════════════════════════════
const S={src:'all',playlist:[],curIdx:-1,isPlaying:false,mode:'repeat',history:[],recs:{},curTrack:null,audio:null};

const MODES={repeat:{icon:'🔁',title:'列表循环'},shuffle:{icon:'🔀',title:'随机播放'},one:{icon:'🔂',title:'单曲循环'}};

const FALLBACK_IMG="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Crect fill='%23222236' width='48' height='48' rx='8'/%3E%3Ctext x='24' y='32' text-anchor='middle' fill='%236c5ce7' font-size='22'%3E🎵%3C/text%3E%3C/svg%3E";

// ═══════════════════════════════════════
//  INIT
// ═══════════════════════════════════════
document.addEventListener('DOMContentLoaded',()=>{
  S.audio=new Audio();S.audio.preload='auto';S.audio.volume=.8;
  S.audio.addEventListener('timeupdate',onTimeUpdate);
  S.audio.addEventListener('ended',onTrackEnd);
  S.audio.addEventListener('error',()=>showToast('播放失败，尝试其他音源','err'));
  S.audio.addEventListener('playing',()=>{S.isPlaying=true;onStateChange()});
  S.audio.addEventListener('pause',()=>{S.isPlaying=false;onStateChange()});
  loadRecommendations();
  loadHistory();
  // 动态获取版本号
  fetch('/').then(r=>r.json()).then(d=>{
    const b=document.getElementById('versionBadge');
    if(b&&d.version) b.textContent='v'+d.version;
  }).catch(()=>{});
  // 动态显示已配置的网盘标签
  fetch('/api/sources').then(r=>r.json()).then(d=>{
    (d.sources||[]).forEach(s=>{
      const tab=document.getElementById('tab-'+s.name);
      if(tab) tab.style.display='';
    });
  }).catch(()=>{});
  document.addEventListener('keydown',onKey);
  renderNP();
});

// ═══════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════
function switchView(name){
  const el=arguments.length>1?arguments[1]:null;
  document.querySelectorAll('.nav-link').forEach(b=>b.classList.remove('active'));
  if(el)el.classList.add('active');
  // support onclick="switchView('home')" without passing this
  if(!el){
    const btns=document.querySelectorAll('.nav-link');
    const map={home:0,search:1,history:2,nowplaying:3};
    if(btns[map[name]])btns[map[name]].classList.add('active');
  }
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  const target=document.getElementById('view-'+name);
  target.classList.add('active');
  if(name==='nowplaying')renderNP();
}

function switchSrc(el){
  // 全局模式：点击标签仅作视觉反馈，实际搜索全部源
  document.querySelectorAll('.src-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
}

// ═══════════════════════════════════════
//  SEARCH
// ═══════════════════════════════════════
// 全局搜索 - 不显示来源，自动匹配最优音源
async function triggerSearch(){
  const q=document.getElementById('searchInput').value.trim();
  if(!q)return;
  switchView('search');
  await globalSearch(q);
}

async function globalSearch(q){
  const btn=document.getElementById('searchBtn');
  const content=document.getElementById('searchContent');
  btn.disabled=true;btn.textContent='搜索中...';
  content.innerHTML='<div class="loading"><div class="spinner"></div><span>正在全网搜索「'+q+'」...</span></div>';
  document.getElementById('searchTitle').textContent='「'+q+'」的搜索结果';
  try{
    const res=await fetch(`/api/search?q=${encodeURIComponent(q)}&source=all&limit=50`);
    const data=await res.json();
    const tracks=(data.results||{}).all||[];
    renderGlobalResults(tracks);
    document.getElementById('searchCount').textContent=tracks.length?`共 ${tracks.length} 条结果`:'';
  }catch(e){
    content.innerHTML='<div class="empty"><div class="empty-icon">⚠️</div>搜索失败: '+e.message+'</div>';
  }
  btn.disabled=false;btn.textContent='🔍 搜索';
}

function renderGlobalResults(tracks){
  const content=document.getElementById('searchContent');
  if(!tracks.length){
    content.innerHTML='<div class="empty"><div class="empty-icon">😔</div>未找到结果，请尝试其他关键词</div>';
    return;
  }
  let html='<div class="track-list fade-in">';
  tracks.forEach((t,i)=>{
    const dur=fmtDur(t.duration);
    const thumb=t.thumbnail||FALLBACK_IMG;
    const src=t._source||'netease';
    html+=`<div class="track-card" onclick="playGlobalTrack('${escJS(t.id)}','${escJS(t.title)}','${escJS(t.artist)}','${escJS(thumb||'')}','${escJS(t.url||'')}',${t.duration||0},'${src}')">
      <span class="track-index">${i+1}</span>
      <img class="track-thumb-48" src="${thumb}" alt="" loading="lazy" onerror="this.src='${FALLBACK_IMG}'">
      <div class="track-info">
        <div class="track-title">${escHtml(t.title)}</div>
        <div class="track-meta">${escHtml(t.artist)}${t.album?' · '+escHtml(t.album):''}</div>
      </div>
      <span class="track-dur">${dur}</span>
    </div>`;
  });
  html+='</div>';
  content.innerHTML=html;
}

async function playGlobalTrack(id,title,artist,thumb,url,duration,source){
  const pb=document.getElementById('playerBar');
  pb.style.display='flex';
  pb.classList.add('visible');
  document.getElementById('pbTitle').textContent=title;
  document.getElementById('pbArtist').textContent=artist;
  document.getElementById('pbThumb').src=thumb||FALLBACK_IMG;
  document.getElementById('playBtn').textContent='⏳';
  S.isPlaying=false;
  const track={id,title,artist,thumb:thumb||'',url:url||'',duration:duration||0,source};
  const ex=S.playlist.findIndex(t=>t.id===id);
  if(ex>=0){S.curIdx=ex;}
  else{S.playlist.push(track);S.curIdx=S.playlist.length-1;}
  S.curTrack=track;
  updatePL();
  addHistory(track);
  try{
    const res=await fetch(`/api/stream?source=${source}&id=${encodeURIComponent(id)}`);
    if(!res.ok)throw new Error('无法获取播放地址');
    const data=await res.json();
    let stream=data.stream_url;
    if(!stream)throw new Error('播放地址为空');
    if(stream.startsWith('http'))stream=`/api/proxy?url=${encodeURIComponent(stream)}`;
    S.audio.src=stream;
    await S.audio.play();
  }catch(e){
    console.error(e);
    showToast('播放失败: '+e.message,'err');
    document.getElementById('playBtn').textContent='▶';
  }
  onStateChange();
  renderNP();
}

function trackCard(t,src){
  const dur=fmtDur(t.duration);
  const thumb=t.thumbnail||FALLBACK_IMG;
  const safeId=escJS(t.id);
  const safeTitle=escJS(t.title);
  const safeArtist=escJS(t.artist);
  const safeThumb=escJS(t.thumbnail||'');
  const safeUrl=escJS(t.url||'');
  return `<div class="track-card" data-id="${escAttr(t.id)}" onclick="playTrack('${src}','${safeId}','${safeTitle}','${safeArtist}','${safeThumb}','${safeUrl}',${t.duration||0})">
    <img class="track-thumb-48" src="${thumb}" alt="" loading="lazy" onerror="this.src='${FALLBACK_IMG}'">
    <div class="track-info">
      <div class="track-title">${escHtml(t.title)}</div>
      <div class="track-meta">${escHtml(t.artist)}${t.album?' · '+escHtml(t.album):''}</div>
    </div>
    <span class="track-source">${t.format||'audio'}</span>
    <span class="track-dur">${dur}</span>
  </div>`;
}

// ═══════════════════════════════════════
//  RECOMMENDATIONS
// ═══════════════════════════════════════
function loadRecommendations(){
  fetch('/api/recommendations')
    .then(r=>r.json())
    .then(data=>{
      S.recs=data;
      renderRecs();
    })
    .catch(e=>{
      document.getElementById('homeContent').innerHTML='<div class="empty"><div class="empty-icon">⚠️</div>加载失败: '+e.message+'</div>';
      document.getElementById('homeLoading').style.display='none';
    });
}

function renderRecs(){
  document.getElementById('homeLoading').style.display='none';
  const c=document.getElementById('homeContent');
  let html='<div class="rec-grid fade-in">';
  const colors={'netease':'#e74c3c','qq':'#31c27c','kugou':'#2daafc','bilibili':'#fb7299','youtube':'#ff6b6b','baidupan':'#3285ff','aliyun':'#ff6a00','quark':'#6c5ce7'};
  for(const[k,rec] of Object.entries(S.recs)){
    if(!rec.items||!rec.items.length)continue;
    const dotColor=colors[rec.source]||'var(--accent)';
    html+=`<div class="rec-card">
      <div class="rec-card-title"><span class="src-dot" style="background:${dotColor}"></span>${rec.title}</div>
      <div class="rec-tracks">`;
    rec.items.forEach((t,i)=>{
      const thumb=t.thumbnail||'';
      html+=`<div class="rec-track" onclick="playTrack('${rec.source}','${escJS(t.id)}','${escJS(t.title)}','${escJS(t.artist)}','${escJS(thumb)}','${escJS(t.url||'')}',${t.duration||0})">
        <span class="rec-track-num">${i+1}</span>
        ${thumb?`<img class="rec-thumb" src="${thumb}" loading="lazy" onerror="this.src='${FALLBACK_IMG}'">`:''}
        <div class="rec-track-info">
          <div class="rec-track-title">${escHtml(t.title)}</div>
          <div class="rec-track-artist">${escHtml(t.artist)}</div>
        </div>
        <button class="rec-play-btn">▶</button>
      </div>`;
    });
    html+='</div></div>';
  }
  html+='</div>';
  c.innerHTML=html;
}

// ═══════════════════════════════════════
//  PLAYBACK ENGINE
// ═══════════════════════════════════════
async function playTrack(source,id,title,artist,thumb,url,duration){
  // Show player bar only when playing
  const pb=document.getElementById('playerBar');
  pb.style.display='flex';
  pb.classList.add('visible');
  document.getElementById('pbTitle').textContent=title;
  document.getElementById('pbArtist').textContent=artist;
  document.getElementById('pbThumb').src=thumb||FALLBACK_IMG;
  document.getElementById('playBtn').textContent='⏳';
  S.isPlaying=false;

  // Add to playlist
  const track={source,id,title,artist,thumb:thumb||'',url:url||'',duration:duration||0};
  const ex=S.playlist.findIndex(t=>t.id===id&&t.source===source);
  if(ex>=0){
    S.curIdx=ex;
  }else{
    S.playlist.push(track);
    S.curIdx=S.playlist.length-1;
  }
  S.curTrack=track;
  updatePL();
  addHistory(track);

  // Fetch stream
  try{
    const res=await fetch(`/api/stream?source=${source}&id=${encodeURIComponent(id)}`);
    if(!res.ok)throw new Error('无法获取播放地址');
    const data=await res.json();
    let stream=data.stream_url;
    if(!stream)throw new Error('播放地址为空');
    if(stream.startsWith('http'))stream=`/api/proxy?url=${encodeURIComponent(stream)}`;
    S.audio.src=stream;
    await S.audio.play();
  }catch(e){
    console.error(e);
    showToast('播放失败: '+e.message,'err');
    document.getElementById('playBtn').textContent='▶';
  }
  onStateChange();
  renderNP();
}

function togglePlay(){
  if(!S.audio.src)return;
  if(S.audio.paused){S.audio.play();}else{S.audio.pause();}
}

function prevTrack(){
  if(!S.playlist.length)return;
  if(S.mode==='shuffle'){S.curIdx=Math.floor(Math.random()*S.playlist.length);}
  else if(S.mode==='one'){S.audio.currentTime=0;S.audio.play();return;}
  else{S.curIdx=(S.curIdx-1+S.playlist.length)%S.playlist.length;}
  playCur();
}

function nextTrack(){
  if(!S.playlist.length)return;
  if(S.mode==='shuffle'){S.curIdx=Math.floor(Math.random()*S.playlist.length);}
  else if(S.mode==='one'){S.audio.currentTime=0;S.audio.play();return;}
  else{S.curIdx=(S.curIdx+1)%S.playlist.length;}
  playCur();
}

function playCur(){
  if(S.curIdx<0||S.curIdx>=S.playlist.length)return;
  const t=S.playlist[S.curIdx];
  playTrack(t.source,t.id,t.title,t.artist,t.thumb,t.url,t.duration);
}

let cachedTrackCards={};
function onStateChange(){
  document.getElementById('playBtn').textContent=S.isPlaying?'⏸':'▶';
  // Update playing state on cards
  document.querySelectorAll('.track-card').forEach(c=>c.classList.remove('playing'));
  if(S.curTrack){
    const card=document.querySelector(`.track-card[data-id="${S.curTrack.id}"]`);
    if(card){card.classList.add('playing');card.scrollIntoView({behavior:'smooth',block:'nearest'});}
  }
  renderNP();
}

function onTimeUpdate(){
  if(!S.audio.duration)return;
  const pct=(S.audio.currentTime/S.audio.duration)*100;
  document.getElementById('progressFill').style.width=pct+'%';
  document.getElementById('curTime').textContent=fmtDur(S.audio.currentTime);
  document.getElementById('totTime').textContent=fmtDur(S.audio.duration);
}

function onTrackEnd(){
  S.isPlaying=false;
  nextTrack();
}

function seek(e){
  if(!S.audio.duration)return;
  const bar=e.currentTarget,rect=bar.getBoundingClientRect();
  S.audio.currentTime=((e.clientX-rect.left)/rect.width)*S.audio.duration;
}

function setVol(v){S.audio.volume=v/100;}
function toggleMute(){
  S.audio.muted=!S.audio.muted;
  document.getElementById('volBtn').textContent=S.audio.muted?'🔇':'🔊';
}

function cycleMode(){
  const order=['repeat','shuffle','one'];
  const cur=order.indexOf(S.mode);
  S.mode=order[(cur+1)%order.length];
  const m=MODES[S.mode];
  const btn=document.getElementById('modeBtn');
  btn.textContent=m.icon;
  btn.title=m.title;
  showToast(m.title);
}

// ═══════════════════════════════════════
//  PLAYLIST
// ═══════════════════════════════════════
function togglePL(){
  document.getElementById('plSidebar').classList.toggle('open');
}

function updatePL(){
  const c=document.getElementById('plItems');
  document.getElementById('plCountN').textContent=S.playlist.length;
  const badge=document.getElementById('plBadge');
  badge.textContent=S.playlist.length;
  badge.style.display=S.playlist.length?'block':'none';
  if(!S.playlist.length){c.innerHTML='<div class="empty">播放列表为空</div>';return;}
  let html='';
  S.playlist.forEach((t,i)=>{
    const active=i===S.curIdx?' active':'';
    html+=`<div class="pl-item${active}" onclick="playByIdx(${i})">
      <div class="pl-item-thumb" style="background:url(${t.thumbnail||''}) center/cover,var(--bg4)"></div>
      <div class="pl-item-info">
        <div class="pl-item-title">${escHtml(t.title)}</div>
        <div class="pl-item-artist">${escHtml(t.artist)}</div>
      </div>
      <button class="pl-item-del" onclick="event.stopPropagation();rmTrack(${i})">✕</button>
    </div>`;
  });
  c.innerHTML=html;
}

function playByIdx(i){
  S.curIdx=i;
  playCur();
  updatePL();
}

function rmTrack(i){
  S.playlist.splice(i,1);
  if(i<S.curIdx)S.curIdx--;
  else if(i===S.curIdx){
    S.curIdx=-1;S.audio.src='';
    const pb=document.getElementById('playerBar');
    pb.style.display='none';pb.classList.remove('visible');
  }
  updatePL();
  onStateChange();
}

// ═══════════════════════════════════════
//  HISTORY
// ═══════════════════════════════════════
function loadHistory(){
  try{S.history=JSON.parse(localStorage.getItem('mplayer_history')||'[]');}catch(e){S.history=[];}
}

function saveHistory(){
  localStorage.setItem('mplayer_history',JSON.stringify(S.history.slice(0,100)));
}

function addHistory(t){
  if(!t||!t.id)return;
  S.history=S.history.filter(h=>h.id!==t.id||h.source!==t.source);
  S.history.unshift({...t,ts:Date.now()});
  S.history=S.history.slice(0,100);
  saveHistory();
}

function clearHistory(){
  S.history=[];
  saveHistory();
  renderHistory();
}

function renderHistory(){
  const c=document.getElementById('historyContent');
  if(!S.history.length){c.innerHTML='<div class="empty"><div class="empty-icon">🕐</div>暂无播放历史</div>';return;}
  let html='<div class="history-list fade-in">';
  S.history.forEach(t=>{
    const dur=fmtDur(t.duration);
    const thumb=t.thumbnail||FALLBACK_IMG;
    html+=`<div class="track-card" onclick="playTrack('${t.source}','${escJS(t.id)}','${escJS(t.title)}','${escJS(t.artist)}','${escJS(t.thumb||'')}','${escJS(t.url||'')}',${t.duration||0})">
      <img class="track-thumb-48" src="${thumb}" alt="" loading="lazy" onerror="this.src='${FALLBACK_IMG}'">
      <div class="track-info">
        <div class="track-title">${escHtml(t.title)}</div>
        <div class="track-meta">${escHtml(t.artist)}</div>
      </div>
      <span class="track-dur">${dur}</span>
    </div>`;
  });
  html+='</div>';
  c.innerHTML=html;
}

// render history when view is shown
const _orig_switchView=switchView;
window.switchView=function(name){
  _orig_switchView.apply(this,arguments);
  if(name==='history')renderHistory();
  if(name==='nowplaying')renderNP();
};

// ═══════════════════════════════════════
//  NOW PLAYING
// ═══════════════════════════════════════
function renderNP(){
  const np=document.getElementById('view-nowplaying');
  if(!S.curTrack){
    document.getElementById('npArtwork').src=FALLBACK_IMG;
    document.getElementById('npTitle').textContent='未播放';
    document.getElementById('npArtist').textContent='-';
    document.getElementById('npLyrics').textContent='♪ ♪ ♪';
    return;
  }
  document.getElementById('npArtwork').src=S.curTrack.thumb||FALLBACK_IMG;
  document.getElementById('npTitle').textContent=S.curTrack.title;
  document.getElementById('npArtist').textContent=S.curTrack.artist;
  document.getElementById('npArtwork').classList.toggle('spin',S.isPlaying);
}

// ═══════════════════════════════════════
//  KEYBOARD SHORTCUTS
// ═══════════════════════════════════════
function onKey(e){
  if(e.target.tagName==='INPUT')return;
  switch(e.code){
    case 'Space':e.preventDefault();togglePlay();break;
    case 'ArrowLeft':S.audio.currentTime=Math.max(0,S.audio.currentTime-5);break;
    case 'ArrowRight':S.audio.currentTime=Math.min(S.audio.duration,S.audio.currentTime+5);break;
    case 'ArrowUp':S.audio.volume=Math.min(1,S.audio.volume+.05);document.getElementById('volSlider').value=S.audio.volume*100;break;
    case 'ArrowDown':S.audio.volume=Math.max(0,S.audio.volume-.05);document.getElementById('volSlider').value=S.audio.volume*100;break;
    case 'KeyM':toggleMute();break;
    case 'KeyS':document.getElementById('searchInput').focus();break;
  }
}

// ═══════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════
function fmtDur(s){
  if(!s||s<=0||isNaN(s))return'-:--';
  s=Math.floor(s);
  const m=Math.floor(s/60);const sec=s%60;
  return m+':'+(sec<10?'0':'')+sec;
}
function escHtml(s){
  if(!s)return'';
  const d=document.createElement('div');d.textContent=s;return d.innerHTML;
}
function escAttr(s){
  return s?String(s).replace(/"/g,'&quot;'):'';
}
function escJS(s){
  if(!s)return'';
  return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/\n/g,' ');
}
function showToast(msg,type){
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.className='toast show'+(type==='err'?' err':'');
  setTimeout(()=>t.className='toast',3000);
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
