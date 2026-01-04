# YouTube Music Download API

A simple Express.js API that downloads audio from YouTube videos/YouTube music and converts them to MP3 format.

## Features

- Download audio from YouTube videos in MP3 format
- Get video information without downloading
- Automatic cleanup of old downloaded files
- CORS enabled for cross-origin requests
- Stream files directly to clients
- High-quality audio extraction

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- `youtube-dl` or `yt-dlp` installed on your system

## Installation

1. Clone the repository or copy the code to your project directory

2. Install dependencies:
```bash
npm install express youtube-dl-exec cors
```

3. Make sure `youtube-dl` or `yt-dlp` is installed on your system:

**Using yt-dlp (recommended):**
```bash
# macOS
brew install yt-dlp

# Linux
sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

# Windows
# Download from https://github.com/yt-dlp/yt-dlp/releases
```

**Or using youtube-dl:**
```bash
# macOS
brew install youtube-dl

# Linux
sudo curl -L https://yt-dl.org/downloads/latest/youtube-dl -o /usr/local/bin/youtube-dl
sudo chmod a+rx /usr/local/bin/youtube-dl

# Windows
# Download from https://youtube-dl.org/
```

4. Ensure FFmpeg is installed (required for audio conversion):
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Usage

### Starting the Server

```bash
node app.js
```

The server will start on port 3000 by default. You can change this by setting the `PORT` environment variable:

```bash
PORT=8080 node app.js
```

### API Endpoints

#### 1. Download Audio

**Endpoint:** `GET /download`

**Query Parameters:**
- `url` (required): YouTube video URL

**Example Request:**
```bash
curl "http://localhost:3000/download?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o audio.mp3
```

**Response:**
- Returns an MP3 file stream
- Custom headers include:
  - `X-Video-Title`: Video title
  - `X-Video-Duration`: Duration in seconds
  - `X-Video-Uploader`: Channel name

#### 2. Get Video Information

**Endpoint:** `GET /info`

**Query Parameters:**
- `url` (required): YouTube video URL

**Example Request:**
```bash
curl "http://localhost:3000/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Example Response:**
```json
{
  "title": "Video Title",
  "duration": 213,
  "uploader": "Channel Name",
  "thumbnail": "https://...",
  "description": "Video description..."
}
```

#### 3. Health Check

**Endpoint:** `GET /health`

**Example Request:**
```bash
curl "http://localhost:3000/health"
```

**Example Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-01-04T12:00:00.000Z"
}
```

## Features Details

### Automatic Cleanup

The API automatically cleans up downloaded files:
- Files older than 1 hour are deleted
- Cleanup runs every 30 minutes
- Files are also deleted immediately after streaming completes

### URL Validation

The API accepts URLs from:
- `youtube.com`
- `youtu.be`
- `music.youtube.com`

### Error Handling

The API provides specific error messages for common issues:
- Invalid URLs
- Unavailable or private videos
- Video not found
- Download failures

## Project Structure

```
.
├── app.js           # Main API server
├── downloads/          # Temporary storage for downloads (auto-created)
├── package.json
└── README.md
```

## Environment Variables

- `PORT`: Server port (default: 3000)

## Security Considerations

- The API validates YouTube URLs before processing
- Downloaded files are automatically cleaned up
- Filenames are sanitized to prevent directory traversal
- CORS is enabled (configure as needed for production)

## Limitations

- Only supports YouTube URLs
- Temporary files are stored on the server
- No authentication/rate limiting implemented
- Designed for single-server deployment

## Troubleshooting

**"youtube-dl not found" error:**
- Make sure `youtube-dl` or `yt-dlp` is installed and in your PATH

**"FFmpeg not found" error:**
- Install FFmpeg as described in the installation section

**Download fails:**
- Check if the video is available and not region-blocked
- Try updating `youtube-dl`/`yt-dlp` to the latest version
- Some videos may be protected and cannot be downloaded

## License

This project is provided as-is for educational purposes. Please respect YouTube's Terms of Service and copyright laws when using this API.

## Disclaimer

This tool is for personal use only. Downloading copyrighted content without permission may violate YouTube's Terms of Service and copyright laws. Users are responsible for ensuring their use complies with all applicable laws and terms of service.