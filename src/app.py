from fastapi import FastAPI
import os
import uuid
from fastapi.responses import FileResponse
from urllib.parse import quote
from fastapi import HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

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

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}

@app.get("/download", tags=["Music"])
async def download(url: str, background_tasks: BackgroundTasks):
    unique_id = str(uuid.uuid4())[:8]
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        # Use only unique ID, add title later
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{unique_id}.%(ext)s'),
        'quiet': True,
    }
    
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
            
            if not os.path.exists(mp3_filename):
                raise HTTPException(status_code=500, detail="File conversion failed")
            
            # Clean title for download filename and make headers ASCII-safe
            title = info_dict.get('title', 'audio')
            # Create an ASCII-only filename: keep only ASCII alnum, '-', '_' and replace others with '_'
            safe_title = "".join((c if (ord(c) < 128 and (c.isalnum() or c in (' ', '-', '_'))) else '_') for c in title).rstrip()
            safe_title = safe_title.replace(' ', '_') or 'audio'

            # HTTP headers must be encodable in latin-1; percent-encode non-ASCII values so headers stay ASCII
            encoded_title = quote(title, safe='')
            
            file_size = os.path.getsize(mp3_filename)
            duration = info_dict.get('duration', 0)
            uploader = info_dict.get('uploader', 'Unknown')
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
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")