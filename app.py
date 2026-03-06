"""TubeGrab redesigned as a multi-screen Kivy application."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Optional

from kivy.app import App as KivyApp
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from downloader import DownloadEngine, DownloadProgress, FormatOption, VideoInfo
from styles import Colors


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        return (1.0, 1.0, 1.0, alpha)
    red = int(value[0:2], 16) / 255.0
    green = int(value[2:4], 16) / 255.0
    blue = int(value[4:6], 16) / 255.0
    return (red, green, blue, alpha)


class AppScaffold(BoxLayout):
    """Root scaffold that hosts top area and bottom navigation."""


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url_input: Optional[TextInput] = None
        self.recent_box: Optional[BoxLayout] = None
        self.helper_label: Optional[Label] = None
        self.version_label: Optional[Label] = None
        self.stage_label: Optional[Label] = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(14))

        top = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(96), spacing=dp(4))
        title_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        title_group = BoxLayout(orientation="vertical", spacing=dp(2))
        title = Label(
            text="TubeGrab",
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            halign="left",
            valign="middle",
            font_size="25sp",
        )
        title.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        subtitle = Label(
            text="Fast Video Downloader",
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="top",
            font_size="12sp",
        )
        subtitle.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        title_group.add_widget(title)
        title_group.add_widget(subtitle)

        self.version_label = Label(
            text="v--",
            size_hint_x=0.26,
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="right",
            valign="middle",
            font_size="11sp",
        )
        self.version_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        title_row.add_widget(title_group)
        title_row.add_widget(self.version_label)

        self.stage_label = Label(
            text="Stage: Home",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.ACCENT_BLUE),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        self.stage_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))

        top.add_widget(title_row)
        top.add_widget(self.stage_label)
        root.add_widget(top)

        url_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.url_input = TextInput(
            hint_text="Paste video or playlist link",
            multiline=False,
            background_normal="",
            background_active="",
            background_color=_hex_to_rgba(Colors.DARK_BG_INPUT),
            foreground_color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            padding=[dp(12), dp(14), dp(12), dp(12)],
            font_size="14sp",
        )
        paste_btn = Button(
            text="Paste",
            size_hint_x=0.26,
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
        )
        paste_btn.bind(on_release=self._on_paste)
        url_row.add_widget(self.url_input)
        url_row.add_widget(paste_btn)
        root.add_widget(url_row)

        fetch_btn = Button(
            text="Fetch Info",
            size_hint_y=None,
            height=dp(54),
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_RED),
            color=(1, 1, 1, 1),
            bold=True,
            font_size="16sp",
        )
        fetch_btn.bind(on_release=self._on_fetch)
        root.add_widget(fetch_btn)

        self.helper_label = Label(
            text="Supports single videos and playlists.",
            size_hint_y=None,
            height=dp(24),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        self.helper_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(self.helper_label)

        recent_title = Label(
            text="Recent Links",
            size_hint_y=None,
            height=dp(24),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            halign="left",
            valign="middle",
            bold=True,
        )
        recent_title.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(recent_title)

        recent_scroll = ScrollView(size_hint=(1, 1))
        self.recent_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, 0, 0, dp(12)))
        self.recent_box.bind(minimum_height=self.recent_box.setter("height"))
        recent_scroll.add_widget(self.recent_box)
        root.add_widget(recent_scroll)

        self.add_widget(root)

    def on_pre_enter(self, *_args):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        if self.version_label:
            self.version_label.text = f"v{app.app_version}"
        if self.stage_label:
            self.stage_label.text = f"Stage: Home  •  {app.status_message}"
        self.update_recent_links(app.recent_links)

    def _on_paste(self, _instance):
        text = (Clipboard.paste() or "").strip()
        if text and self.url_input:
            self.url_input.text = text

    def _on_fetch(self, _instance):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        url = (self.url_input.text if self.url_input else "").strip()
        app.start_fetch(url)

    def update_recent_links(self, recent_links: list[str]):
        if not self.recent_box:
            return

        self.recent_box.clear_widgets()
        if not recent_links:
            empty = Label(
                text="No recent links yet.",
                size_hint_y=None,
                height=dp(32),
                color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
                halign="left",
                valign="middle",
            )
            empty.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.recent_box.add_widget(empty)
            return

        for item in recent_links[:8]:
            btn = Button(
                text=item,
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
                halign="left",
            )
            btn.bind(on_release=lambda _btn, value=item: self._reuse_recent(value))
            self.recent_box.add_widget(btn)

    def _reuse_recent(self, value: str):
        if self.url_input:
            self.url_input.text = value


class MediaInfoScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_label: Optional[Label] = None
        self.meta_label: Optional[Label] = None
        self.mode_buttons: dict[str, Button] = {}
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        back = Button(
            text="< Back",
            size_hint_x=0.24,
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
        )
        back.bind(on_release=lambda _btn: self._go_home())
        title = Label(text="Video Info", color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY), bold=True, font_size="20sp")
        top.add_widget(back)
        top.add_widget(title)
        root.add_widget(top)

        stage = Label(
            text="Review media and choose playlist mode",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        stage.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(stage)

        preview = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(160), spacing=dp(6))
        self.title_label = Label(
            text="No media loaded",
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            halign="left",
            valign="top",
            font_size="18sp",
        )
        self.title_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        self.meta_label = Label(
            text="",
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="top",
        )
        self.meta_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        preview.add_widget(self.title_label)
        preview.add_widget(self.meta_label)
        root.add_widget(preview)

        modes = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for key, label in (
            ("single", "Single Video"),
            ("first", "First Video"),
            ("full", "Full Playlist"),
        ):
            btn = Button(
                text=label,
                background_normal="",
                background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            )
            btn.bind(on_release=lambda _btn, mode=key: self._select_mode(mode))
            self.mode_buttons[key] = btn
            modes.add_widget(btn)
        root.add_widget(modes)

        continue_btn = Button(
            text="Choose Format",
            size_hint_y=None,
            height=dp(54),
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_BLUE),
            color=(1, 1, 1, 1),
            bold=True,
            font_size="16sp",
        )
        continue_btn.bind(on_release=lambda _btn: self._go_format())
        root.add_widget(continue_btn)

        root.add_widget(Label())
        self.add_widget(root)

    def on_pre_enter(self, *_args):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        info = app.video_info
        if not info:
            return

        if self.title_label:
            self.title_label.text = info.playlist_title if info.is_playlist and info.playlist_title else info.title
        if self.meta_label:
            if info.is_playlist:
                self.meta_label.text = f"Playlist • {info.playlist_count} items"
            else:
                self.meta_label.text = f"{info.channel} • {info.duration_str}"

        is_playlist = info.is_playlist
        for key, btn in self.mode_buttons.items():
            btn.disabled = not is_playlist

        self._refresh_mode_ui(app.playlist_mode)

    def _refresh_mode_ui(self, mode: str):
        for key, btn in self.mode_buttons.items():
            if key == mode:
                btn.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
                btn.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)

    def _select_mode(self, mode: str):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.playlist_mode = mode
        if mode == "full":
            app.download_full_playlist = True
        elif mode == "first":
            app.download_full_playlist = False
        elif mode == "single":
            app.download_full_playlist = False
        self._refresh_mode_ui(mode)

    def _go_format(self):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.go_to("format_select")

    def _go_home(self):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.go_to("home")


class FormatSelectionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.summary_label: Optional[Label] = None
        self.path_input: Optional[TextInput] = None
        self.list_box: Optional[BoxLayout] = None
        self.format_buttons: list[tuple[Button, FormatOption]] = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        back = Button(
            text="< Back",
            size_hint_x=0.24,
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
        )
        back.bind(on_release=lambda _btn: self._go_media())
        title = Label(text="Select Format", color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY), bold=True, font_size="20sp")
        top.add_widget(back)
        top.add_widget(title)
        root.add_widget(top)

        stage = Label(
            text="Choose quality and confirm save path",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        stage.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(stage)

        self.summary_label = Label(
            text="No media selected",
            size_hint_y=None,
            height=dp(44),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
        )
        self.summary_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(self.summary_label)

        scroll = ScrollView(size_hint=(1, 1))
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, 0, 0, dp(10)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        path_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.path_input = TextInput(
            multiline=False,
            background_normal="",
            background_active="",
            background_color=_hex_to_rgba(Colors.DARK_BG_INPUT),
            foreground_color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            padding=[dp(10), dp(12), dp(10), dp(10)],
        )
        set_btn = Button(
            text="Change",
            size_hint_x=0.24,
            background_normal="",
            background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
        )
        set_btn.bind(on_release=self._on_set_path)
        path_row.add_widget(self.path_input)
        path_row.add_widget(set_btn)
        root.add_widget(path_row)

        start_btn = Button(
            text="Start Download",
            size_hint_y=None,
            height=dp(54),
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_BLUE),
            color=(1, 1, 1, 1),
            bold=True,
            font_size="16sp",
        )
        start_btn.bind(on_release=self._on_start)
        root.add_widget(start_btn)

        self.add_widget(root)

    def on_pre_enter(self, *_args):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        info = app.video_info
        if self.path_input:
            self.path_input.text = app.engine.default_output_dir

        if self.summary_label:
            if info:
                self.summary_label.text = f"{info.title} • {info.duration_str}"
            else:
                self.summary_label.text = "No media selected"

        self._rebuild_formats(info.formats if info else [], app.selected_format)

    def _rebuild_formats(self, formats: list[FormatOption], selected: Optional[FormatOption]):
        if not self.list_box:
            return

        self.list_box.clear_widgets()
        self.format_buttons = []
        if not formats:
            no_data = Label(
                text="No formats available.",
                size_hint_y=None,
                height=dp(34),
                color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
                halign="left",
                valign="middle",
            )
            no_data.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.list_box.add_widget(no_data)
            return

        for fmt in formats[:16]:
            suffix = f" - {KivyApp.get_running_app().engine.sizeof_fmt(fmt.filesize)}" if fmt.filesize else ""
            text = f"o {fmt.label}{suffix}"
            btn = Button(
                text=text,
                size_hint_y=None,
                height=dp(44),
                background_normal="",
                halign="left",
            )
            self._style_format_button(btn, fmt == selected)
            btn.bind(on_release=lambda _btn, current=fmt: self._select_format(current))
            self.list_box.add_widget(btn)
            self.format_buttons.append((btn, fmt))

    def _style_format_button(self, button: Button, is_selected: bool):
        if is_selected:
            button.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
            button.color = (1, 1, 1, 1)
        else:
            button.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
            button.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)

    def _select_format(self, fmt: FormatOption):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.selected_format = fmt
        for btn, target in self.format_buttons:
            self._style_format_button(btn, target == fmt)

    def _on_set_path(self, _instance):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        target = (self.path_input.text if self.path_input else "").strip() or app.engine.default_output_dir
        try:
            os.makedirs(target, exist_ok=True)
            app.engine.default_output_dir = target
            if self.path_input:
                self.path_input.text = target
        except Exception:
            app.set_status("Invalid save path")

    def _on_start(self, _instance):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        target = (self.path_input.text if self.path_input else "").strip() or app.engine.default_output_dir
        app.start_download(target)

    def _go_media(self):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.go_to("media_info")


class ActiveDownloadScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_label: Optional[Label] = None
        self.percent_label: Optional[Label] = None
        self.metrics_label: Optional[Label] = None
        self.status_label: Optional[Label] = None
        self.progress_bar: Optional[ProgressBar] = None
        self.pause_btn: Optional[Button] = None
        self.cancel_btn: Optional[Button] = None
        self.done_actions: Optional[BoxLayout] = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = Label(
            text="Downloading",
            size_hint_y=None,
            height=dp(44),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="22sp",
        )
        root.add_widget(top)

        subtitle = Label(
            text="Live progress and controls",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            font_size="11sp",
        )
        root.add_widget(subtitle)

        self.title_label = Label(
            text="No active download",
            size_hint_y=None,
            height=dp(40),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            halign="left",
            valign="middle",
            bold=True,
        )
        self.title_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(self.title_label)

        self.percent_label = Label(
            text="0%",
            size_hint_y=None,
            height=dp(42),
            color=_hex_to_rgba(Colors.ACCENT_BLUE),
            bold=True,
            font_size="32sp",
        )
        root.add_widget(self.percent_label)

        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(18))
        root.add_widget(self.progress_bar)

        self.metrics_label = Label(
            text="0MB / 0MB\n0MB/s | ETA -",
            size_hint_y=None,
            height=dp(54),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="center",
            valign="middle",
        )
        self.metrics_label.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(self.metrics_label)

        self.status_label = Label(
            text="Idle",
            size_hint_y=None,
            height=dp(28),
            color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
        )
        root.add_widget(self.status_label)

        controls = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        self.pause_btn = Button(
            text="Pause",
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_YELLOW),
            color=(0.1, 0.1, 0.1, 1),
        )
        self.pause_btn.bind(on_release=self._on_pause_resume)
        self.cancel_btn = Button(
            text="Cancel",
            background_normal="",
            background_color=_hex_to_rgba(Colors.ACCENT_ORANGE),
            color=(0.1, 0.1, 0.1, 1),
        )
        self.cancel_btn.bind(on_release=self._on_cancel)
        controls.add_widget(self.pause_btn)
        controls.add_widget(self.cancel_btn)
        root.add_widget(controls)

        self.done_actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8), opacity=0)
        open_btn = Button(text="Open File", background_normal="", background_color=_hex_to_rgba(Colors.DARK_BG_CARD))
        folder_btn = Button(text="Show Folder", background_normal="", background_color=_hex_to_rgba(Colors.DARK_BG_CARD))
        home_btn = Button(text="Return Home", background_normal="", background_color=_hex_to_rgba(Colors.DARK_BG_CARD))
        home_btn.bind(on_release=lambda _btn: self._go_home())
        self.done_actions.add_widget(open_btn)
        self.done_actions.add_widget(folder_btn)
        self.done_actions.add_widget(home_btn)
        root.add_widget(self.done_actions)

        root.add_widget(Label())
        self.add_widget(root)

    def _on_pause_resume(self, _instance):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.toggle_pause_resume()

    def _on_cancel(self, _instance):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.cancel_download()

    def _go_home(self):
        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        app.go_to("home")

    def update_progress(self, data: dict):
        status = data.get("status", "idle")
        percent = max(0.0, min(100.0, float(data.get("percent", 0.0))))

        if self.progress_bar:
            self.progress_bar.value = percent
        if self.percent_label:
            self.percent_label.text = f"{percent:.1f}%"
        if self.metrics_label:
            self.metrics_label.text = (
                f"{data.get('downloaded', '?')} / {data.get('total', '?')}\n"
                f"{data.get('speed', '-') or '-'} | ETA {data.get('eta', '-') or '-'}"
            )
        if self.status_label:
            self.status_label.text = status.capitalize()
            if status == "finished":
                self.status_label.color = _hex_to_rgba(Colors.SUCCESS)
            elif status == "error":
                self.status_label.color = _hex_to_rgba(Colors.ERROR)
            elif status == "downloading":
                self.status_label.color = _hex_to_rgba(Colors.ACCENT_BLUE)
            else:
                self.status_label.color = _hex_to_rgba(Colors.DARK_TEXT_MUTED)

        if self.pause_btn:
            self.pause_btn.text = "Resume" if data.get("is_paused") else "Pause"
            self.pause_btn.disabled = status in {"finished", "error", "cancelled"}

        if self.cancel_btn:
            self.cancel_btn.disabled = status in {"finished", "error", "cancelled"}

        if self.done_actions:
            self.done_actions.opacity = 1 if status == "finished" else 0


class DownloadManagerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_tab = "active"
        self.tab_buttons: dict[str, Button] = {}
        self.content_box: Optional[BoxLayout] = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        title = Label(
            text="Downloads",
            size_hint_y=None,
            height=dp(42),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="20sp",
        )
        root.add_widget(title)

        subtitle = Label(
            text="Active, completed, and failed downloads",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        subtitle.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(subtitle)

        tabs = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        for tab in ("active", "completed", "failed"):
            btn = Button(
                text=tab.capitalize(),
                background_normal="",
                background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            )
            btn.bind(on_release=lambda _btn, current=tab: self._set_tab(current))
            self.tab_buttons[tab] = btn
            tabs.add_widget(btn)
        root.add_widget(tabs)

        scroll = ScrollView(size_hint=(1, 1))
        self.content_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, 0, 0, dp(10)))
        self.content_box.bind(minimum_height=self.content_box.setter("height"))
        scroll.add_widget(self.content_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_pre_enter(self, *_args):
        self._refresh_tabs()
        self.refresh()

    def _set_tab(self, tab: str):
        self.active_tab = tab
        self._refresh_tabs()
        self.refresh()

    def _refresh_tabs(self):
        for key, btn in self.tab_buttons.items():
            if key == self.active_tab:
                btn.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
                btn.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)

    def refresh(self):
        if not self.content_box:
            return

        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        self.content_box.clear_widgets()

        rows: list[dict]
        if self.active_tab == "active":
            rows = [app.active_download] if app.active_download else []
        elif self.active_tab == "completed":
            rows = [item for item in reversed(app.download_history) if item.get("status") == "Finished"]
        else:
            rows = [item for item in reversed(app.download_history) if item.get("status") in {"Failed", "Cancelled"}]

        if not rows:
            empty = Label(
                text="No items.",
                size_hint_y=None,
                height=dp(40),
                color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
            )
            self.content_box.add_widget(empty)
            return

        for item in rows[:30]:
            status = item.get("status", "")
            title = item.get("title", "Unknown")
            line = title if self.active_tab == "active" else f"[{item.get('time', '')}] {status}: {title}"
            card = Label(
                text=line,
                size_hint_y=None,
                height=dp(48),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
                halign="left",
                valign="middle",
            )
            card.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.content_box.add_widget(card)


class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.box: Optional[BoxLayout] = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        title = Label(
            text="History",
            size_hint_y=None,
            height=dp(42),
            color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            bold=True,
            font_size="20sp",
        )
        root.add_widget(title)

        subtitle = Label(
            text="Recent actions and outcomes",
            size_hint_y=None,
            height=dp(20),
            color=_hex_to_rgba(Colors.DARK_TEXT_SECONDARY),
            halign="left",
            valign="middle",
            font_size="11sp",
        )
        subtitle.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
        root.add_widget(subtitle)

        scroll = ScrollView(size_hint=(1, 1))
        self.box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, 0, 0, dp(10)))
        self.box.bind(minimum_height=self.box.setter("height"))
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        self.add_widget(root)

    def on_pre_enter(self, *_args):
        self.refresh()

    def refresh(self):
        if not self.box:
            return

        app: TubeGrabApp = KivyApp.get_running_app()  # type: ignore[assignment]
        self.box.clear_widgets()

        if not app.download_history:
            empty = Label(
                text="No history yet.",
                size_hint_y=None,
                height=dp(36),
                color=_hex_to_rgba(Colors.DARK_TEXT_MUTED),
            )
            self.box.add_widget(empty)
            return

        for item in reversed(app.download_history[-40:]):
            icon = "[OK]" if item.get("status") == "Finished" else "[X]"
            row = Label(
                text=f"{icon} {item.get('time', '')}  {item.get('status', '')}  {item.get('title', '')}",
                size_hint_y=None,
                height=dp(44),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
                halign="left",
                valign="middle",
            )
            row.bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))
            self.box.add_widget(row)


class TubeGrabApp(KivyApp):
    """Multi-screen TubeGrab application."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = DownloadEngine()
        self.app_version = self._load_app_version()
        self.video_info: Optional[VideoInfo] = None
        self.selected_format: Optional[FormatOption] = None
        self.download_full_playlist = False
        self.playlist_mode = "single"

        self.status_message = "Ready"
        self.loading_modal: Optional[ModalView] = None

        self.last_download_url = ""
        self.last_download_format: Optional[FormatOption] = None
        self.last_download_full_playlist = False
        self.pause_requested = False
        self.is_paused = False

        self.active_download: Optional[dict] = None

        base_dir = os.path.dirname(__file__)
        self.history_path = os.path.join(base_dir, "download_history.json")
        self.recent_links_path = os.path.join(base_dir, "recent_links.json")
        self.download_history = self._load_json_list(self.history_path)
        self.recent_links = self._load_json_list(self.recent_links_path)

        self.screen_manager: Optional[ScreenManager] = None
        self.bottom_nav_buttons: dict[str, Button] = {}

    def _load_app_version(self) -> str:
        spec_path = os.path.join(os.path.dirname(__file__), "buildozer.spec")
        if not os.path.exists(spec_path):
            return "dev"

        try:
            with open(spec_path, "r", encoding="utf-8") as fp:
                for line in fp:
                    clean = line.strip()
                    if clean.lower().startswith("version") and "=" in clean:
                        return clean.split("=", 1)[1].strip() or "dev"
        except Exception:
            return "dev"
        return "dev"

    @staticmethod
    def _load_json_list(path: str) -> list:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _save_json_list(path: str, data: list):
        try:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def build(self):
        self.title = "TubeGrab"
        if Window is not None:
            Window.minimum_width = dp(360)
            Window.minimum_height = dp(640)
            Window.clearcolor = _hex_to_rgba(Colors.DARK_BG_PRIMARY)

        root = AppScaffold(orientation="vertical", spacing=0)

        self.screen_manager = ScreenManager(transition=FadeTransition(duration=0.15))
        self.screen_manager.add_widget(HomeScreen(name="home"))
        self.screen_manager.add_widget(MediaInfoScreen(name="media_info"))
        self.screen_manager.add_widget(FormatSelectionScreen(name="format_select"))
        self.screen_manager.add_widget(ActiveDownloadScreen(name="active_download"))
        self.screen_manager.add_widget(DownloadManagerScreen(name="downloads"))
        self.screen_manager.add_widget(HistoryScreen(name="history"))
        root.add_widget(self.screen_manager)

        nav = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(8), padding=[dp(10), dp(8), dp(10), dp(8)])
        for name, target in (("Home", "home"), ("Downloads", "downloads"), ("History", "history")):
            btn = Button(
                text=name,
                background_normal="",
                background_color=_hex_to_rgba(Colors.DARK_BG_CARD),
                color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY),
            )
            btn.bind(on_release=lambda _btn, screen=target: self.go_to(screen))
            self.bottom_nav_buttons[target] = btn
            nav.add_widget(btn)
        root.add_widget(nav)

        self._refresh_nav("home")
        return root

    def _refresh_nav(self, active: str):
        for key, btn in self.bottom_nav_buttons.items():
            if key == active:
                btn.background_color = _hex_to_rgba(Colors.ACCENT_BLUE)
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = _hex_to_rgba(Colors.DARK_BG_CARD)
                btn.color = _hex_to_rgba(Colors.DARK_TEXT_PRIMARY)

    def go_to(self, screen_name: str):
        if self.screen_manager:
            self.screen_manager.current = screen_name
        self._refresh_nav(screen_name if screen_name in self.bottom_nav_buttons else "home")

    def set_status(self, message: str):
        self.status_message = message

    def _show_loading(self, message: str):
        self._close_loading()
        modal = ModalView(auto_dismiss=False, size_hint=(0.85, 0.22), background_color=(0.02, 0.02, 0.08, 0.9))
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        label = Label(text=message, color=_hex_to_rgba(Colors.DARK_TEXT_PRIMARY), bold=True)
        body.add_widget(label)
        modal.add_widget(body)
        modal.open()
        self.loading_modal = modal

    def _close_loading(self):
        if self.loading_modal is not None:
            self.loading_modal.dismiss()
            self.loading_modal = None

    def start_fetch(self, url: str):
        if not url:
            self.set_status("Paste a URL first.")
            return

        self._show_loading("Fetching video information...")
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url: str):
        try:
            info = self.engine.fetch_info(url)
            Clock.schedule_once(lambda _dt: self._apply_fetch(info, url), 0)
        except Exception as exc:
            Clock.schedule_once(lambda _dt, err=str(exc): self._fetch_error(err), 0)

    def _apply_fetch(self, info: VideoInfo, url: str):
        self._close_loading()
        self.video_info = info
        self.selected_format = info.formats[0] if info.formats else None

        if info.is_playlist:
            self.playlist_mode = "full"
            self.download_full_playlist = True
        else:
            self.playlist_mode = "single"
            self.download_full_playlist = False

        self._add_recent_link(url)
        self.go_to("media_info")

    def _fetch_error(self, message: str):
        self._close_loading()
        self.set_status(f"Fetch failed: {message}")

    def _add_recent_link(self, url: str):
        clean = url.strip()
        if not clean:
            return
        items = [clean] + [x for x in self.recent_links if x != clean]
        self.recent_links = items[:20]
        self._save_json_list(self.recent_links_path, self.recent_links)

    def _get_download_url(self) -> str:
        if self.video_info and self.video_info.url:
            return self.video_info.url

        home = self.screen_manager.get_screen("home") if self.screen_manager else None
        if isinstance(home, HomeScreen) and home.url_input:
            return (home.url_input.text or "").strip()
        return ""

    def start_download(self, output_dir: str):
        url = self._get_download_url()
        if not url:
            self.set_status("No URL to download.")
            return
        if self.selected_format is None:
            self.set_status("Select a format first.")
            return

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as exc:
            self.set_status(f"Invalid path: {exc}")
            return

        try:
            self.engine.download(
                url=url,
                format_option=self.selected_format,
                output_dir=output_dir,
                download_full_playlist=self.download_full_playlist,
                playlist_title=(self.video_info.playlist_title if self.video_info else ""),
                progress_callback=self._on_engine_progress,
            )
        except Exception as exc:
            self.set_status(f"Download start failed: {exc}")
            return

        title = self.video_info.title if self.video_info else "Unknown"
        if self.video_info and self.video_info.is_playlist and self.download_full_playlist:
            title = self.video_info.playlist_title or title

        self.active_download = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "title": title,
            "format": self.selected_format.label,
            "status": "Active",
            "path": output_dir,
        }

        self.last_download_url = url
        self.last_download_format = self.selected_format
        self.last_download_full_playlist = self.download_full_playlist
        self.pause_requested = False
        self.is_paused = False

        active = self.screen_manager.get_screen("active_download") if self.screen_manager else None
        if isinstance(active, ActiveDownloadScreen) and active.title_label:
            active.title_label.text = title

        self.go_to("active_download")
        self._refresh_manager()

    def toggle_pause_resume(self):
        if self.engine.is_busy:
            self.pause_requested = True
            self.engine.cancel()
            return

        if not self.is_paused:
            return

        if not self.last_download_url or self.last_download_format is None:
            return

        output_dir = self.engine.default_output_dir
        try:
            self.engine.download(
                url=self.last_download_url,
                format_option=self.last_download_format,
                output_dir=output_dir,
                download_full_playlist=self.last_download_full_playlist,
                playlist_title=(self.video_info.playlist_title if self.video_info else ""),
                progress_callback=self._on_engine_progress,
            )
        except Exception:
            return

        self.pause_requested = False
        self.is_paused = False

    def cancel_download(self):
        self.engine.cancel()

    def _on_engine_progress(self, progress: DownloadProgress):
        snapshot = {
            "status": progress.status,
            "percent": float(progress.percent),
            "speed": progress.speed,
            "eta": progress.eta,
            "downloaded": progress.downloaded,
            "total": progress.total,
            "error_message": progress.error_message,
            "is_paused": self.is_paused,
        }
        Clock.schedule_once(lambda _dt, data=snapshot: self._apply_progress(data), 0)

    def _apply_progress(self, data: dict):
        status = data.get("status", "idle")

        active = self.screen_manager.get_screen("active_download") if self.screen_manager else None
        if isinstance(active, ActiveDownloadScreen):
            data["is_paused"] = self.is_paused
            active.update_progress(data)

        if status == "cancelled":
            if self.pause_requested:
                self.pause_requested = False
                self.is_paused = True
                if isinstance(active, ActiveDownloadScreen):
                    data["is_paused"] = True
                    active.update_progress(data)
                return
            self._finish_active("Cancelled")
            return

        if status == "finished":
            self._finish_active("Finished")
            return

        if status == "error":
            self._finish_active("Failed", details=data.get("error_message", ""))

    def _finish_active(self, final_status: str, details: str = ""):
        self.is_paused = False
        if self.active_download:
            entry = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "title": self.active_download.get("title", "Unknown"),
                "format": self.active_download.get("format", "Unknown"),
                "status": final_status,
                "path": self.active_download.get("path", self.engine.default_output_dir),
                "details": details,
            }
            self.download_history.append(entry)
            self.download_history = self.download_history[-80:]
            self._save_json_list(self.history_path, self.download_history)

        self.active_download = None
        self._refresh_manager()

        history = self.screen_manager.get_screen("history") if self.screen_manager else None
        if isinstance(history, HistoryScreen):
            history.refresh()

    def _refresh_manager(self):
        manager = self.screen_manager.get_screen("downloads") if self.screen_manager else None
        if isinstance(manager, DownloadManagerScreen):
            manager.refresh()


__all__ = ["TubeGrabApp"]
