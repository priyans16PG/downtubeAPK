"""TubeGrab mobile-compatible app built with Kivy."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Optional

from kivy.app import App as KivyApp
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.clipboard import Clipboard
from kivy.graphics import Color, RoundedRectangle, Triangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from downloader import DownloadEngine, DownloadProgress, FormatOption, VideoInfo
from styles import Colors


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    """Convert #RRGGBB to Kivy RGBA tuple."""
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return (1.0, 1.0, 1.0, alpha)
    red = int(value[0:2], 16) / 255.0
    green = int(value[2:4], 16) / 255.0
    blue = int(value[4:6], 16) / 255.0
    return (red, green, blue, alpha)


class Card(BoxLayout):
    """Simple rounded card container with dark theme styling."""

    def __init__(self, background_hex: str, radius: int = 16, **kwargs):
        super().__init__(**kwargs)
        self.background_rgba = _hex_to_rgba(background_hex)
        self.radius = radius
        with self.canvas.before:
            self._bg_color = Color(*self.background_rgba)
            self._bg_rect = RoundedRectangle(radius=[self.radius])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size


class LogoBadge(Widget):
    """Custom drawn TubeGrab logo badge."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._bg_color = Color(*_hex_to_rgba(Colors.ACCENT_RED))
            self._bg = RoundedRectangle(radius=[dp(10)])
            self._play_color = Color(1, 1, 1, 1)
            self._play = Triangle()
        self.bind(pos=self._draw_logo, size=self._draw_logo)

    def _draw_logo(self, *_args):
        self._bg.pos = self.pos
        self._bg.size = self.size

        cx = self.x + self.width * 0.50
        cy = self.y + self.height * 0.50
        scale = min(self.width, self.height)
        self._play.points = [
            cx - scale * 0.14,
            cy - scale * 0.18,
            cx - scale * 0.14,
            cy + scale * 0.18,
            cx + scale * 0.20,
            cy,
        ]


class TubeGrabApp(KivyApp):
    """Kivy UI for desktop and Android builds."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = DownloadEngine()
        self.app_version = self._load_app_version()
        self.video_info: Optional[VideoInfo] = None
        self.selected_format: Optional[FormatOption] = None
        self.format_buttons: list[tuple[Button, FormatOption]] = []
        self.fetch_button: Optional[Button] = None
        self.download_button: Optional[Button] = None
        self.cancel_button: Optional[Button] = None
        self.pause_resume_button: Optional[Button] = None
        self.path_set_button: Optional[Button] = None
        self.playlist_mode_button: Optional[Button] = None
        self.url_input: Optional[TextInput] = None
        self.path_input: Optional[TextInput] = None
        self.video_title_label: Optional[Label] = None
        self.video_meta_label: Optional[Label] = None
        self.status_label: Optional[Label] = None
        self.history_label: Optional[Label] = None
        self.progress_text: Optional[Label] = None
        self.progress_bar: Optional[ProgressBar] = None
        self.formats_box: Optional[BoxLayout] = None
        self.loading_modal: Optional[ModalView] = None
        self.loading_message: Optional[Label] = None
        self.loading_dots_event = None
        self.logo_path = os.path.join(os.path.dirname(__file__), "logo", "tubegraplogo.png")
        self.history_path = os.path.join(os.path.dirname(__file__), "download_history.json")
        self.download_history = self._load_download_history()
        self.last_download_url = ""
        self.last_download_format: Optional[FormatOption] = None
        self.download_full_playlist = False
        self.last_download_full_playlist = False
        self.pause_requested = False
        self.is_paused = False

    def _load_app_version(self) -> str:
        """Read app version from buildozer.spec so UI auto-updates when version is bumped."""
        spec_path = os.path.join(os.path.dirname(__file__), "buildozer.spec")
        if not os.path.exists(spec_path):
            return "dev"

        try:
            with open(spec_path, "r", encoding="utf-8") as fp:
                for raw_line in fp:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.lower().startswith("version") and "=" in line:
                        return line.split("=", 1)[1].strip() or "dev"
        except Exception:
            return "dev"

        return "dev"

    def _load_download_history(self) -> list[dict]:
        """Load persisted download history if available."""
        if not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def _save_download_history(self):
        """Persist download history to disk."""
        try:
            with open(self.history_path, "w", encoding="utf-8") as fp:
                json.dump(self.download_history[-30:], fp, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def _add_history_entry(self, status: str, details: str = ""):
        """Add one history event and refresh UI section."""
        title = self.video_info.title if self.video_info else "Unknown"
        if self.video_info and self.video_info.is_playlist and self.download_full_playlist:
            title = self.video_info.playlist_title or title
        fmt = self.selected_format.label if self.selected_format else "Unknown format"
        target = self._get_selected_output_dir()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "time": timestamp,
            "title": title,
            "format": fmt,
            "status": status,
            "path": target,
            "details": details,
        }
        self.download_history.append(entry)
        self.download_history = self.download_history[-30:]
        self._save_download_history()
        self._refresh_history_label()

    def _refresh_history_label(self):
        if not self.history_label:
            return
        if not self.download_history:
            self.history_label.text = "No downloads yet."
            return
        lines = []
        for item in reversed(self.download_history[-5:]):
            status = item.get("status", "")
            title = item.get("title", "Unknown")
            tstamp = item.get("time", "")
            lines.append(f"[{tstamp}] {status}: {title}")
        self.history_label.text = "\n".join(lines)

    def _get_selected_output_dir(self) -> str:
        """Read save-path text input and fallback to engine default path."""
        raw = (self.path_input.text or "").strip() if self.path_input else ""
        return raw or self.engine.default_output_dir

    def _make_logo_widget(self, size_dp: float):
        """Build logo widget from file when available, fallback to vector badge."""
        size_px = dp(size_dp)
        if os.path.exists(self.logo_path):
            return Image(
                source=self.logo_path,
                size_hint=(None, None),
                size=(size_px, size_px),
                allow_stretch=True,
                keep_ratio=True,
            )
        return LogoBadge(size_hint=(None, None), size=(size_px, size_px))

    def build(self):
        self.title = "TubeGrab"
        if Window is not None:
            Window.minimum_width = dp(360)
            Window.minimum_height = dp(640)
            Window.clearcolor = _hex_to_rgba(Colors.DARK_BG_PRIMARY)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        scroll = ScrollView(size_hint=(1, 1))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
            padding=(0, dp(8)),
        )
        content.bind(minimum_height=content.setter("height"))

        header = Card(
            background_hex=Colors.DARK_BG_SECONDARY,
            orientation="horizontal",
            size_hint_y=None,
            height=dp(72),
            spacing=dp(12),
            padding=[dp(14), dp(10), dp(14), dp(10)],
        )
        logo = self._make_logo_widget(42)
        header.add_widget(logo)
        title_group = BoxLayout(orientation="vertical", spacing=dp(2))
        title = Label(
            text="TubeGrab",
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            size_hint_y=0.62,
            halign="left",
            valign="bottom",
            bold=True,
            font_size="22sp",
        )
        title.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        subtitle = Label(
            text=f"Fast video and audio downloads  |  v{self.app_version}",
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            size_hint_y=0.38,
            halign="left",
            valign="top",
            font_size="12sp",
        )
        subtitle.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        title_group.add_widget(title)
        title_group.add_widget(subtitle)
        header.add_widget(title_group)
        content.add_widget(header)

        url_card = Card(
            background_hex=Colors.DARK_BG_SECONDARY,
            orientation="vertical",
            size_hint_y=None,
            height=dp(276),
            spacing=dp(10),
            padding=[dp(14), dp(14), dp(14), dp(14)],
        )
        paste_label = Label(
            text="Paste YouTube URL",
            size_hint_y=None,
            height=dp(22),
            halign="left",
            valign="middle",
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="15sp",
        )
        paste_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        url_card.add_widget(paste_label)

        url_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        self.url_input = TextInput(
            hint_text="https://youtube.com/watch?v=...",
            multiline=False,
            size_hint=(0.75, 1),
            background_normal="",
            background_active="",
            background_color=_hex_to_rgba(Colors.DARK_BG_INPUT),
            foreground_color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            cursor_color=_hex_to_rgba(Colors.ACCENT_RED),
            padding=[dp(12), dp(12), dp(12), dp(12)],
        )
        url_row.add_widget(self.url_input)

        paste_button = Button(
            text="Paste",
            size_hint=(0.25, 1),
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
        )
        paste_button.bind(on_release=self.on_paste_url_pressed)
        url_row.add_widget(paste_button)
        url_card.add_widget(url_row)

        button_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        self.fetch_button = Button(
            text="Fetch",
            size_hint_x=0.5,
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_RED),
            color=(1, 1, 1, 1),
            bold=True,
        )
        self.fetch_button.bind(on_release=self.on_fetch_pressed)
        button_row.add_widget(self.fetch_button)

        self.download_button = Button(
            text="Download",
            size_hint_x=0.5,
            disabled=True,
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_BLUE),
            color=(1, 1, 1, 1),
            bold=True,
        )
        self.download_button.bind(on_release=self.on_download_pressed)
        button_row.add_widget(self.download_button)
        url_card.add_widget(button_row)

        save_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        self.path_input = TextInput(
            text=self.engine.default_output_dir,
            multiline=False,
            size_hint=(0.78, 1),
            background_normal="",
            background_active="",
            background_color=_hex_to_rgba(Colors.DARK_BG_INPUT),
            foreground_color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        save_row.add_widget(self.path_input)

        self.path_set_button = Button(
            text="Set Path",
            size_hint=(0.22, 1),
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
        )
        self.path_set_button.bind(on_release=self.on_set_path_pressed)
        save_row.add_widget(self.path_set_button)
        url_card.add_widget(save_row)

        playlist_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        self.playlist_mode_button = Button(
            text="Playlist Mode: Single Video",
            size_hint=(1, 1),
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
        )
        self.playlist_mode_button.bind(on_release=self.on_playlist_mode_pressed)
        playlist_row.add_widget(self.playlist_mode_button)
        url_card.add_widget(playlist_row)
        self._refresh_playlist_mode_button()

        content.add_widget(url_card)

        action_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        self.pause_resume_button = Button(
            text="Pause",
            size_hint=(0.5, 1),
            disabled=True,
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_YELLOW),
            color=(0.1, 0.1, 0.1, 1),
            bold=True,
        )
        self.pause_resume_button.bind(on_release=self.on_pause_resume_pressed)
        action_row.add_widget(self.pause_resume_button)

        self.cancel_button = Button(
            text="Cancel",
            size_hint=(0.5, 1),
            disabled=True,
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_ORANGE),
            color=(0.1, 0.1, 0.1, 1),
            bold=True,
        )
        self.cancel_button.bind(on_release=self.on_cancel_pressed)
        action_row.add_widget(self.cancel_button)
        content.add_widget(action_row)

        preview_card = Card(
            background_hex=Colors.DARK_BG_SECONDARY,
            orientation="vertical",
            size_hint_y=None,
            height=dp(138),
            spacing=dp(4),
            padding=[dp(14), dp(12), dp(14), dp(12)],
        )
        self.video_title_label = Label(
            text="No video loaded.",
            size_hint_y=None,
            height=dp(62),
            halign="left",
            valign="top",
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            text_size=(0, None),
            bold=True,
            font_size="15sp",
        )
        self.video_title_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        preview_card.add_widget(self.video_title_label)

        self.video_meta_label = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            font_size="12sp",
        )
        self.video_meta_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        preview_card.add_widget(self.video_meta_label)
        content.add_widget(preview_card)

        formats_header = Label(
            text="Formats",
            size_hint_y=None,
            height=dp(26),
            halign="left",
            valign="middle",
            bold=True,
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            font_size="16sp",
        )
        formats_header.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(formats_header)

        self.formats_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6), padding=(0, 0, 0, dp(6)))
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
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
        )
        self.progress_text.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        content.add_widget(self.progress_text)

        footer_card = Card(
            background_hex=Colors.DARK_BG_SECONDARY,
            orientation="vertical",
            size_hint_y=None,
            height=dp(132),
            padding=[dp(14), dp(10), dp(14), dp(10)],
        )
        self.status_label = Label(
            text=f"Save path: {self._get_selected_output_dir()}",
            size_hint_y=None,
            height=dp(64),
            halign="left",
            valign="top",
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            font_size="12sp",
        )
        self.status_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        footer_card.add_widget(self.status_label)

        self.history_label = Label(
            text="No downloads yet.",
            size_hint_y=None,
            height=dp(48),
            halign="left",
            valign="top",
            color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
            font_size="11sp",
        )
        self.history_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        footer_card.add_widget(self.history_label)
        content.add_widget(footer_card)
        self._refresh_history_label()

        scroll.add_widget(content)
        root.add_widget(scroll)
        Clock.schedule_once(lambda _dt: self._show_startup_splash(), 0.05)
        return root

    def _show_startup_splash(self):
        """Display startup loading screen with custom logo."""
        modal = ModalView(
            auto_dismiss=False,
            size_hint=(1, 1),
            background_color=(0.02, 0.02, 0.05, 0.95),
        )

        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(14),
            padding=[dp(20), dp(80), dp(20), dp(80)],
        )

        spacer_top = Widget(size_hint_y=0.9)
        layout.add_widget(spacer_top)

        logo = self._make_logo_widget(84)
        logo_holder = BoxLayout(size_hint_y=None, height=dp(90), padding=[0, 0, 0, 0])
        logo_holder.add_widget(Widget(size_hint_x=1))
        logo_holder.add_widget(logo)
        logo_holder.add_widget(Widget(size_hint_x=1))
        layout.add_widget(logo_holder)

        title = Label(
            text="TubeGrab",
            size_hint_y=None,
            height=dp(34),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="26sp",
        )
        layout.add_widget(title)

        subtitle = Label(
            text="Preparing downloader...",
            size_hint_y=None,
            height=dp(24),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            font_size="14sp",
        )
        layout.add_widget(subtitle)

        self.loading_message = Label(
            text="Loading",
            size_hint_y=None,
            height=dp(28),
            color=_hex_to_rgba(Colors.ACCENT_RED),
            bold=True,
            font_size="15sp",
        )
        layout.add_widget(self.loading_message)

        spacer_bottom = Widget(size_hint_y=1.1)
        layout.add_widget(spacer_bottom)
        modal.add_widget(layout)
        modal.open()

        self.loading_modal = modal
        self.loading_dots_event = Clock.schedule_interval(self._animate_loading_text, 0.45)
        pulse = Animation(opacity=0.35, duration=0.55) + Animation(opacity=1.0, duration=0.55)
        pulse.repeat = True
        pulse.start(logo)
        Clock.schedule_once(lambda _dt: self._close_loading_modal(), 1.9)

    def _animate_loading_text(self, _dt):
        if not self.loading_message:
            return
        current = self.loading_message.text
        dots = current.count(".")
        dots = 0 if dots >= 3 else dots + 1
        self.loading_message.text = f"Loading{'.' * dots}"

    def _show_loading_overlay(self, message: str):
        """Show a non-blocking loading overlay for network tasks."""
        if self.loading_modal is not None:
            self._close_loading_modal()

        modal = ModalView(
            auto_dismiss=False,
            size_hint=(1, 1),
            background_color=(0.03, 0.03, 0.08, 0.82),
        )
        body = BoxLayout(orientation="vertical", spacing=dp(10), padding=[dp(20), dp(20), dp(20), dp(20)])
        body.add_widget(Widget(size_hint_y=1))
        message_label = Label(
            text=message,
            size_hint_y=None,
            height=dp(32),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="16sp",
        )
        body.add_widget(message_label)
        self.loading_message = Label(
            text="Please wait",
            size_hint_y=None,
            height=dp(28),
            color=_hex_to_rgba(Colors.ACCENT_BLUE),
            font_size="14sp",
        )
        body.add_widget(self.loading_message)
        body.add_widget(Widget(size_hint_y=1))
        modal.add_widget(body)
        modal.open()
        self.loading_modal = modal
        self.loading_dots_event = Clock.schedule_interval(self._animate_loading_wait, 0.4)

    def _animate_loading_wait(self, _dt):
        if not self.loading_message:
            return
        variants = ["Please wait", "Please wait.", "Please wait..", "Please wait..."]
        try:
            current_index = variants.index(self.loading_message.text)
        except ValueError:
            current_index = 0
        self.loading_message.text = variants[(current_index + 1) % len(variants)]

    def _close_loading_modal(self):
        if self.loading_dots_event is not None:
            self.loading_dots_event.cancel()
            self.loading_dots_event = None
        if self.loading_modal is not None:
            self.loading_modal.dismiss()
            self.loading_modal = None
        self.loading_message = None

    def on_fetch_pressed(self, _instance):
        url = (self.url_input.text or "").strip() if self.url_input else ""
        if not url:
            self._set_status("Paste a YouTube URL first.")
            return

        if self.fetch_button:
            self.fetch_button.disabled = True
        self._set_status("Fetching video info...")
        self._show_loading_overlay("Fetching video details")
        threading.Thread(target=self._fetch_video_info_worker, args=(url,), daemon=True).start()

    def on_paste_url_pressed(self, _instance):
        text = (Clipboard.paste() or "").strip()
        if not text:
            self._set_status("Clipboard is empty.")
            return
        if self.url_input:
            self.url_input.text = text
        self._set_status("URL pasted from clipboard.")

    def on_set_path_pressed(self, _instance):
        path = self._get_selected_output_dir()
        try:
            os.makedirs(path, exist_ok=True)
            self.engine.default_output_dir = path
            self._set_status("Save path updated.")
        except Exception as exc:
            self._set_status(f"Invalid save path: {exc}")

    def _fetch_video_info_worker(self, url: str):
        try:
            info = self.engine.fetch_info(url)
            Clock.schedule_once(lambda _dt: self._apply_video_info(info), 0)
        except Exception as exc:
            Clock.schedule_once(lambda _dt, err=str(exc): self._set_fetch_error(err), 0)

    def _apply_video_info(self, info: VideoInfo):
        self._close_loading_modal()
        self.video_info = info
        self.selected_format = info.formats[0] if info.formats else None

        if info.is_playlist:
            self.download_full_playlist = True
        else:
            self.download_full_playlist = False
        self._refresh_playlist_mode_button()

        if self.video_title_label:
            self.video_title_label.text = info.title or "Untitled video"
        if self.video_meta_label:
            meta = f"{info.channel or 'Unknown channel'} | {info.duration_str}"
            if info.is_playlist:
                count = info.playlist_count or 0
                meta = f"Playlist: {info.playlist_title or info.title} | {count} items"
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
        self._close_loading_modal()
        if self.fetch_button:
            self.fetch_button.disabled = False
        if self.download_button:
            self.download_button.disabled = True
        self._set_status(f"Fetch failed: {message}")

    def _rebuild_format_buttons(self, formats: list[FormatOption]):
        if not self.formats_box:
            return

        self.formats_box.clear_widgets()
        self.format_buttons = []
        if not formats:
            no_formats = Label(text="No formats available.", size_hint_y=None, height=dp(30), halign="left")
            no_formats.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.formats_box.add_widget(no_formats)
            return

        for fmt in formats[:8]:
            suffix = f" - {self.engine.sizeof_fmt(fmt.filesize)}" if fmt.filesize else ""
            text = f"{fmt.label}{suffix}"
            btn = Button(text=text, size_hint_y=None, height=dp(42))
            btn.background_normal = ""
            self._style_format_button(btn, fmt == self.selected_format)
            btn.bind(on_release=lambda _btn, current=fmt: self._select_format(current))
            self.formats_box.add_widget(btn)
            self.format_buttons.append((btn, fmt))

    def _style_format_button(self, button: Button, is_selected: bool):
        if is_selected:
            button.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
            button.color = (1, 1, 1, 1)
        else:
            button.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
            button.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)

    def _refresh_format_button_selection(self):
        for button, fmt in self.format_buttons:
            self._style_format_button(button, fmt == self.selected_format)

    def _select_format(self, fmt: FormatOption):
        self.selected_format = fmt
        self._refresh_format_button_selection()
        self._set_status(f"Selected format: {fmt.label}")

    def _refresh_playlist_mode_button(self):
        if not self.playlist_mode_button:
            return

        if self.video_info and self.video_info.is_playlist:
            if self.download_full_playlist:
                self.playlist_mode_button.text = "Playlist Mode: Full Playlist"
                self.playlist_mode_button.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
                self.playlist_mode_button.color = (1, 1, 1, 1)
            else:
                self.playlist_mode_button.text = "Playlist Mode: First Video Only"
                self.playlist_mode_button.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
                self.playlist_mode_button.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)
            self.playlist_mode_button.disabled = False
            return

        self.playlist_mode_button.text = "Playlist Mode: Single Video"
        self.playlist_mode_button.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
        self.playlist_mode_button.color = _hex_to_rgba(Colors.DARK_TEXT_MUTED)
        self.playlist_mode_button.disabled = True

    def on_playlist_mode_pressed(self, _instance):
        if not self.video_info or not self.video_info.is_playlist:
            self._set_status("Load a playlist URL to change playlist mode.")
            return

        self.download_full_playlist = not self.download_full_playlist
        self._refresh_playlist_mode_button()
        if self.download_full_playlist:
            self._set_status("Playlist mode set to full playlist download.")
        else:
            self._set_status("Playlist mode set to first video only.")

    def on_download_pressed(self, _instance):
        url = (self.url_input.text or "").strip() if self.url_input else ""
        if not url:
            self._set_status("Paste a YouTube URL first.")
            return

        if self.selected_format is None:
            self._set_status("Fetch and select a format first.")
            return

        output_dir = self._get_selected_output_dir()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as exc:
            self._set_status(f"Invalid save path: {exc}")
            return

        try:
            self.engine.download(
                url=url,
                format_option=self.selected_format,
                output_dir=output_dir,
                download_full_playlist=self.download_full_playlist,
                progress_callback=self._on_engine_progress,
            )
        except Exception as exc:
            self._set_status(f"Download start failed: {exc}")
            return

        self.last_download_url = url
        self.last_download_format = self.selected_format
        self.last_download_full_playlist = self.download_full_playlist
        self.pause_requested = False
        self.is_paused = False

        if self.download_button:
            self.download_button.disabled = True
        if self.fetch_button:
            self.fetch_button.disabled = True
        if self.cancel_button:
            self.cancel_button.disabled = False
        if self.pause_resume_button:
            self.pause_resume_button.disabled = False
            self.pause_resume_button.text = "Pause"
        if self.path_set_button:
            self.path_set_button.disabled = True
        if self.path_input:
            self.path_input.disabled = True
        self._show_loading_overlay("Starting download")
        if self.video_info and self.video_info.is_playlist and self.download_full_playlist:
            count = self.video_info.playlist_count or 0
            self._set_status(f"Playlist download started ({count} items)...")
        else:
            self._set_status("Download started...")

    def on_pause_resume_pressed(self, _instance):
        if self.engine.is_busy:
            self.pause_requested = True
            self.engine.cancel()
            self._set_status("Pausing download...")
            return

        if not self.is_paused:
            self._set_status("No paused download to resume.")
            return

        if not self.last_download_url or self.last_download_format is None:
            self._set_status("Nothing to resume yet.")
            return

        output_dir = self._get_selected_output_dir()
        try:
            self.engine.download(
                url=self.last_download_url,
                format_option=self.last_download_format,
                output_dir=output_dir,
                download_full_playlist=self.last_download_full_playlist,
                progress_callback=self._on_engine_progress,
            )
        except Exception as exc:
            self._set_status(f"Resume failed: {exc}")
            return

        self.pause_requested = False
        self.is_paused = False
        if self.pause_resume_button:
            self.pause_resume_button.text = "Pause"
        if self.cancel_button:
            self.cancel_button.disabled = False
        self._set_status("Resuming download...")

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
        status = data.get("status", "idle")
        if status in {"downloading", "processing"}:
            self._close_loading_modal()

        percent = max(0.0, min(100.0, data.get("percent", 0.0)))
        if self.progress_bar:
            self.progress_bar.value = percent

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
            self._add_history_entry("Finished")
            self._set_status(f"Finished. Saved to {self._get_selected_output_dir()}")
            self._reset_buttons_after_download()
        elif status == "cancelled":
            if self.pause_requested:
                self.pause_requested = False
                self.is_paused = True
                if self.pause_resume_button:
                    self.pause_resume_button.disabled = False
                    self.pause_resume_button.text = "Resume"
                if self.download_button:
                    self.download_button.disabled = True
                if self.fetch_button:
                    self.fetch_button.disabled = True
                if self.cancel_button:
                    self.cancel_button.disabled = False
                self._set_status("Download paused. Press Resume to continue.")
                self._add_history_entry("Paused")
            else:
                self._set_status("Download cancelled.")
                self._add_history_entry("Cancelled")
                self._reset_buttons_after_download()
        elif status == "error":
            error_message = data.get("error_message") or "Unknown error"
            self._set_status(f"Download failed: {error_message}")
            self._add_history_entry("Failed", error_message)
            self._reset_buttons_after_download()

    def on_cancel_pressed(self, _instance):
        if self.is_paused:
            self._add_history_entry("Cancelled", "Cancelled from paused state")
            self._set_status("Paused download cancelled.")
            self._reset_buttons_after_download()
            return
        self.engine.cancel()
        self._close_loading_modal()
        self._set_status("Cancelling download...")

    def _reset_buttons_after_download(self):
        self.pause_requested = False
        self.is_paused = False
        if self.download_button:
            self.download_button.disabled = self.selected_format is None
        if self.fetch_button:
            self.fetch_button.disabled = False
        if self.cancel_button:
            self.cancel_button.disabled = True
        if self.pause_resume_button:
            self.pause_resume_button.disabled = True
            self.pause_resume_button.text = "Pause"
        if self.path_set_button:
            self.path_set_button.disabled = False
        if self.path_input:
            self.path_input.disabled = False
        self._refresh_playlist_mode_button()

    def _set_status(self, message: str):
        if self.status_label:
            self.status_label.text = (
                f"TubeGrab v{self.app_version}\n"
                f"Save path: {self._get_selected_output_dir()}\n"
                f"Status: {message}"
            )


__all__ = ["TubeGrabApp"]
