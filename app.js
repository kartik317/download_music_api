const express = require('express');
const youtubedl = require('youtube-dl-exec');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Create downloads directory
const downloadDir = './downloads';
if (!fs.existsSync(downloadDir)) {
  fs.mkdirSync(downloadDir, { recursive: true });
}

// Clean up old files (older than 1 hour)
function cleanupOldFiles() {
  const files = fs.readdirSync(downloadDir);
  const now = Date.now();
  const oneHour = 60 * 60 * 1000;

  files.forEach(file => {
    const filePath = path.join(downloadDir, file);
    const stats = fs.statSync(filePath);
    if (now - stats.mtimeMs > oneHour) {
      fs.unlinkSync(filePath);
      console.log(`Cleaned up old file: ${file}`);
    }
  });
}

// Run cleanup every 30 minutes
setInterval(cleanupOldFiles, 30 * 60 * 1000);

// Download endpoint
app.get('/download', async (req, res) => {
  const { url } = req.query;

  if (!url) {
    return res.status(400).json({ error: 'URL parameter is required' });
  }

  // Validate YouTube URL
  const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)\/.+/;
  if (!youtubeRegex.test(url)) {
    return res.status(400).json({ error: 'Invalid YouTube URL' });
  }

  try {
    console.log('Fetching video info...');

    // Get video info first
    const info = await youtubedl(url, {
      dumpSingleJson: true,
      noCheckCertificates: true,
      noWarnings: true,
      preferFreeFormats: true,
      skipDownload: true,
    });

    const videoTitle = info.title || 'audio';
    const duration = info.duration || 0;
    const uploader = info.uploader || 'Unknown';
    
    // Sanitize filename
    const safeTitle = videoTitle
      .replace(/[^a-zA-Z0-9\s-]/g, '')
      .replace(/\s+/g, '_')
      .substring(0, 100);
    
    const filename = `${Date.now()}_${safeTitle}.mp3`;
    const outputPath = path.join(downloadDir, filename);

    console.log(`Downloading: ${videoTitle}`);

    // Download and convert to MP3
    await youtubedl(url, {
      extractAudio: true,
      audioFormat: 'mp3',
      audioQuality: 0, // Best quality
      output: outputPath,
      noCheckCertificates: true,
      noWarnings: true,
      preferFreeFormats: true,
      addMetadata: true,
    });

    console.log('Download completed, streaming file...');

    // Check if file exists
    if (!fs.existsSync(outputPath)) {
      return res.status(500).json({ error: 'File download failed' });
    }

    const fileStats = fs.statSync(outputPath);

    // Set headers with metadata
    res.set({
      'Content-Type': 'audio/mpeg',
      'Content-Length': fileStats.size,
      'Content-Disposition': `attachment; filename="${encodeURIComponent(filename)}"`,
      'X-Video-Title': encodeURIComponent(videoTitle),
      'X-Video-Duration': duration.toString(),
      'X-Video-Uploader': encodeURIComponent(uploader),
    });

    // Stream the file
    const fileStream = fs.createReadStream(outputPath);
    
    fileStream.on('end', () => {
      // Delete file after streaming
      setTimeout(() => {
        if (fs.existsSync(outputPath)) {
          fs.unlinkSync(outputPath);
          console.log(`Cleaned up: ${filename}`);
        }
      }, 5000);
    });

    fileStream.on('error', (err) => {
      console.error('Stream error:', err);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Error streaming file' });
      }
    });

    fileStream.pipe(res);

  } catch (error) {
    console.error('Download error:', error);
    
    let errorMessage = 'Failed to download audio';
    if (error.message?.includes('Video unavailable')) {
      errorMessage = 'Video is unavailable or private';
    } else if (error.message?.includes('not found')) {
      errorMessage = 'Video not found';
    }

    if (!res.headersSent) {
      res.status(500).json({ error: errorMessage, details: error.message });
    }
  }
});

// Get video info endpoint (without downloading)
app.get('/info', async (req, res) => {
  const { url } = req.query;

  if (!url) {
    return res.status(400).json({ error: 'URL parameter is required' });
  }

  try {
    const info = await youtubedl(url, {
      dumpSingleJson: true,
      noCheckCertificates: true,
      noWarnings: true,
      preferFreeFormats: true,
      skipDownload: true,
    });

    res.json({
      title: info.title,
      duration: info.duration,
      uploader: info.uploader,
      thumbnail: info.thumbnail,
      description: info.description,
    });
  } catch (error) {
    console.error('Info fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch video info' });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`YouTube Audio Download API running on port ${PORT}`);
  console.log(`Download endpoint: http://localhost:${PORT}/download?url=YOUR_YOUTUBE_URL`);
});