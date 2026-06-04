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
        """使用B站API直接获取音频流URL，避免yt-dlp防盗链问题"""
        try:
            # 1. 先通过搜索API获取cid和标题信息
            info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            headers = {
                **COMMON_HEADERS,
                "Referer": f"https://www.bilibili.com/video/{bvid}",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(info_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json(encoding="utf-8", content_type=None)
                    if data.get("code") != 0:
                        return {}
                    video_data = data.get("data", {})
                    cid = video_data.get("cid", 0)
                    title = video_data.get("title", "")
                    artist = video_data.get("owner", {}).get("name", "")
                    duration = video_data.get("duration", 0)
                    thumbnail = video_data.get("pic", "")
                    if not cid:
                        return {}

            # 2. 获取播放流URL（请求高音质音频）
            play_url = "https://api.bilibili.com/x/player/playurl"
            params = {
                "bvid": bvid,
                "cid": cid,
                "fnval": "16",  # 请求DASH格式，包含独立音频流
                "qn": "32",     # 低画质（只要音频）
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(play_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {}
                    play_data = await resp.json(encoding="utf-8", content_type=None)
                    if play_data.get("code") != 0:
                        return {}
                    dash = play_data.get("data", {}).get("dash")
                    if dash:
                        # DASH格式：提取音频流
                        audio_list = dash.get("audio", [])
                        if audio_list:
                            # 按带宽排序，取最高音质
                            audio_list.sort(key=lambda x: x.get("bandwidth", 0), reverse=True)
                            audio_url = audio_list[0].get("baseUrl", "") or audio_list[0].get("base_url", "")
                            return {
                                "stream_url": audio_url,
                                "title": title,
                                "artist": artist,
                                "duration": duration,
                                "thumbnail": thumbnail,
                                "format": "m4a",
                            }
                    # 无DASH，尝试durl
                    durl = play_data.get("data", {}).get("durl", [])
                    if durl:
                        return {
                            "stream_url": durl[0].get("url", ""),
                            "title": title,
                            "artist": artist,
                            "duration": duration,
                            "thumbnail": thumbnail,
                            "format": "flv",
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
    check: bool = Query(True, description="是否预检测链接可用性"),
):
    """全局搜索：自动搜索所有可用源，合并去重，预检测链接可用性"""
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
    
    # 预检测：批量检测链接可用性，只返回能播放的歌曲
    if check and merged:
        merged = await _filter_playable(merged, max_check=30)
    
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


async def _filter_playable(tracks: list, max_check: int = 30) -> list:
    """批量预检测歌曲链接可用性，只返回能播放的歌曲（并发检测，最多max_check首）"""
    check_tracks = tracks[:max_check]
    remaining = tracks[max_check:]
    
    async def _check_one(t: dict) -> bool:
        src = t.get("_source", "netease")
        tid = t.get("id", "")
        if not tid:
            return False
        try:
            stream_info = await asyncio.wait_for(
                source_manager.get_stream(src, tid),
                timeout=8
            )
            stream_url = stream_info.get("stream_url", "")
            if not stream_url:
                return False
            # 检测链接是否真的可用
            parsed = urlparse(stream_url)
            host = parsed.host.lower()
            if "bilibili" in host or "bilivideo" in host:
                referer = "https://www.bilibili.com/"
            elif "youtube" in host or "googlevideo" in host:
                referer = "https://www.youtube.com/"
            elif "music.126" in host or "163" in host:
                referer = "https://music.163.com/"
            elif "qq.com" in host or "gtimg" in host:
                referer = "https://y.qq.com/"
            elif "kugou" in host:
                referer = "https://www.kugou.com/"
            else:
                referer = "https://www.bilibili.com/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": referer,
                "Range": "bytes=0-1023",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as resp:
                    return resp.status in (200, 206)
        except Exception:
            return False
    
    # 并发检测所有歌曲
    tasks = [_check_one(t) for t in check_tracks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    playable = []
    for t, ok in zip(check_tracks, results):
        if ok is True:
            playable.append(t)
        else:
            print(f"[Filter] 不可播放: {t.get('title', '')} ({t.get('_source', '')})")
    
    # 超出max_check部分直接保留（不检测）
    playable.extend(remaining)
    print(f"[Filter] 预检测: {len(check_tracks)}首中{len(playable)-len(remaining)}首可播放")
    return playable


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


@app.get("/api/lyric")
async def get_lyric(
    source: str = Query("netease", description="音乐源"),
    id: str = Query(..., description="音乐ID"),
):
    """获取歌词"""
    # 网易云：使用 tonzhon API
    if source == "netease":
        try:
            url = "https://tonzhon.com/api.php"
            payload = f"types=lyric&id={id}&source=netease"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://tonzhon.com/",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text(encoding="utf-8")
                        data = json.loads(text)
                        lyric = data.get("lyric", "")
                        if lyric and lyric.startswith("data:text/plain,"):
                            lyric = lyric[len("data:text/plain,"):]
                        return {"lyric": lyric}
        except Exception as e:
            print(f"[Lyric] error: {e}")
    
    return {"lyric": ""}


@app.get("/api/check")
async def check_url(url: str = Query(...)):
    """检测播放链接是否可用（GET Range 请求前1KB，5秒超时）"""
    try:
        parsed = urlparse(url)
        host = parsed.host.lower()
        if "bilibili" in host or "bilivideo" in host:
            referer = "https://www.bilibili.com/"
        elif "youtube" in host or "googlevideo" in host:
            referer = "https://www.youtube.com/"
        elif "music.126" in host or "163" in host:
            referer = "https://music.163.com/"
        elif "qq.com" in host or "gtimg" in host:
            referer = "https://y.qq.com/"
        elif "kugou" in host:
            referer = "https://www.kugou.com/"
        else:
            referer = "https://www.bilibili.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": referer,
            "Range": "bytes=0-1023",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as resp:
                ok = resp.status in (200, 206)
                return {"ok": ok, "status": resp.status}
    except Exception:
        return {"ok": False, "status": 0}


@app.get("/api/proxy")
async def proxy_stream(url: str = Query(..., description="音频流URL")):
    try:
        # 根据URL来源动态设置Referer，绕过防盗链
        parsed = urlparse(url)
        host = parsed.host.lower()
        if "bilibili" in host or "bilivideo" in host:
            referer = "https://www.bilibili.com/"
        elif "youtube" in host or "googlevideo" in host:
            referer = "https://www.youtube.com/"
        elif "music.126" in host or "163" in host:
            referer = "https://music.163.com/"
        elif "qq.com" in host or "gtimg" in host:
            referer = "https://y.qq.com/"
        elif "kugou" in host:
            referer = "https://www.kugou.com/"
        else:
            referer = "https://www.bilibili.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": referer,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=120), allow_redirects=True) as resp:
                if resp.status >= 400:
                    raise HTTPException(status_code=502, detail=f"源站返回 {resp.status}")
                content_type = resp.headers.get("Content-Type", "audio/mpeg")
                async def stream_generator():
                    try:
                        async for chunk in resp.content.iter_chunked(8192):
                            yield chunk
                    except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError, ConnectionResetError, asyncio.CancelledError):
                        pass
                return StreamingResponse(
                    stream_generator(),
                    media_type=content_type,
                    headers={"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}
                )
    except HTTPException:
        raise
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
<title>🎵 Music Player</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎵</text></svg>">
<style>
:root{--bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a28;--bg4:#222236;--bg5:#2a2a3e;--accent:#6c5ce7;--accent-g:linear-gradient(135deg,#6c5ce7,#8b5cf6);--accent2:#a29bfe;--accent3:#74b9ff;--text:#e0e0e8;--text2:#9090a8;--text3:#606078;--success:#00b894;--warning:#fdcb6e;--danger:#ff6b6b;--radius:12px;--r-sm:8px;--r-lg:16px;--r-xl:20px;--shadow:0 4px 24px rgba(0,0,0,.4);--shadow-sm:0 2px 8px rgba(0,0,0,.3);--trans:.25s cubic-bezier(.4,0,.2,1)}
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
#app{display:flex;flex-direction:column;height:100vh;overflow:hidden}
.topnav{display:flex;align-items:center;gap:16px;padding:10px 20px;background:var(--bg2);border-bottom:1px solid rgba(108,92,231,.1);flex-shrink:0;z-index:50;height:52px}
.logo{font-size:1.15em;font-weight:800;background:var(--accent-g);-webkit-background-clip:text;-webkit-text-fill-color:transparent;white-space:nowrap;letter-spacing:-.5px;display:flex;align-items:center;gap:6px}
.logo .ver{font-size:.45em;font-weight:400;opacity:.5;vertical-align:middle}
.nav-links{display:flex;gap:4px;margin:0 auto}
.nav-link{padding:5px 12px;border-radius:16px;font-size:.82em;color:var(--text2);transition:var(--trans);position:relative;cursor:pointer}
.nav-link:hover{color:var(--text);background:rgba(108,92,231,.08)}
.nav-link.active{color:#fff;background:var(--accent-g)}
.search-wrap{display:flex;gap:6px;max-width:360px;width:100%}
.search-wrap input{flex:1;padding:6px 14px;border-radius:20px;border:1px solid rgba(108,92,231,.15);background:var(--bg3);color:var(--text);font-size:.85em;transition:var(--trans)}
.search-wrap input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(108,92,231,.15)}
.search-wrap input::placeholder{color:var(--text3)}
.search-wrap button{padding:6px 14px;border-radius:20px;background:var(--accent-g);color:#fff;font-size:.82em;font-weight:500;transition:var(--trans);white-space:nowrap}
.search-wrap button:hover{opacity:.9;transform:scale(1.02)}
.search-wrap button:disabled{opacity:.5;transform:none}
.views-container{flex:1;overflow-y:auto;overflow-x:hidden;position:relative}
.view{display:none;height:100%;overflow-y:auto}
.view.active{display:block}
#view-home{padding:16px}
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.rec-card{background:var(--bg2);border-radius:var(--radius);padding:14px;border:1px solid rgba(108,92,231,.06);transition:var(--trans)}
.rec-card:hover{border-color:rgba(108,92,231,.15)}
.rec-card-title{font-size:.88em;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.src-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.rec-tracks{display:grid;gap:4px}
.rec-track{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:var(--r-sm);cursor:pointer;transition:var(--trans)}
.rec-track:hover{background:var(--bg3)}
.rec-track-num{width:18px;font-size:.7em;color:var(--text3);text-align:center;flex-shrink:0}
.rec-thumb{width:30px;height:30px;border-radius:4px;object-fit:cover;background:var(--bg4);flex-shrink:0}
.rec-track-info{flex:1;min-width:0}
.rec-track-title{font-size:.8em;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rec-track-artist{font-size:.7em;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#view-search{padding:16px}
.search-header{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.search-header h2{font-size:1em;font-weight:600}
.search-header .count{font-size:.75em;color:var(--text3)}
.search-results{display:grid;gap:4px}
.song-item{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:var(--r-sm);cursor:pointer;transition:var(--trans);position:relative}
.song-item:hover{background:var(--bg3)}
.song-item.playing{background:rgba(108,92,231,.1);border-left:2px solid var(--accent)}
.song-thumb{width:36px;height:36px;border-radius:6px;object-fit:cover;background:var(--bg4);flex-shrink:0}
.song-info{flex:1;min-width:0}
.song-title{font-size:.85em;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.song-artist{font-size:.72em;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.song-duration{font-size:.7em;color:var(--text3);flex-shrink:0;margin-left:8px}
.song-acts{display:flex;gap:4px;opacity:0;transition:var(--trans)}
.song-item:hover .song-acts{opacity:1}
.song-act-btn{padding:4px 8px;border-radius:6px;font-size:.7em;color:var(--text2);background:var(--bg4);transition:var(--trans)}
.song-act-btn:hover{color:#fff;background:var(--accent)}
.song-act-btn.dl:hover{background:var(--success)}
#view-nowplaying{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;gap:16px}
.lyric-cover{width:180px;height:180px;border-radius:var(--r-lg);object-fit:cover;background:var(--bg4);box-shadow:0 8px 40px rgba(108,92,231,.2);flex-shrink:0}
.lyric-info{text-align:center}
.lyric-song{font-size:1.1em;font-weight:700;margin-bottom:4px}
.lyric-artist{font-size:.85em;color:var(--text2)}
.lyric-box{width:100%;max-width:420px;height:200px;overflow-y:auto;text-align:center;padding:10px 16px;mask-image:linear-gradient(transparent 0%,#000 15%,#000 85%,transparent 100%);-webkit-mask-image:linear-gradient(transparent 0%,#000 15%,#000 85%,transparent 100%)}
.lyric-line{font-size:.85em;color:var(--text3);padding:5px 0;transition:var(--trans);line-height:1.6}
.lyric-line.active{color:var(--accent2);font-size:.95em;font-weight:600}
.lyric-empty{color:var(--text3);font-size:.85em;text-align:center;padding-top:60px}
.player-bar{display:flex;align-items:center;gap:12px;padding:8px 16px;background:var(--bg2);border-top:1px solid rgba(108,92,231,.1);flex-shrink:0;z-index:50;height:60px}
.pb-info{display:flex;align-items:center;gap:10px;flex:1;min-width:0;overflow:hidden}
.pb-thumb{width:38px;height:38px;border-radius:6px;object-fit:cover;background:var(--bg4);flex-shrink:0;cursor:pointer;transition:var(--trans)}
.pb-thumb:hover{opacity:.8}
.pb-text{min-width:0}
.pb-title{font-size:.82em;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pb-artist{font-size:.7em;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pb-controls{display:flex;align-items:center;gap:6px;flex-shrink:0}
.pb-btn{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--text2);transition:var(--trans);font-size:.9em}
.pb-btn:hover{color:#fff;background:rgba(108,92,231,.15)}
.pb-btn.play{width:38px;height:38px;background:var(--accent-g);color:#fff;font-size:1em}
.pb-btn.play:hover{opacity:.9;transform:scale(1.05)}
.pb-btn.active{color:var(--accent)}
.pb-extra{display:flex;align-items:center;gap:4px;flex-shrink:0}
.pb-btn.dl{color:var(--success)}
.pb-btn.dl:hover{background:rgba(0,184,148,.15)}
.pb-progress{flex:1;max-width:200px;display:flex;align-items:center;gap:8px}
.pb-time{font-size:.65em;color:var(--text3);white-space:nowrap;min-width:30px}
.pb-bar{flex:1;height:3px;background:var(--bg5);border-radius:2px;cursor:pointer;position:relative}
.pb-bar-fill{height:100%;background:var(--accent-g);border-radius:2px;width:0%;transition:.1s linear}
.pb-bar:hover{height:5px}
.pb-volume{display:flex;align-items:center;gap:4px}
.pb-vol-bar{width:60px;height:3px;background:var(--bg5);border-radius:2px;cursor:pointer}
.pb-vol-fill{height:100%;background:var(--accent);border-radius:2px;width:70%}
#view-playlist{padding:16px}
.pl-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.pl-header h2{font-size:1em;font-weight:600}
.pl-header .count{font-size:.75em;color:var(--text3)}
.pl-clear{font-size:.75em;color:var(--danger);cursor:pointer;padding:4px 10px;border-radius:6px;transition:var(--trans)}
.pl-clear:hover{background:rgba(255,107,107,.1)}
.pl-items{display:grid;gap:2px}
.pl-item{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:var(--r-sm);cursor:pointer;transition:var(--trans)}
.pl-item:hover{background:var(--bg3)}
.pl-item.playing{background:rgba(108,92,231,.08)}
.pl-idx{width:20px;font-size:.7em;color:var(--text3);text-align:center;flex-shrink:0}
.pl-title{font-size:.82em;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pl-artist{font-size:.7em;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px}
.pl-dur{font-size:.7em;color:var(--text3);flex-shrink:0}
.pl-del{font-size:.75em;color:var(--text3);padding:4px;border-radius:4px;opacity:0;transition:var(--trans)}
.pl-item:hover .pl-del{opacity:1}
.pl-del:hover{color:var(--danger)}
.pl-empty{color:var(--text3);text-align:center;padding:40px;font-size:.85em}
.loading{text-align:center;padding:30px;color:var(--text3);font-size:.85em}
.loading::after{content:'';display:inline-block;width:14px;height:14px;border:2px solid var(--bg5);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-left:8px}
@keyframes spin{to{transform:rotate(360deg)}}
.empty-state{text-align:center;padding:40px;color:var(--text3);font-size:.85em}
.empty-state .icon{font-size:2em;margin-bottom:8px}
.toast{position:fixed;bottom:70px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--bg4);color:var(--text);padding:8px 16px;border-radius:20px;font-size:.8em;box-shadow:var(--shadow);z-index:100;opacity:0;transition:var(--trans);white-space:nowrap;pointer-events:none}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.footer-note{text-align:center;padding:8px;font-size:.65em;color:var(--text3);opacity:.5;flex-shrink:0;background:var(--bg2)}
@media(max-width:640px){.topnav{padding:8px 12px;gap:8px}.logo{font-size:1em}.nav-link{padding:4px 8px;font-size:.75em}.search-wrap{max-width:200px}.search-wrap input{padding:5px 10px;font-size:.8em}.search-wrap button{padding:5px 10px;font-size:.75em}.pb-progress{display:none}.pb-volume{display:none}.lyric-cover{width:140px;height:140px}.lyric-box{height:160px}}
</style>
</head>
<body>
<div id="app">
<div class="topnav">
<div class="logo">&#x1F3B5; Music<span class="ver" id="nav-ver"></span></div>
<div class="nav-links">
<div class="nav-link active" data-view="home">&#x1F3E0; 首页</div>
<div class="nav-link" data-view="search">&#x1F50D; 搜索</div>
<div class="nav-link" data-view="nowplaying">&#x1F4BF; 正在播放</div>
<div class="nav-link" data-view="playlist">&#x1F4CB; 列表</div>
</div>
<div class="search-wrap">
<input id="search-input" type="text" placeholder="全局搜索歌曲、歌手&#x2026;" autocomplete="off">
<button id="search-btn" onclick="doSearch()">&#x1F50D; 搜索</button>
</div>
</div>
<div class="views-container">
<div class="view active" id="view-home">
<div id="rec-list" class="rec-grid"><div class="loading">加载推荐中</div></div>
</div>
<div class="view" id="view-search">
<div class="search-header"><h2>&#x1F50D; 搜索结果</h2><span class="count" id="search-count"></span></div>
<div id="search-results" class="search-results"></div>
</div>
<div class="view" id="view-nowplaying">
<img class="lyric-cover" id="lyric-cover" src="" alt="">
<div class="lyric-info"><div class="lyric-song" id="lyric-song">&#x2014;</div><div class="lyric-artist" id="lyric-artist">&#x2014;</div></div>
<div class="lyric-box" id="lyric-box"><div class="lyric-empty">搜索并播放歌曲，歌词将在这里显示</div></div>
</div>
<div class="view" id="view-playlist">
<div class="pl-header"><h2>&#x1F4CB; 播放列表 <span class="count" id="pl-count">(0)</span></h2><span class="pl-clear" onclick="clearPlaylist()">清空</span></div>
<div id="pl-items" class="pl-items"><div class="pl-empty">播放列表为空，去搜索歌曲吧 &#x1F3B5;</div></div>
</div>
</div>
<div class="footer-note">因各大平台限制，部分歌曲可能无法播放</div>
<div class="player-bar" id="player-bar">
<div class="pb-info">
<img class="pb-thumb" id="pb-thumb" src="" onclick="switchView('nowplaying')" alt="">
<div class="pb-text"><div class="pb-title" id="pb-title">未播放</div><div class="pb-artist" id="pb-artist">&#x2014;</div></div>
</div>
<div class="pb-controls">
<button class="pb-btn" onclick="prevTrack()" title="上一首">&#x23EE;</button>
<button class="pb-btn play" id="pb-play" onclick="togglePlay()" title="播放/暂停">&#x25B6;</button>
<button class="pb-btn" onclick="nextTrack()" title="下一首">&#x23ED;</button>
</div>
<div class="pb-progress">
<span class="pb-time" id="pb-cur">0:00</span>
<div class="pb-bar" id="pb-bar" onclick="seekTrack(event)"><div class="pb-bar-fill" id="pb-bar-fill"></div></div>
<span class="pb-time" id="pb-dur">0:00</span>
</div>
<div class="pb-extra">
<button class="pb-btn dl" id="pb-dl" onclick="downloadCurrent()" title="下载">&#x2B07;</button>
<button class="pb-btn" id="pb-mode" onclick="cycleMode()" title="播放模式">&#x1F501;</button>
<div class="pb-volume"><button class="pb-btn" onclick="toggleMute()" id="pb-vol-btn" title="音量">&#x1F50A;</button><div class="pb-vol-bar" onclick="setVolume(event)"><div class="pb-vol-fill" id="pb-vol-fill"></div></div></div>
</div>
</div>
<div class="toast" id="toast"></div>
</div>
<audio id="audio" preload="none"></audio>
<script>
const audio=document.getElementById("audio");
let S={view:"home",list:[],idx:-1,playing:false,mode:"all",muted:false,vol:.7,checked:new Set(),failed:new Set(),lyric:[],lyricIdx:-1,pl:[]};
const $=id=>document.getElementById(id);
function toast(m){const t=$("toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2000)}
function fmt(s){s=Math.floor(s);return Math.floor(s/60)+":"+(s%60).toString().padStart(2,"0")}
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}
async function api(p,ps={}){const u=new URL(p,location.origin);Object.entries(ps).forEach(([k,v])=>u.searchParams.set(k,v));const r=await fetch(u);if(!r.ok)throw new Error(r.status);return r.json()}
function proxyUrl(u){return"/api/proxy?url="+encodeURIComponent(u)}
async function checkUrl(u){try{const r=await fetch("/api/check?url="+encodeURIComponent(u),{signal:AbortSignal.timeout(4000)});return(await r.json()).ok}catch(e){return false}}
function switchView(v){S.view=v;document.querySelectorAll(".nav-link").forEach(e=>e.classList.toggle("active",e.dataset.view===v));document.querySelectorAll(".view").forEach(e=>e.classList.toggle("active",e.id==="view-"+v));if(v==="nowplaying")renderLyric();if(v==="playlist")renderPlaylist()}
document.querySelectorAll(".nav-link").forEach(e=>e.addEventListener("click",()=>switchView(e.dataset.view)));
async function doSearch(){const q=$("search-input").value.trim();if(!q)return;switchView("search");$("search-results").innerHTML='<div class="loading">搜索中</div>';$("search-count").textContent="";try{const d=await api("/api/search",{q,source:"all"});const res=d.results;S.list=(res&&res.all)?res.all:(Array.isArray(res)?res:[]);S.idx=-1;S.checked.clear();S.failed.clear();renderSearch()}catch(e){$("search-results").innerHTML='<div class="empty-state"><div class="icon">&#x274C;</div>搜索失败</div>'}}
$("search-input").addEventListener("keydown",e=>{if(e.key==="Enter")doSearch()});
function renderSearch(){const c=$("search-results");$("search-count").textContent=S.list.length+" \u9996";if(!S.list.length){c.innerHTML='<div class="empty-state"><div class="icon">&#x1F50D;</div>\u672a\u627e\u5230\u76f8\u5173\u6b4c\u66f2</div>';return}c.innerHTML=S.list.map((s,i)=>{const id=s.id;const ip=S.idx===i&&S.playing;if(S.failed.has(id))return"";return'<div class="song-item'+(ip?" playing":"")+'" data-idx="'+i+'"><img class="song-thumb" src="'+esc(s.cover||s.thumbnail||"")+'" onerror="this.style.background=\'var(--bg4)\'"><div class="song-info"><div class="song-title">'+esc(s.title)+'</div><div class="song-artist">'+esc(s.artist)+'</div></div><span class="song-duration">'+(s.duration?fmt(s.duration):"\u2014")+'</span><div class="song-acts"><button class="song-act-btn" onclick="event.stopPropagation();playIdx('+i+')">&#x25B6;</button><button class="song-act-btn dl" onclick="event.stopPropagation();downloadSong('+i+')">&#x2B07;</button></div></div>'}).join("");c.querySelectorAll(".song-item").forEach(e=>e.addEventListener("click",()=>playIdx(+e.dataset.idx)))}
async function playIdx(i){const s=S.list[i];if(!s)return;const id=s.id;if(S.failed.has(id)){toast("\u8be5\u6b4c\u66f2\u6682\u4e0d\u53ef\u64ad\u653e");if(i<S.list.length-1)playIdx(i+1);return}if(!S.checked.has(id)){toast("\u68c0\u6d4b\u64ad\u653e\u94fe\u63a5\u2026");let rawUrl;try{const d=await api("/api/stream",{source:s._source||"netease",id});rawUrl=d.stream_url}catch(e){S.failed.add(id);renderSearch();toast("\u94fe\u63a5\u83b7\u53d6\u5931\u8d25");if(i<S.list.length-1)playIdx(i+1);return}if(!rawUrl){S.failed.add(id);renderSearch();toast("\u8be5\u6b4c\u66f2\u6682\u4e0d\u53ef\u64ad\u653e");if(i<S.list.length-1)playIdx(i+1);return}const pUrl=proxyUrl(rawUrl);if(!await checkUrl(rawUrl)){S.failed.add(id);renderSearch();toast("\u8be5\u6b4c\u66f2\u94fe\u63a5\u4e0d\u53ef\u7528");if(i<S.list.length-1)playIdx(i+1);return}S.checked.add(id);s._playUrl=pUrl;s._rawUrl=rawUrl}else{s._playUrl=s._playUrl||proxyUrl(s._rawUrl||"")}_playSong(s,i)}
function _playSong(s,i){S.idx=i;updateBar(s);switchView("nowplaying");loadLyric(s);audio.src=s._playUrl;audio.play().catch(e=>{toast("\u64ad\u653e\u5931\u8d25")});S.playing=true;updatePlayBtn();renderSearch();renderPlaylist();if(!S.pl.find(x=>x.id===s.id))S.pl.push(s)}
function updateBar(s){$("pb-title").textContent=s.title||"\u672a\u77e5";$("pb-artist").textContent=s.artist||"\u672a\u77e5";$("pb-thumb").src=s.cover||s.thumbnail||"";$("lyric-song").textContent=s.title||"\u2014";$("lyric-artist").textContent=s.artist||"\u2014";$("lyric-cover").src=s.cover||s.thumbnail||""}
audio.addEventListener("play",()=>{S.playing=true;updatePlayBtn()});
audio.addEventListener("pause",()=>{S.playing=false;updatePlayBtn()});
audio.addEventListener("ended",()=>autoNext());
audio.addEventListener("timeupdate",()=>{const c=audio.currentTime,d=audio.duration;if(!d)return;$("pb-cur").textContent=fmt(c);$("pb-dur").textContent=fmt(d);$("pb-bar-fill").style.width=(c/d*100)+"%";syncLyric(c)});
audio.addEventListener("error",()=>{toast("\u64ad\u653e\u51fa\u9519");if(S.list[S.idx])S.failed.add(S.list[S.idx].id);renderSearch();autoNext()});
function updatePlayBtn(){$("pb-play").textContent=S.playing?"&#x23F8;":"&#x25B6;"}
function togglePlay(){if(S.idx<0)return;if(audio.paused)audio.play();else audio.pause()}
function prevTrack(){if(!S.list.length)return;let i=S.idx-1;if(i<0)i=S.list.length-1;playIdx(i)}
function nextTrack(){autoNext()}
function autoNext(){if(!S.list.length)return;let i;if(S.mode==="one")i=S.idx;else if(S.mode==="random")i=Math.floor(Math.random()*S.list.length);else{i=S.idx+1;if(i>=S.list.length)i=0}playIdx(i)}
function seekTrack(e){if(!audio.duration)return;const r=e.currentTarget.getBoundingClientRect();audio.currentTime=((e.clientX-r.left)/r.width)*audio.duration}
function cycleMode(){const m=["all","one","random"],ic={all:"&#x1F501;",one:"&#x1F502;",random:"&#x1F500;"},x=m.indexOf(S.mode);S.mode=m[(x+1)%m.length];$("pb-mode").textContent=ic[S.mode];toast({all:"\u5217\u8868\u5faa\u73af",one:"\u5355\u66f2\u5faa\u73af",random:"\u968f\u673a\u64ad\u653e"}[S.mode])}
function toggleMute(){S.muted=!S.muted;audio.muted=S.muted;$("pb-vol-btn").textContent=S.muted?"&#x1F507;":"&#x1F50A;"}
function setVolume(e){const r=e.currentTarget.getBoundingClientRect();S.vol=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));audio.volume=S.vol;$("pb-vol-fill").style.width=(S.vol*100)+"%"}
function downloadSong(i){const s=S.list[i];if(!s)return;api("/api/stream",{source:s._source||"netease",id:s.id}).then(d=>{if(d.stream_url){window.open(d.stream_url,"_blank");toast("\u5f00\u59cb\u4e0b\u8f7d")}else toast("\u65e0\u4e0b\u8f7d\u94fe\u63a5")}).catch(()=>toast("\u83b7\u53d6\u94fe\u63a5\u5931\u8d25"))}
function downloadCurrent(){if(S.idx<0)return;downloadSong(S.idx)}
async function loadLyric(s){S.lyric=[];S.lyricIdx=-1;$("lyric-box").innerHTML='<div class="lyric-empty">\u52a0\u8f7d\u6b4c\u8bcd\u2026</div>';try{const d=await api("/api/lyric",{source:s._source||"netease",id:s.id});const raw=d.lyric||"";if(!raw){$("lyric-box").innerHTML='<div class="lyric-empty">\u6682\u65e0\u6b4c\u8bcd</div>';return}const lines=[];raw.split("\n").forEach(line=>{const m=line.match(/^\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\](.*)/);if(m){const t=parseInt(m[1])*60+parseInt(m[2])+(m[3]?parseInt(m[3])/(m[3].length===3?100:1000):0);const txt=m[4].trim();if(txt)lines.push({t,txt})}});lines.sort((a,b)=>a.t-b.t);S.lyric=lines;renderLyric()}catch(e){$("lyric-box").innerHTML='<div class="lyric-empty">\u6b4c\u8bcd\u52a0\u8f7d\u5931\u8d25</div>'}}
function renderLyric(){if(!S.lyric.length){$("lyric-box").innerHTML='<div class="lyric-empty">\u6682\u65e0\u6b4c\u8bcd</div>';return}$("lyric-box").innerHTML=S.lyric.map((l,i)=>'<div class="lyric-line" data-i="'+i+'">'+esc(l.txt)+'</div>').join("")}
function syncLyric(cur){if(!S.lyric.length)return;let idx=S.lyricIdx;for(let i=0;i<S.lyric.length;i++){if(cur>=S.lyric[i].t)idx=i;else break}if(idx!==S.lyricIdx){S.lyricIdx=idx;const box=$("lyric-box");const lines=box.querySelectorAll(".lyric-line");lines.forEach(l=>l.classList.remove("active"));if(lines[idx]){lines[idx].classList.add("active");lines[idx].scrollIntoView({behavior:"smooth",block:"center"})}}}
function renderPlaylist(){const c=$("pl-items");$("pl-count").textContent="("+S.pl.length+")";if(!S.pl.length){c.innerHTML='<div class="pl-empty">\u64ad\u653e\u5217\u8868\u4e3a\u7a7a\uff0c\u53bb\u641c\u7d22\u6b4c\u66f2\u5427 &#x1F3B5;</div>';return}c.innerHTML=S.pl.map((s,i)=>{const ic=i===S.idx;return'<div class="pl-item'+(ic?" playing":"")+'" onclick="playFromPl('+i+')"><span class="pl-idx">'+(ic?"&#x25B6;":i+1)+'</span><span class="pl-title">'+esc(s.title)+'</span><span class="pl-artist">'+esc(s.artist)+'</span><span class="pl-dur">'+(s.duration?fmt(s.duration):"\u2014")+'</span><span class="pl-del" onclick="event.stopPropagation();rmFromPl('+i+')">&#x2715;</span></div>'}).join("")}
function playFromPl(i){const s=S.pl[i];const li=S.list.findIndex(x=>x.id===s.id);if(li>=0){S.idx=li;_playSong(s,li)}else _playSong(s,-1)}
function rmFromPl(i){S.pl.splice(i,1);renderPlaylist()}
function clearPlaylist(){S.pl=[];S.idx=-1;audio.pause();audio.src="";S.playing=false;updatePlayBtn();updateBar({title:"\u672a\u64ad\u653e",artist:"\u2014",cover:""});renderPlaylist()}
async function loadRec(){try{const d=await api("/api/recommendations");const g=d.groups||[];if(!g.length){$("rec-list").innerHTML='<div class="empty-state"><div class="icon">&#x1F3B5;</div>\u6682\u65e0\u63a8\u8350</div>';return}$("rec-list").innerHTML=g.map(gr=>{const dc={netease:"#e74c3c",bilibili:"#fb7299",youtube:"#ff0000",qq:"#12b7f5",kugou:"#2da0dc"};return'<div class="rec-card"><div class="rec-card-title"><span class="src-dot" style="background:'+(dc[gr.source]||"#888")+'"></span>'+esc(gr.source_name||gr.source)+'</div><div class="rec-tracks">'+(gr.tracks||[]).map((t,j)=>'<div class="rec-track" onclick="playRec(\''+esc(gr.source)+'\',\''+esc(t.id)+'\',\''+esc(t.title)+'\',\''+esc(t.artist)+'\',\''+esc(t.cover||"")+'\')"><span class="rec-track-num">'+(j+1)+'</span><img class="rec-thumb" src="'+esc(t.cover||"")+'" onerror="this.style.background=\'var(--bg4)\'"><div class="rec-track-info"><div class="rec-track-title">'+esc(t.title)+'</div><div class="rec-track-artist">'+esc(t.artist)+'</div></div></div>').join("")+"</div></div>"}).join("")}catch(e){$("rec-list").innerHTML='<div class="empty-state"><div class="icon">&#x274C;</div>\u52a0\u8f7d\u5931\u8d25</div>'}}
async function playRec(src,id,title,artist,cover){const s={id,title,artist,cover,_source:src};S.list=[s];S.checked.clear();S.failed.clear();playIdx(0)}
async function init(){try{const d=await api("/api/");$("nav-ver").textContent=d.version||""}catch(e){}loadRec();audio.volume=S.vol}
init();
document.addEventListener("keydown",e=>{if(e.target.tagName==="INPUT")return;const k=e.key;if(k===" "){e.preventDefault();togglePlay()}else if(k==="ArrowLeft"){audio.currentTime=Math.max(0,audio.currentTime-5)}else if(k==="ArrowRight"){audio.currentTime=Math.min(audio.duration,audio.currentTime+5)}else if(k==="ArrowUp"){S.vol=Math.min(1,S.vol+.1);audio.volume=S.vol;$("pb-vol-fill").style.width=(S.vol*100)+"%"}else if(k==="ArrowDown"){S.vol=Math.max(0,S.vol-.1);audio.volume=S.vol;$("pb-vol-fill").style.width=(S.vol*100)+"%"}else if(k==="m"||k==="M")toggleMute();else if(k==="n"||k==="N")nextTrack();else if(k==="p"||k==="P")prevTrack()});
</script>
</body>
</html>"""



if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
