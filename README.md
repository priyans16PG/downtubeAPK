# TubeGrab - Advanced YouTube Downloader

TubeGrab is a Python-based YouTube downloader with a Kivy UI, designed to run on desktop and be packaged into an Android APK with Buildozer.

## Features

- Fetch YouTube metadata (title, channel, duration)
- Select available video/audio formats from `yt-dlp`
- Full playlist download mode (or first-video-only mode)
- Download in a background thread to keep UI responsive
- Real-time progress updates (percent, size, speed, ETA)
- Android-friendly default output directory:
	`/storage/emulated/0/Download/TubeGrab`

## Tech Stack

- Kivy (UI)
- yt-dlp (download engine)
- Requests
- Pillow

## Project Structure

```text
.
|- main.py            # App entrypoint (runs Kivy app)
|- app.py             # Kivy UI (mobile-responsive layout)
|- downloader.py      # Core yt-dlp engine + progress callbacks
|- buildozer.spec     # Android build configuration
|- requirements.txt   # Python dependencies
|- styles.py          # Legacy file (currently unused)
`- README.md
```

## Run on Desktop

### Prerequisites

- Python 3.10+ recommended
- ffmpeg installed on system PATH (recommended for merge/audio conversion)

### Install and Run

```bash
pip install -r requirements.txt
python main.py
```

## Build Android APK (Buildozer)

Buildozer is Linux-first. On Windows, use WSL2 or Linux for reliable builds.

### 1. Install Build Tools (Linux/WSL)

- Python, pip, git
- Buildozer and Cython
- Java JDK + Android SDK/NDK prerequisites

```bash
pip install --upgrade pip
pip install buildozer cython
```

### 2. Verify `buildozer.spec`

This repository already includes `buildozer.spec` configured for:

- `entrypoint = main.py`
- `requirements = python3,kivy,yt-dlp,requests,pillow,ffmpeg`
- Android permissions for internet and storage access

### 3. Build Debug APK

```bash
buildozer android debug
```

Generated APKs are placed in `bin/`.

### 4. Deploy to Device (optional)

```bash
buildozer android deploy run
```

## Notes

- No Windows-only binaries are bundled.
- `downloader.py` uses ffmpeg from environment/PATH (or `FFMPEG_LOCATION` if provided).
- If Android storage permissions are restricted on newer Android versions, you may need to adjust `buildozer.spec` and/or app storage strategy.

## Version Updates

- The app UI displays `v<version>` by reading `buildozer.spec` (`version = ...`).
- For every new release, bump the value in `buildozer.spec` so the version shown in the app updates automatically.

## License

MIT
