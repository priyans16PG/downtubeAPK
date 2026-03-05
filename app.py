"""TubeGrab mobile-compatible app built with Kivy."""

from __future__ import annotations

import threading
from typing import Optional

from kivy.app import App as KivyApp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from downloader import DownloadEngine, DownloadProgress, FormatOption, VideoInfo


class TubeGrabApp(KivyApp):
    """Kivy UI for desktop and Android builds."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = DownloadEngine()
        self.video_info: Optional[VideoInfo] = None
        self.selected_format: Optional[FormatOption] = None
        self.fetch_button: Optional[Button] = None
        self.download_button: Optional[Button] = None
        self.cancel_button: Optional[Button] = None
        self.url_input: Optional[TextInput] = None
        self.video_title_label: Optional[Label] = None
        self.video_meta_label: Optional[Label] = None
        self.status_label: Optional[Label] = None
        self.progress_text: Optional[Label] = None
        self.progress_bar: Optional[ProgressBar] = None
        self.formats_box: Optional[BoxLayout] = None

    def build(self):
        self.title = "TubeGrab"
        if Window is not None:
            Window.minimum_width = dp(360)
            Window.minimum_height = dp(640)

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        scroll = ScrollView(size_hint=(1, 1))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
            padding=(0, dp(6)),
        )
        content.bind(minimum_height=content.setter("height"))

        title = Label(
            text="TubeGrab - Advanced YouTube Downloader",
            size_hint_y=None,
            height=dp(40),
            halign="left",
            valign="middle",
            bold=True,
        )
        title.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(title)

        self.url_input = TextInput(
            hint_text="Paste YouTube URL",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )
        content.add_widget(self.url_input)

        button_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        self.fetch_button = Button(text="Fetch", size_hint_x=0.5)
        self.fetch_button.bind(on_release=self.on_fetch_pressed)
        button_row.add_widget(self.fetch_button)

        self.download_button = Button(text="Download", size_hint_x=0.5, disabled=True)
        self.download_button.bind(on_release=self.on_download_pressed)
        button_row.add_widget(self.download_button)
        content.add_widget(button_row)

        self.cancel_button = Button(text="Cancel", size_hint_y=None, height=dp(42), disabled=True)
        self.cancel_button.bind(on_release=self.on_cancel_pressed)
        content.add_widget(self.cancel_button)

        self.video_title_label = Label(
            text="No video loaded.",
            size_hint_y=None,
            height=dp(44),
            halign="left",
            valign="top",
        )
        self.video_title_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(self.video_title_label)

        self.video_meta_label = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
        )
        self.video_meta_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(self.video_meta_label)

        formats_header = Label(
            text="Formats",
            size_hint_y=None,
            height=dp(26),
            halign="left",
            valign="middle",
            bold=True,
        )
        formats_header.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(formats_header)

        self.formats_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.formats_box.bind(minimum_height=self.formats_box.setter("height"))
        content.add_widget(self.formats_box)

        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(18))
        content.add_widget(self.progress_bar)

        self.progress_text = Label(
            text="Progress: 0%",
            size_hint_y=None,
            height=dp(24),
            halign="left",
            valign="middle",
        )
        self.progress_text.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(self.progress_text)

        self.status_label = Label(
            text=f"Save path: {self.engine.default_output_dir}",
            size_hint_y=None,
            height=dp(56),
            halign="left",
            valign="top",
        )
        self.status_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(self.status_label)

        scroll.add_widget(content)
        root.add_widget(scroll)
        return root

    def on_fetch_pressed(self, _instance):
        url = (self.url_input.text or "").strip() if self.url_input else ""
        if not url:
            self._set_status("Paste a YouTube URL first.")
            return

        if self.fetch_button:
            self.fetch_button.disabled = True
        self._set_status("Fetching video info...")
        threading.Thread(target=self._fetch_video_info_worker, args=(url,), daemon=True).start()

    def _fetch_video_info_worker(self, url: str):
        try:
            info = self.engine.fetch_info(url)
            Clock.schedule_once(lambda _dt: self._apply_video_info(info), 0)
        except Exception as exc:
            Clock.schedule_once(lambda _dt, err=str(exc): self._set_fetch_error(err), 0)

    def _apply_video_info(self, info: VideoInfo):
        self.video_info = info
        self.selected_format = info.formats[0] if info.formats else None

        if self.video_title_label:
            self.video_title_label.text = info.title or "Untitled video"
        if self.video_meta_label:
            meta = f"{info.channel or 'Unknown channel'} | {info.duration_str}"
            self.video_meta_label.text = meta

        self._rebuild_format_buttons(info.formats)

        if self.download_button:
            self.download_button.disabled = self.selected_format is None
        if self.fetch_button:
            self.fetch_button.disabled = False

        if self.selected_format:
            self._set_status(f"Ready: {self.selected_format.label}")
        else:
            self._set_status("No downloadable formats found.")

    def _set_fetch_error(self, message: str):
        if self.fetch_button:
            self.fetch_button.disabled = False
        if self.download_button:
            self.download_button.disabled = True
        self._set_status(f"Fetch failed: {message}")

    def _rebuild_format_buttons(self, formats: list[FormatOption]):
        if not self.formats_box:
            return

        self.formats_box.clear_widgets()
        if not formats:
            no_formats = Label(text="No formats available.", size_hint_y=None, height=dp(30), halign="left")
            no_formats.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.formats_box.add_widget(no_formats)
            return

        for fmt in formats[:8]:
            suffix = f" - {self.engine.sizeof_fmt(fmt.filesize)}" if fmt.filesize else ""
            text = f"{fmt.label}{suffix}"
            btn = Button(text=text, size_hint_y=None, height=dp(42))
            btn.bind(on_release=lambda _btn, current=fmt: self._select_format(current))
            self.formats_box.add_widget(btn)

    def _select_format(self, fmt: FormatOption):
        self.selected_format = fmt
        self._set_status(f"Selected format: {fmt.label}")

    def on_download_pressed(self, _instance):
        url = (self.url_input.text or "").strip() if self.url_input else ""
        if not url:
            self._set_status("Paste a YouTube URL first.")
            return

        if self.selected_format is None:
            self._set_status("Fetch and select a format first.")
            return

        try:
            self.engine.download(
                url=url,
                format_option=self.selected_format,
                output_dir=self.engine.default_output_dir,
                progress_callback=self._on_engine_progress,
            )
        except Exception as exc:
            self._set_status(f"Download start failed: {exc}")
            return

        if self.download_button:
            self.download_button.disabled = True
        if self.fetch_button:
            self.fetch_button.disabled = True
        if self.cancel_button:
            self.cancel_button.disabled = False
        self._set_status("Download started...")

    def _on_engine_progress(self, progress: DownloadProgress):
        snapshot = {
            "status": progress.status,
            "percent": float(progress.percent),
            "speed": progress.speed,
            "eta": progress.eta,
            "downloaded": progress.downloaded,
            "total": progress.total,
            "error_message": progress.error_message,
        }
        Clock.schedule_once(lambda _dt, data=snapshot: self._apply_progress(data), 0)

    def _apply_progress(self, data: dict):
        percent = max(0.0, min(100.0, data.get("percent", 0.0)))
        if self.progress_bar:
            self.progress_bar.value = percent

        status = data.get("status", "idle")
        if status == "downloading":
            speed = data.get("speed") or ""
            eta = data.get("eta") or ""
            downloaded = data.get("downloaded") or ""
            total = data.get("total") or ""
            if self.progress_text:
                self.progress_text.text = (
                    f"Progress: {percent:.1f}% | {downloaded}/{total} | {speed} | ETA {eta}"
                )
            self._set_status("Downloading...")
            return

        if self.progress_text:
            self.progress_text.text = f"Progress: {percent:.1f}%"

        if status == "processing":
            self._set_status("Post-processing media...")
        elif status == "finished":
            self._set_status(f"Finished. Saved to {self.engine.default_output_dir}")
            self._reset_buttons_after_download()
        elif status == "cancelled":
            self._set_status("Download cancelled.")
            self._reset_buttons_after_download()
        elif status == "error":
            error_message = data.get("error_message") or "Unknown error"
            self._set_status(f"Download failed: {error_message}")
            self._reset_buttons_after_download()

    def on_cancel_pressed(self, _instance):
        self.engine.cancel()
        self._set_status("Cancelling download...")

    def _reset_buttons_after_download(self):
        if self.download_button:
            self.download_button.disabled = self.selected_format is None
        if self.fetch_button:
            self.fetch_button.disabled = False
        if self.cancel_button:
            self.cancel_button.disabled = True

    def _set_status(self, message: str):
        if self.status_label:
            self.status_label.text = f"Save path: {self.engine.default_output_dir}\nStatus: {message}"


__all__ = ["TubeGrabApp"]
