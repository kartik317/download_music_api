from fastapi import FastAPI
import os
import uuid
import time
import random
import subprocess
from fastapi.responses import FileResponse
from urllib.parse import quote, urlparse
from fastapi import HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import requests

# Create a directory for downloads if it doesn't exist
DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="Music API",
    description="API for downloading music tracks",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (or specify: ["http://localhost:5173", "http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def _get_user_agents():
    """Return a list of common user agents to rotate through"""
    return [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    ]

def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    parsed = urlparse(url)
    if 'youtube.com' in parsed.netloc:
        return parsed.query.split('v=')[1].split('&')[0] if 'v=' in parsed.query else None
    elif 'youtu.be' in parsed.netloc:
        return parsed.path.lstrip('/')
    return None

def _download_via_invidious(video_id: str, download_dir: str, unique_id: str) -> str:
    """Try to download using Invidious API as fallback"""
    invidious_instances = [
        'https://invidious.jing.rocks',
        'https://invidious.io',
        'https://iv.ggtyler.dev',
    ]
    
    for instance in invidious_instances:
        try:
            # Get video info from Invidious
            info_url = f"{instance}/api/v1/videos/{video_id}"
            response = requests.get(info_url, timeout=10)
            if response.status_code != 200:
                continue
                
            video_info = response.json()
            # Use the highest quality audio-only format
            formats = video_info.get('formatStreams', [])
            
            for fmt in formats:
                if 'audio' in fmt.get('type', '').lower():
                    audio_url = f"{instance}{fmt['url']}"
                    mp3_path = os.path.join(download_dir, f'{unique_id}.mp3')
                    
                    # Download audio
                    audio_response = requests.get(audio_url, timeout=30, stream=True)
                    with open(mp3_path, 'wb') as f:
                        for chunk in audio_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    return mp3_path
        except Exception:
            continue
    
    return None

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

@app.get("/download", tags=["Music"])
async def download(url: str, background_tasks: BackgroundTasks):
    unique_id = str(uuid.uuid4())[:8]
    video_id = _extract_video_id(url)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{unique_id}.%(ext)s'),
        'quiet': True,
        'socket_timeout': 30,
        'nocheckcertificate': True,
        'no_warnings': True,
        'skip_unavailable_fragments': True,
        # Browser simulation headers
        'user_agent': random.choice(_get_user_agents()),
        'http_headers': {
            'User-Agent': random.choice(_get_user_agents()),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.youtube.com/',
        },
        # YouTube specific options
        'youtube_include_dash_manifest': False,
        'extract_flat': False,
    }
    
    max_retries = 2
    mp3_filename = None
    info_dict = None
    
    # Try yt-dlp first
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
            
            # Find the downloaded file
            original_filename = ydl.prepare_filename(info_dict)
            mp3_filename = original_filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            # If the file doesn't exist with those extensions, find it
            if not os.path.exists(mp3_filename):
                # Get all files starting with the unique_id
                for file in os.listdir(DOWNLOAD_DIR):
                    if file.startswith(unique_id):
                        mp3_filename = os.path.join(DOWNLOAD_DIR, file)
                        break
            
            if os.path.exists(mp3_filename):
                break
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3 + random.uniform(0, 2)
                time.sleep(wait_time)
                continue
            # yt-dlp failed, try Invidious fallback
            if video_id:
                mp3_filename = _download_via_invidious(video_id, DOWNLOAD_DIR, unique_id)
                if mp3_filename:
                    info_dict = {'title': 'audio', 'duration': 0, 'uploader': 'Unknown'}
                    break
            raise HTTPException(status_code=500, detail=f"Download failed: {error_msg}")
    
    if not mp3_filename or not os.path.exists(mp3_filename):
        raise HTTPException(status_code=500, detail="File conversion failed")
    
    # Clean title for download filename and make headers ASCII-safe
    title = info_dict.get('title', 'audio') if info_dict else 'audio'
    safe_title = "".join((c if (ord(c) < 128 and (c.isalnum() or c in (' ', '-', '_'))) else '_') for c in title).rstrip()
    safe_title = safe_title.replace(' ', '_') or 'audio'

    # HTTP headers must be encodable in latin-1; percent-encode non-ASCII values so headers stay ASCII
    encoded_title = quote(title, safe='')
    
    file_size = os.path.getsize(mp3_filename)
    duration = info_dict.get('duration', 0) if info_dict else 0
    uploader = info_dict.get('uploader', 'Unknown') if info_dict else 'Unknown'
    encoded_uploader = quote(uploader, safe='')
    
    # Schedule file removal after response is completed
    background_tasks.add_task(_safe_remove, mp3_filename)

    return FileResponse(
        path=mp3_filename,
        filename=f"{safe_title}.mp3",
        media_type='audio/mpeg',
        headers={
            "Content-Length": str(file_size),
            "X-Video-Title": encoded_title,
            "X-Video-Duration": str(duration),
            "X-Video-Uploader": encoded_uploader
        }
    )

import threading
import requests
import time

def keep_alive():
    while True:
        time.sleep(300)  # 5 minutes
        try:
            requests.get("https://yourapp.onrender.com")
        except:
            pass

# Start in a separate thread
threading.Thread(target=keep_alive, daemon=True).start()