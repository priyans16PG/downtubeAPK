"""Core download engine shared by desktop and Android Kivy UI."""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

import yt_dlp


@dataclass
class FormatOption:
    """Represents one yt-dlp format option."""

    format_id: str
    label: str
    ext: str
    filesize: Optional[int] = None
    is_audio_only: bool = False
    has_audio: bool = False
    quality_key: int = 0


@dataclass
class VideoInfo:
    """Metadata returned from yt-dlp extraction."""

    title: str = ""
    channel: str = ""
    duration: int = 0
    thumbnail_url: str = ""
    url: str = ""
    view_count: int = 0
    upload_date: str = ""
    description: str = ""
    formats: list[FormatOption] = field(default_factory=list)
    is_playlist: bool = False
    playlist_count: int = 0
    playlist_title: str = ""

    @property
    def duration_str(self) -> str:
        if self.duration <= 0:
            return "Live / Unknown"
        h, remainder = divmod(self.duration, 3600)
        m, s = divmod(remainder, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


@dataclass
class DownloadProgress:
    """Progress updates passed from worker thread to UI."""

    status: str = "idle"
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: str = ""
    total: str = ""
    filename: str = ""
    error_message: str = ""


class DownloadEngine:
    """Thread-safe download engine backed by yt-dlp."""

    ANDROID_DOWNLOAD_DIR = "/storage/emulated/0/Download/TubeGrab"

    def __init__(self):
        self._cancel_event = threading.Event()
        self._current_thread: Optional[threading.Thread] = None
        self._is_busy = False
        self._ffmpeg_location = self._resolve_ffmpeg_location()
        self.default_output_dir = self._resolve_default_output_dir()

    @staticmethod
    def _is_android() -> bool:
        return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

    @classmethod
    def _resolve_default_output_dir(cls) -> str:
        candidates = [
            cls.ANDROID_DOWNLOAD_DIR,
            os.path.join(os.path.expanduser("~"), "Downloads", "TubeGrab"),
            os.path.join(os.getcwd(), "downloads"),
        ]

        for path in candidates:
            try:
                os.makedirs(path, exist_ok=True)
                return path
            except OSError:
                continue

        return os.getcwd()

    @staticmethod
    def _resolve_ffmpeg_location() -> Optional[str]:
        # Buildozer-provided ffmpeg should be available from PATH at runtime.
        env_ffmpeg_location = os.environ.get("FFMPEG_LOCATION")
        if env_ffmpeg_location and os.path.exists(env_ffmpeg_location):
            return env_ffmpeg_location
        return None

    @staticmethod
    def _safe_dir_name(name: str) -> str:
        """Sanitize folder name for Windows/Android file systems."""
        if not name:
            return "Playlist"
        cleaned = "".join("_" if ch in '<>:"/\\|?*' else ch for ch in name)
        cleaned = cleaned.strip().rstrip(".")
        return cleaned or "Playlist"

    @staticmethod
    def sizeof_fmt(num: float | int | None) -> str:
        if num is None or num <= 0:
            return "?"
        n = float(num)
        for unit in ("B", "KB", "MB", "GB"):
            if abs(n) < 1024.0:
                return f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    @staticmethod
    def _eta_fmt(seconds: int | float | None) -> str:
        if seconds is None or seconds < 0:
            return "-"
        seconds_int = int(seconds)
        if seconds_int < 60:
            return f"{seconds_int}s"
        minutes, remaining_seconds = divmod(seconds_int, 60)
        return f"{minutes}m {remaining_seconds}s"

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    def fetch_info(self, url: str) -> VideoInfo:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            raise ValueError("Could not fetch video information. Check the URL.")

        is_playlist = info.get("_type") == "playlist" or "entries" in info
        if is_playlist:
            entries = list(info.get("entries", []))
            first = entries[0] if entries else {}
            video_info = VideoInfo(
                title=first.get("title", info.get("title", "Playlist")),
                channel=first.get("channel", first.get("uploader", "")),
                duration=first.get("duration", 0) or 0,
                thumbnail_url=first.get("thumbnail", ""),
                url=url,
                view_count=first.get("view_count", 0) or 0,
                upload_date=first.get("upload_date", ""),
                is_playlist=True,
                playlist_count=len(entries),
                playlist_title=info.get("title", ""),
            )
            video_info.formats = self._parse_formats(first)
            return video_info

        video_info = VideoInfo(
            title=info.get("title", "Unknown"),
            channel=info.get("channel", info.get("uploader", "Unknown")),
            duration=info.get("duration", 0) or 0,
            thumbnail_url=info.get("thumbnail", ""),
            url=url,
            view_count=info.get("view_count", 0) or 0,
            upload_date=info.get("upload_date", ""),
            description=info.get("description", ""),
        )
        video_info.formats = self._parse_formats(info)
        return video_info

    def _parse_formats(self, info: dict) -> list[FormatOption]:
        formats: list[FormatOption] = []
        seen_labels: set[str] = set()
        raw_formats = info.get("formats", [])

        resolution_map: dict[int, FormatOption] = {}
        for item in raw_formats:
            vcodec = item.get("vcodec", "none")
            acodec = item.get("acodec", "none")
            height = item.get("height")
            ext = item.get("ext", "mp4")
            if vcodec != "none" and height:
                label = f"{height}p ({ext.upper()})"
                existing = resolution_map.get(int(height))
                size = item.get("filesize") or item.get("filesize_approx")
                candidate_has_audio = acodec != "none"
                if existing is None:
                    should_replace = True
                elif candidate_has_audio and not existing.has_audio:
                    # Prefer progressive (video+audio) variants at the same resolution.
                    should_replace = True
                elif candidate_has_audio == existing.has_audio and (size or 0) > (existing.filesize or 0):
                    should_replace = True
                else:
                    should_replace = False

                if should_replace:
                    resolution_map[int(height)] = FormatOption(
                        format_id=item.get("format_id", ""),
                        label=label,
                        ext=ext,
                        filesize=size,
                        has_audio=candidate_has_audio,
                        quality_key=int(height),
                    )

        for height in sorted(resolution_map.keys(), reverse=True):
            opt = resolution_map[height]
            if opt.label not in seen_labels:
                seen_labels.add(opt.label)
                formats.append(opt)

        audio_map: dict[int, FormatOption] = {}
        for item in raw_formats:
            vcodec = item.get("vcodec", "none")
            acodec = item.get("acodec", "none")
            abr = int(item.get("abr", 0) or 0)
            ext = item.get("ext", "m4a")
            if vcodec == "none" and acodec != "none" and abr > 0:
                label = f"Audio {abr}kbps ({ext.upper()})"
                existing = audio_map.get(abr)
                size = item.get("filesize") or item.get("filesize_approx")
                if existing is None or (size or 0) > (existing.filesize or 0):
                    audio_map[abr] = FormatOption(
                        format_id=item.get("format_id", ""),
                        label=label,
                        ext=ext,
                        filesize=size,
                        is_audio_only=True,
                        quality_key=abr,
                    )

        for abr in sorted(audio_map.keys(), reverse=True):
            opt = audio_map[abr]
            if opt.label not in seen_labels:
                seen_labels.add(opt.label)
                formats.append(opt)

        best_options = [
            FormatOption(
                format_id="bestvideo+bestaudio/best",
                label="Best Quality (Video+Audio)",
                ext="mp4",
                quality_key=99999,
            ),
            FormatOption(
                format_id="bestaudio/best",
                label="Best Audio Only (MP3)",
                ext="mp3",
                is_audio_only=True,
                quality_key=99998,
            ),
        ]
        return best_options + formats

    def download(
        self,
        url: str,
        format_option: FormatOption,
        output_dir: str,
        download_full_playlist: bool = False,
        playlist_title: str = "",
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> None:
        if self._is_busy:
            raise RuntimeError("A download is already in progress.")

        self._cancel_event.clear()
        self._is_busy = True

        def _run_download() -> None:
            try:
                self._do_download(
                    url,
                    format_option,
                    output_dir,
                    download_full_playlist,
                    playlist_title,
                    progress_callback,
                )
            finally:
                self._is_busy = False

        self._current_thread = threading.Thread(target=_run_download, daemon=True)
        self._current_thread.start()

    def _do_download(
        self,
        url: str,
        fmt: FormatOption,
        output_dir: str,
        download_full_playlist: bool,
        playlist_title: str,
        callback: Callable[[DownloadProgress], None] | None,
    ) -> None:
        progress = DownloadProgress(status="downloading")

        def _hook(data: dict) -> None:
            if self._cancel_event.is_set():
                raise yt_dlp.utils.DownloadCancelled("Cancelled by user")

            status = data.get("status", "")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes", 0)
                speed = data.get("speed") or 0
                eta = data.get("eta")

                progress.status = "downloading"
                progress.percent = (downloaded / total * 100) if total else 0
                progress.speed = self.sizeof_fmt(speed) + "/s" if speed else ""
                progress.eta = self._eta_fmt(eta)
                progress.downloaded = self.sizeof_fmt(downloaded)
                progress.total = self.sizeof_fmt(total)
                progress.filename = data.get("filename", "")
            elif status == "finished":
                progress.status = "processing"
                progress.percent = 100.0
                progress.speed = ""
                progress.eta = ""
                progress.filename = data.get("filename", "")

            if callback:
                callback(progress)

        os.makedirs(output_dir, exist_ok=True)
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        ydl_opts: dict = {
            "outtmpl": outtmpl,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "prefer_ffmpeg": True,
            "continuedl": True,
            "nooverwrites": True,
            # When False, yt-dlp downloads only the first item from a playlist URL.
            "noplaylist": not download_full_playlist,
        }

        if download_full_playlist:
            # Save full playlists into a dedicated folder named after playlist title.
            folder_name = self._safe_dir_name(playlist_title)
            playlist_dir = os.path.join(output_dir, folder_name)
            os.makedirs(playlist_dir, exist_ok=True)
            ydl_opts["outtmpl"] = os.path.join(playlist_dir, "%(playlist_index)03d - %(title)s.%(ext)s")

        if self._ffmpeg_location:
            ydl_opts["ffmpeg_location"] = self._ffmpeg_location

        has_ffmpeg = bool(self._ffmpeg_location or shutil.which("ffmpeg"))

        if fmt.format_id == "bestaudio/best" or fmt.is_audio_only:
            # Keep the exact selected audio stream for audio-only formats.
            selected_audio_format = fmt.format_id or "bestaudio/best"
            ydl_opts["format"] = selected_audio_format

            # Convert to MP3 only for the explicit "Best Audio Only (MP3)" option.
            if has_ffmpeg and fmt.format_id == "bestaudio/best":
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
        else:
            if fmt.format_id.startswith("best"):
                ydl_opts["format"] = "bestvideo+bestaudio/best" if has_ffmpeg else "best[ext=mp4]/best"
            elif has_ffmpeg:
                # Merge selected video stream with best audio when ffmpeg is available.
                if fmt.has_audio:
                    ydl_opts["format"] = fmt.format_id
                else:
                    ydl_opts["format"] = f"{fmt.format_id}+bestaudio/best"
                    ydl_opts["merge_output_format"] = "mp4"
            else:
                # No ffmpeg: prefer progressive streams (video+audio in one file) to avoid silent video.
                # Never force video-only ids first here; choose audio+video streams to avoid silent files.
                target_height = max(int(fmt.quality_key or 0), 0)
                if target_height > 0:
                    progressive_fallback = (
                        f"best[height<={target_height}][vcodec!=none][acodec!=none][ext=mp4]/"
                        f"best[height<={target_height}][vcodec!=none][acodec!=none]/"
                        "best[ext=mp4]/best"
                    )
                    if fmt.has_audio:
                        ydl_opts["format"] = f"{fmt.format_id}/{progressive_fallback}"
                    else:
                        ydl_opts["format"] = progressive_fallback
                else:
                    if fmt.has_audio:
                        ydl_opts["format"] = f"{fmt.format_id}/best[ext=mp4]/best"
                    else:
                        ydl_opts["format"] = "best[ext=mp4]/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not self._cancel_event.is_set():
                progress.status = "finished"
                progress.percent = 100.0
                if callback:
                    callback(progress)
        except yt_dlp.utils.DownloadCancelled:
            progress.status = "cancelled"
            if callback:
                callback(progress)
        except Exception as exc:
            progress.status = "error"
            progress.error_message = str(exc)
            if callback:
                callback(progress)

    def cancel(self) -> None:
        self._cancel_event.set()
