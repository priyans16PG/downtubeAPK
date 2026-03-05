[app]

title = TubeGrab
package.name = tubegrab
package.domain = org.tubegrab

source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,txt,md
source.exclude_dirs = __pycache__,.git,.venv,venv,build,bin

version = 1.0.0

# main.py starts TubeGrabApp().run()
entrypoint = main.py

requirements = python3,kivy,yt_dlp,requests,pillow

orientation = portrait
fullscreen = 0

# Android API levels
android.minapi = 24
android.api = 34
android.ndk_api = 24

# Target common device architectures
android.archs = arm64-v8a, armeabi-v7a

# Network + external storage access for downloads
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# Keep app alive while download threads run
android.wakelock = True

# If your app icon/presplash assets exist, uncomment and set paths
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png

[buildozer]

log_level = 2
warn_on_root = 1

# Build outputs
bin_dir = ./bin
build_dir = ./.buildozer
