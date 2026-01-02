from fastapi import FastAPI
import os
import uuid
import base64
from fastapi.responses import FileResponse
from urllib.parse import quote
from fastapi import HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


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
    allow_origins=["*"],
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


def create_temp_cookies_file(unique_id: str) -> str:
    """Create a temporary cookies file from base64 environment variable"""
    cookies_base64 = os.getenv('COOKIES_BASE64')
    
    if not cookies_base64:
        print("Warning: COOKIES_BASE64 environment variable not set")
        return None
    
    try:
        # Decode base64 string to get cookies content
        cookies_content = base64.b64decode(cookies_base64).decode('utf-8')
        
        # Create a temporary cookies file
        temp_cookie_file = os.path.join(DOWNLOAD_DIR, f'cookies_{unique_id}.txt')
        
        with open(temp_cookie_file, 'w') as f:
            f.write(cookies_content)
        
        print(f"Created temporary cookies file: {temp_cookie_file}")
        return temp_cookie_file
        
    except Exception as e:
        print(f"Error creating cookies file: {str(e)}")
        return None


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


@app.get("/download", tags=["Music"])
async def download(url: str, background_tasks: BackgroundTasks):
    unique_id = str(uuid.uuid4())[:8]
    
    # Create temporary cookies file
    temp_cookie_file = create_temp_cookies_file(unique_id)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{unique_id}.%(ext)s'),
        'quiet': True,
        # YouTube-specific configurations
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['configs'],
            }
        },
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
    }
    
    # Add cookies to options if available
    if temp_cookie_file:
        ydl_opts['cookiefile'] = temp_cookie_file
        print(f"Using cookies file: {temp_cookie_file}")
    else:
        print("No cookies file available, proceeding without cookies")
    
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
                    if file.startswith(unique_id) and not file.endswith('_cookies.txt'):
                        mp3_filename = os.path.join(DOWNLOAD_DIR, file)
                        break
            
            if not os.path.exists(mp3_filename):
                raise HTTPException(status_code=500, detail="File conversion failed")
            
            # Clean title for download filename and make headers ASCII-safe
            title = info_dict.get('title', 'audio')
            safe_title = "".join((c if (ord(c) < 128 and (c.isalnum() or c in (' ', '-', '_'))) else '_') for c in title).rstrip()
            safe_title = safe_title.replace(' ', '_') or 'audio'

            # HTTP headers must be encodable in latin-1; percent-encode non-ASCII values
            encoded_title = quote(title, safe='')
            
            file_size = os.path.getsize(mp3_filename)
            duration = info_dict.get('duration', 0)
            uploader = info_dict.get('uploader', 'Unknown')
            encoded_uploader = quote(uploader, safe='')
            
            # Schedule file removal after response is completed
            background_tasks.add_task(_safe_remove, mp3_filename)
            
            # Also remove temporary cookies file if it exists
            if temp_cookie_file:
                background_tasks.add_task(_safe_remove, temp_cookie_file)

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
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg:
            raise HTTPException(
                status_code=403,
                detail="YouTube is blocking requests. Cookies may have expired. Please update COOKIES_BASE64 environment variable."
            )
        else:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")