# TubeGrab — Advanced YouTube Downloader

A premium, feature-rich YouTube video downloader built with Python. Featuring a sleek dark-themed GUI powered by CustomTkinter and the robust yt-dlp backend.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Features

- **🔍 Smart Fetch** — Paste a URL and instantly preview title, thumbnail, duration, and channel
- **📊 Quality Selector** — Choose from all available formats (4K, 1080p, 720p, etc.)
- **🎵 Audio-Only Mode** — Download as MP3 with best quality
- **📃 Playlist Support** — Detect and download entire playlists
- **📈 Real-Time Progress** — Animated progress bar with speed, ETA, and size info
- **📋 Download Queue** — Queue multiple URLs for batch downloading  
- **📜 Download History** — Track all past downloads with status indicators
- **🌗 Dark/Light Theme** — Toggle between dark and light modes
- **📂 Custom Save Location** — Browse and choose your output folder

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- [FFmpeg](https://ffmpeg.org/download.html) installed and on PATH (required for merging video+audio)

### Installation

```bash
# Clone the repo
cd "yt downloader"

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## 🛠 Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend   | yt-dlp    |
| GUI       | CustomTkinter |
| Imaging   | Pillow    |
| HTTP      | Requests  |

## 📁 Project Structure

```
├── main.py           # Entry point
├── app.py            # GUI application
├── downloader.py     # Core download engine
├── styles.py         # Theme & styling constants
├── requirements.txt  # Dependencies
└── README.md         # This file
```

## 📝 License

MIT License — feel free to use and modify.
