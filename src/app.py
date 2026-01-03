from fastapi import FastAPI
import os
import uuid
import subprocess
from fastapi.responses import FileResponse
from urllib.parse import quote
from fastapi import HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pytubefix import YouTube
from pytubefix.cli import on_progress
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


def convert_to_mp3(input_file: str, output_file: str, bitrate: str = "192k"):
    """Convert audio file to MP3 using ffmpeg"""
    try:
        command = [
            'ffmpeg',
            '-i', input_file,
            '-vn',  # No video
            '-acodec', 'libmp3lame',
            '-b:a', bitrate,
            '-y',  # Overwrite output file if it exists
            output_file
        ]
        
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion error: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        raise Exception("FFmpeg is not installed. Please install ffmpeg to convert audio files.")


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


@app.get("/download", tags=["Music"])
async def download(url: str, background_tasks: BackgroundTasks):
    unique_id = str(uuid.uuid4())[:8]
    temp_file = None
    mp3_filename = None
    
    try:
        # Initialize YouTube object with progress callback
        print(f"Fetching video info for: {url}")
        yt = YouTube(url, on_progress_callback=on_progress)
        
        # Get the best audio stream
        audio_stream = yt.streams.get_audio_only()
        
        if not audio_stream:
            raise HTTPException(status_code=404, detail="No audio stream found")
        
        # Download the audio file
        print(f"Downloading: {yt.title}")
        print(f"Audio format: {audio_stream.subtype}")
        
        temp_file = audio_stream.download(
            output_path=DOWNLOAD_DIR,
            filename=f"{unique_id}.{audio_stream.subtype}"
        )
        
        # Convert to MP3
        mp3_filename = os.path.join(DOWNLOAD_DIR, f"{unique_id}.mp3")
        
        if audio_stream.subtype.lower() in ['mp3']:
            # If already MP3, just rename
            print("File is already MP3, skipping conversion")
            os.rename(temp_file, mp3_filename)
        else:
            # Convert to MP3 using ffmpeg
            print(f"Converting {audio_stream.subtype} to MP3...")
            success = convert_to_mp3(temp_file, mp3_filename)
            
            if not success:
                raise HTTPException(status_code=500, detail="Audio conversion failed")
            
            # Remove the original temp file after conversion
            _safe_remove(temp_file)
        
        if not os.path.exists(mp3_filename):
            raise HTTPException(status_code=500, detail="File conversion failed")
        
        # Clean title for download filename and make headers ASCII-safe
        title = yt.title or 'audio'
        safe_title = "".join((c if (ord(c) < 128 and (c.isalnum() or c in (' ', '-', '_'))) else '_') for c in title).rstrip()
        safe_title = safe_title.replace(' ', '_') or 'audio'

        # HTTP headers must be encodable in latin-1; percent-encode non-ASCII values
        encoded_title = quote(title, safe='')
        
        file_size = os.path.getsize(mp3_filename)
        duration = yt.length or 0
        uploader = yt.author or 'Unknown'
        encoded_uploader = quote(uploader, safe='')
        
        print(f"Download complete: {safe_title}.mp3 ({file_size} bytes)")
        
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
        # Clean up any temporary files on error
        if temp_file and os.path.exists(temp_file):
            _safe_remove(temp_file)
        if mp3_filename and os.path.exists(mp3_filename):
            _safe_remove(mp3_filename)
        
        error_msg = str(e)
        print(f"Error: {error_msg}")
        
        if "unavailable" in error_msg.lower() or "private" in error_msg.lower():
            raise HTTPException(
                status_code=404,
                detail="Video is unavailable or private"
            )
        elif "age" in error_msg.lower():
            raise HTTPException(
                status_code=403,
                detail="Video is age-restricted"
            )
        elif "ffmpeg" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="FFmpeg is not installed. Please install ffmpeg."
            )
        else:
            raise HTTPException(status_code=500, detail=f"Download failed: {error_msg}")