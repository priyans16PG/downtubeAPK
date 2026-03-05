"""
Theme & Styling Constants for the YouTube Downloader.
Provides dark and light color palettes, fonts, and spacing.
"""


class Colors:
    """Color palette constants."""

    # ── Dark Theme ──────────────────────────────────────────────
    DARK_BG_PRIMARY = "#0f0f14"
    DARK_BG_SECONDARY = "#1a1a24"
    DARK_BG_TERTIARY = "#24243a"
    DARK_BG_CARD = "#1e1e30"
    DARK_BG_INPUT = "#16162a"
    DARK_BG_HOVER = "#2a2a44"
    DARK_BORDER = "#2e2e4a"
    DARK_TEXT_PRIMARY = "#f0f0f8"
    DARK_TEXT_SECONDARY = "#a0a0c0"
    DARK_TEXT_MUTED = "#6a6a90"

    # ── Light Theme ─────────────────────────────────────────────
    LIGHT_BG_PRIMARY = "#f5f5fa"
    LIGHT_BG_SECONDARY = "#ffffff"
    LIGHT_BG_TERTIARY = "#eaeaf0"
    LIGHT_BG_CARD = "#ffffff"
    LIGHT_BG_INPUT = "#f0f0f5"
    LIGHT_BG_HOVER = "#e0e0ea"
    LIGHT_BORDER = "#d0d0e0"
    LIGHT_TEXT_PRIMARY = "#1a1a2e"
    LIGHT_TEXT_SECONDARY = "#5a5a7a"
    LIGHT_TEXT_MUTED = "#9090a8"

    # ── Accent Colors ───────────────────────────────────────────
    ACCENT_RED = "#ff2d55"
    ACCENT_RED_HOVER = "#ff4d70"
    ACCENT_RED_DARK = "#cc1a3e"
    ACCENT_BLUE = "#4a7dff"
    ACCENT_BLUE_HOVER = "#6a95ff"
    ACCENT_GREEN = "#34d399"
    ACCENT_GREEN_HOVER = "#50e0aa"
    ACCENT_ORANGE = "#ff9f43"
    ACCENT_PURPLE = "#a855f7"
    ACCENT_YELLOW = "#fbbf24"

    # ── Status ──────────────────────────────────────────────────
    SUCCESS = "#34d399"
    WARNING = "#fbbf24"
    ERROR = "#ff4757"
    INFO = "#4a7dff"

    # ── Gradient endpoints (for canvas-based gradients) ────────
    GRADIENT_START = "#ff2d55"
    GRADIENT_END = "#ff6b81"


class Fonts:
    """Font configurations."""
    FAMILY = "Segoe UI"
    FAMILY_MONO = "Cascadia Code"

    TITLE = (FAMILY, 22, "bold")
    HEADING = (FAMILY, 16, "bold")
    SUBHEADING = (FAMILY, 14, "bold")
    BODY = (FAMILY, 13)
    BODY_BOLD = (FAMILY, 13, "bold")
    SMALL = (FAMILY, 11)
    SMALL_BOLD = (FAMILY, 11, "bold")
    TINY = (FAMILY, 10)
    MONO = (FAMILY_MONO, 12)
    BUTTON = (FAMILY, 13, "bold")
    ICON = ("Segoe UI Emoji", 16)


class Spacing:
    """Consistent spacing & sizing."""
    PAD_XS = 4
    PAD_SM = 8
    PAD_MD = 14
    PAD_LG = 20
    PAD_XL = 28

    CORNER_RADIUS = 10
    CORNER_RADIUS_SM = 6
    CORNER_RADIUS_LG = 14

    BUTTON_HEIGHT = 40
    INPUT_HEIGHT = 42
    CARD_PAD = 16

    PROGRESS_HEIGHT = 8
    THUMBNAIL_WIDTH = 320
    THUMBNAIL_HEIGHT = 180


class Theme:
    """Resolves colors based on current theme mode."""

    def __init__(self, mode: str = "dark"):
        self.mode = mode

    @property
    def is_dark(self) -> bool:
        return self.mode == "dark"

    def toggle(self):
        self.mode = "light" if self.is_dark else "dark"

    # Convenience accessors
    @property
    def bg_primary(self):
        return Colors.DARK_BG_PRIMARY if self.is_dark else Colors.LIGHT_BG_PRIMARY

    @property
    def bg_secondary(self):
        return Colors.DARK_BG_SECONDARY if self.is_dark else Colors.LIGHT_BG_SECONDARY

    @property
    def bg_tertiary(self):
        return Colors.DARK_BG_TERTIARY if self.is_dark else Colors.LIGHT_BG_TERTIARY

    @property
    def bg_card(self):
        return Colors.DARK_BG_CARD if self.is_dark else Colors.LIGHT_BG_CARD

    @property
    def bg_input(self):
        return Colors.DARK_BG_INPUT if self.is_dark else Colors.LIGHT_BG_INPUT

    @property
    def bg_hover(self):
        return Colors.DARK_BG_HOVER if self.is_dark else Colors.LIGHT_BG_HOVER

    @property
    def border(self):
        return Colors.DARK_BORDER if self.is_dark else Colors.LIGHT_BORDER

    @property
    def text_primary(self):
        return Colors.DARK_TEXT_PRIMARY if self.is_dark else Colors.LIGHT_TEXT_PRIMARY

    @property
    def text_secondary(self):
        return Colors.DARK_TEXT_SECONDARY if self.is_dark else Colors.LIGHT_TEXT_SECONDARY

    @property
    def text_muted(self):
        return Colors.DARK_TEXT_MUTED if self.is_dark else Colors.LIGHT_TEXT_MUTED
