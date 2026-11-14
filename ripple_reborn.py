"""
Ripple Reborn - AFK macro (Windows).

Layout and feature set follow the screenshots you sent:
  main window (Start / Settings / Pause, stats, 5 toggles, session feed)
  settings window with Match / Options / Discord / Tools tabs
  hotkeys Ctrl+Alt+ 1 start, 2 stop, P pause, K kill, 3..9 tools

Needs: Windows, Python 3.10+, Pillow, pytesseract, requests, and the Tesseract OCR
program installed (https://github.com/UB-Mannheim/tesseract/wiki).
Fortnite must be in WINDOWED mode, 1280x720.

NOTE: automating Fortnite input is against Epic's rules and can get an account
banned. Use at your own risk, preferably on an account you can afford to lose.
"""
import configparser
import ctypes
import io
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import ttk

try:
    from PIL import Image, ImageGrab, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageGrab = ImageOps = None
try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None
try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

VERSION = "1.0"
APP = "RippleReborn"
IS_WIN = sys.platform == "win32"
TARGET_W, TARGET_H = 1280, 720

DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.ini")
LOG_FILE = os.path.join(DATA_DIR, "log.txt")
DEBUG_DIR = os.path.join(DATA_DIR, "debug")
os.makedirs(DEBUG_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# Defaults.  Points are (x, y) and zones (x1, y1, x2, y2), all as fractions of
# the Fortnite client area, so they survive moving the window.  Re-calibrate
# them in Settings > Tools (Calibrate) if a click lands in the wrong spot.
# ----------------------------------------------------------------------------
POINTS = {
    "play": (0.100, 0.668),          # lobby PLAY button (fallback if OCR cannot find it)
    "mode": (0.288, 0.668),          # the "..." next to PLAY (opens the mode list)
    "quads": (0.200, 0.400),         # "Quads" entry in the mode list
    "leave_menu": (0.500, 0.640),    # "Leave match" in the Esc menu
    "leave_confirm": (0.420, 0.600), # confirm-leave button
    "play_again": (0.880, 0.940),    # play again on the results screen
}
ZONES = {
    "players": (0.905, 0.030, 0.985, 0.075),   # players-left counter
    "lobby": (0.000, 0.000, 1.000, 0.120),     # top menu bar (PLAY SHOP LOCKER ...)
    "results": (0.300, 0.050, 0.700, 0.200),   # results / victory header
    "banner": (0.250, 0.200, 0.750, 0.330),    # item-found banner
    "feed": (0.010, 0.350, 0.300, 0.600),      # elimination / reboot feed
}
POINTS_VERSION = "3"
CAL_NAMES = list(POINTS) + [f"{z}_{c}" for z in ZONES for c in ("tl", "br")]

DEFAULTS = {
    "main": {
        "movement": "1", "afk_messages": "0", "reboot_thanks": "0",
        "play_again": "0", "leave_if_team_out": "1",
    },
    "match": {
        "leave_at_players": "20", "wait_before_jump": "60", "proceed_anyway": "60",
        "afk_second_msg": "40", "max_match_min": "9", "landing_wait": "40",
        "lobby_settle": "10",
    },
    "options": {
        "ocr_lobby": "1", "debug_shots": "0", "always_on_top": "1", "set_quads": "1",
        "pickaxe_key": "1", "gun_key": "2", "look_up": "150",
    },
    "discord": {"webhook": "", "shot_on_find": "1"},
    "text": {
        "afk1": "brb, afk for a minute", "afk2": "still afk, back soon",
        "thanks": "ty for the reboot!",
        "banner_words": "gizmo", "reboot_words": "reboot", "team_out_words": "eliminated",
    },
    "points": {k: f"{v[0]:.4f},{v[1]:.4f}" for k, v in POINTS.items()},
}
for _z, _r in ZONES.items():
    DEFAULTS["points"][f"{_z}_tl"] = f"{_r[0]:.4f},{_r[1]:.4f}"
    DEFAULTS["points"][f"{_z}_br"] = f"{_r[2]:.4f},{_r[3]:.4f}"

SCALE = 1.0


def S(n):
    """Scale a pixel size for high-DPI displays."""
    return max(1, int(round(n * SCALE)))


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def dark_titlebar(win, _again=True):
    """Dark title bar on Windows 10/11 (the default one is white)."""
    if not IS_WIN:
        return
    try:
        win.update_idletasks()
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi
        one = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old id)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(one), 4)
        for attr, rgb in ((35, 0x140B0D), (36, 0xFAF0F2)):  # Win11: caption / text colour (BGR)
            c = ctypes.c_int(rgb)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c), 4)
        # SWP_NOMOVE|NOSIZE|NOZORDER|NOACTIVATE|FRAMECHANGED: repaint the frame
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
        if _again:  # once more after the window is really on screen
            for ms in (60, 350):
                win.after(ms, lambda: dark_titlebar(win, False))
    except Exception:
        pass


def set_icon(win):
    try:
        win.iconphoto(True, tk.PhotoImage(file=resource("logo.png")))
        if IS_WIN:
            win.iconbitmap(resource("logo.ico"))
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Colours (match the dark purple look of the screenshots)
# ----------------------------------------------------------------------------
BG = "#0d0b14"
PANEL = "#17132a"
LINE = "#2a2540"
FG = "#f2f0fa"
DIM = "#6f6a8a"
ACCENT = "#7c2cf0"
ACCENT_HI = "#9448ff"
PINK = "#d010e0"
OFF = "#26223a"
GOOD = "#6fe08a"
BAD = "#ff6b6b"
FONT = ("Segoe UI", 10)
FONT_S = ("Segoe UI", 9)
FONT_B = ("Segoe UI", 11, "bold")
MONO = ("Consolas", 9)


# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
class Settings:
    def __init__(self):
        self.cp = configparser.ConfigParser(interpolation=None)
        self.cp.read_dict(DEFAULTS)
        self.loaded = False
        if os.path.exists(SETTINGS_FILE):
            try:
                self.cp.read(SETTINGS_FILE, encoding="utf-8")
                self.loaded = True
            except configparser.Error:
                pass
        self.lock = threading.Lock()
        raw = configparser.ConfigParser(interpolation=None)
        try:
            raw.read(SETTINGS_FILE, encoding="utf-8")
        except configparser.Error:
            pass
        if raw.get("meta", "points_version", fallback="") != POINTS_VERSION:
            # positions from older builds were guesses: reset them once
            for k, v in DEFAULTS["points"].items():
                self.cp.set("points", k, v)
            if not self.cp.has_section("meta"):
                self.cp.add_section("meta")
            self.cp.set("meta", "points_version", POINTS_VERSION)
            if self.loaded:
                try:
                    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                        self.cp.write(f)
                except OSError:
                    pass

    def get(self, sec, key):
        return self.cp.get(sec, key, fallback=DEFAULTS.get(sec, {}).get(key, ""))

    def int(self, sec, key):
        try:
            return int(float(self.get(sec, key)))
        except ValueError:
            return int(float(DEFAULTS[sec][key]))

    def bool(self, sec, key):
        return self.get(sec, key) in ("1", "true", "True", "yes")

    def set(self, sec, key, value):
        if isinstance(value, bool):
            value = "1" if value else "0"
        with self.lock:
            if not self.cp.has_section(sec):
                self.cp.add_section(sec)
            self.cp.set(sec, key, str(value))
            try:
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    self.cp.write(f)
            except OSError:
                pass

    def point(self, name):
        try:
            x, y = self.get("points", name).split(",")
            return float(x), float(y)
        except ValueError:
            d = DEFAULTS["points"][name].split(",")
            return float(d[0]), float(d[1])

    def zone(self, name):
        x1, y1 = self.point(f"{name}_tl")
        x2, y2 = self.point(f"{name}_br")
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


# ----------------------------------------------------------------------------
# Windows helpers: window finding, screen grab, SendInput
# ----------------------------------------------------------------------------
if IS_WIN:
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


SCAN = {
    "esc": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08,
    "8": 0x09, "9": 0x0A, "0": 0x0B, "tab": 0x0F, "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13,
    "t": 0x14, "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19, "enter": 0x1C,
    "ctrl": 0x1D, "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23, "j": 0x24,
    "k": 0x25, "l": 0x26, "shift": 0x2A, "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
    "n": 0x31, "m": 0x32, "space": 0x39, "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E,
    "f5": 0x3F, "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44, "f11": 0x57,
    "f12": 0x58,
}


def _send(inp):
    if IS_WIN:
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def key_event(name, down):
    sc = SCAN.get(str(name).lower())
    if sc is None:
        return
    inp = INPUT(type=1)
    inp.u.ki = KEYBDINPUT(0, sc, 0x0008 | (0 if down else 0x0002), 0, 0)
    _send(inp)


def tap(name, hold=0.06):
    key_event(name, True)
    time.sleep(hold)
    key_event(name, False)


def type_text(text, delay=0.02):
    for ch in text:
        for flags in (0x0004, 0x0004 | 0x0002):  # KEYEVENTF_UNICODE down / up
            inp = INPUT(type=1)
            inp.u.ki = KEYBDINPUT(0, ord(ch), flags, 0, 0)
            _send(inp)
        time.sleep(delay)


def mouse_button(down_flag, up_flag, hold=0.06):
    for fl in (down_flag, up_flag):
        inp = INPUT(type=0)
        inp.u.mi = MOUSEINPUT(0, 0, 0, fl, 0, 0)
        _send(inp)
        time.sleep(hold)


def move_abs(x, y):
    """Move the cursor with a real mouse-move event (games ignore silent SetCursorPos)."""
    if not IS_WIN:
        return
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    nx = int((x - vx) * 65535 / max(1, vw - 1))
    ny = int((y - vy) * 65535 / max(1, vh - 1))
    inp = INPUT(type=0)
    inp.u.mi = MOUSEINPUT(nx, ny, 0, 0x0001 | 0x8000 | 0x4000, 0, 0)
    _send(inp)


def click(x, y):
    if not IS_WIN:
        return
    move_abs(x - 8, y - 5)
    time.sleep(0.10)
    move_abs(x, y)
    time.sleep(0.25)
    mouse_button(0x0002, 0x0004, hold=0.10)


def mouse_move_rel(dx, dy, steps=12, total_time=0.25):
    """Relative move in small steps so the game's raw-input camera follows."""
    sx = dx / steps
    sy = dy / steps
    ax = ay = 0.0
    for _ in range(steps):
        ax += sx
        ay += sy
        ix, iy = int(ax), int(ay)
        ax -= ix
        ay -= iy
        inp = INPUT(type=0)
        inp.u.mi = MOUSEINPUT(ix, iy, 0, 0x0001, 0, 0)
        _send(inp)
        time.sleep(total_time / steps)


def cursor_pos():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def find_fortnite():
    if not IS_WIN:
        return None
    found = []
    buf = ctypes.create_unicode_buffer(256)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            user32.GetClassNameW(hwnd, buf, 256)
            cls = buf.value
            user32.GetWindowTextW(hwnd, buf, 256)
            if cls == "UnrealWindow" and buf.value.strip().startswith("Fortnite"):
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def own_window_rects():
    """Screen rectangles of this program's visible windows."""
    if not IS_WIN:
        return []
    pid = os.getpid()
    rects = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid:
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                if r.right - r.left > 20 and r.bottom - r.top > 20:
                    rects.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumWindows(cb, 0)
    return rects


def client_rect(hwnd):
    """Screen-space (x, y, w, h) of the window's client area."""
    rc = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rc.right - rc.left, rc.bottom - rc.top


def position_fortnite(hwnd):
    """Move Fortnite to the top-left and size its client area to 1280x720."""
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    outer = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(outer))
    _, _, cw, ch = client_rect(hwnd)
    ow = (outer.right - outer.left) - cw + TARGET_W
    oh = (outer.bottom - outer.top) - ch + TARGET_H
    user32.SetWindowPos(hwnd, 0, 0, 0, ow, oh, 0x0040)  # SWP_SHOWWINDOW
    time.sleep(0.4)
    return client_rect(hwnd)


def focus(hwnd):
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)


def grab(box=None):
    if ImageGrab is None:
        raise RuntimeError("Pillow is not installed")
    return ImageGrab.grab(bbox=box, all_screens=True)


# ----------------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------------
def setup_tesseract():
    if pytesseract is None:
        return False
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    for p in (resource(os.path.join("tesseract", "tesseract.exe")),  # bundled inside the exe
              os.path.join(here, "tesseract", "tesseract.exe"),
              r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            os.environ["TESSDATA_PREFIX"] = os.path.join(os.path.dirname(p), "tessdata")
            return True
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


_WINOCR = None      # None = not tried yet, False = unavailable, tuple = ready
_tls = threading.local()
OCR_ERROR = ""


def _load_winocr():
    """Windows 10/11 ships an OCR engine; use it so no extra program is needed."""
    global _WINOCR
    if _WINOCR is None:
        try:
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.graphics.imaging import BitmapDecoder
            from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
            _WINOCR = (OcrEngine, BitmapDecoder, InMemoryRandomAccessStream, DataWriter)
        except Exception:
            _WINOCR = False
    return _WINOCR


def ocr_ready():
    return bool(_load_winocr()) or setup_tesseract()


async def _winocr_async(png, want_words=False):
    OcrEngine, BitmapDecoder, Stream, Writer = _WINOCR
    stream = Stream()
    w = Writer(stream)
    w.write_bytes(png)
    await w.store_async()
    w.detach_stream()
    stream.seek(0)
    dec = await BitmapDecoder.create_async(stream)
    bmp = await dec.get_software_bitmap_async()
    eng = OcrEngine.try_create_from_user_profile_languages()
    res = await eng.recognize_async(bmp)
    if want_words:
        out = []
        for line in res.lines:
            for wd in line.words:
                r = wd.bounding_rect
                out.append((wd.text, r.x, r.y, r.width, r.height))
        return out
    return res.text


def _winocr(img):
    global OCR_ERROR
    import asyncio
    if not getattr(_tls, "init", False):
        _tls.init = True
        try:
            from winrt.runtime import init_apartment
            init_apartment()
        except Exception:
            pass
    buf = io.BytesIO()
    img.save(buf, "PNG")
    try:
        return asyncio.run(_winocr_async(buf.getvalue())).strip()
    except Exception as e:
        OCR_ERROR = str(e)
        return ""


def _winocr_words(img):
    global OCR_ERROR
    import asyncio
    if not getattr(_tls, "init", False):
        _tls.init = True
        try:
            from winrt.runtime import init_apartment
            init_apartment()
        except Exception:
            pass
    buf = io.BytesIO()
    img.save(buf, "PNG")
    try:
        return asyncio.run(_winocr_async(buf.getvalue(), True))
    except Exception as e:
        OCR_ERROR = str(e)
        return []


def ocr_words(img, inv=False):
    """[(text, x, y, w, h)] with positions in the pixels of `img`."""
    sc = min(2.0, 2500.0 / max(img.size))
    if _load_winocr():
        g = ImageOps.autocontrast(ImageOps.grayscale(img))
        g = g.resize((max(1, int(g.width * sc)), max(1, int(g.height * sc))), Image.LANCZOS)
        if inv:
            g = ImageOps.invert(g)
        return [(t, x / sc, y / sc, w / sc, h / sc) for t, x, y, w, h in _winocr_words(g)]
    if pytesseract is None:
        return []
    try:
        d = pytesseract.image_to_data(prep(img, inv), config="--psm 11",
                                      output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    out = []
    for i, t in enumerate(d["text"]):
        if t.strip():
            out.append((t, d["left"][i] / 3, d["top"][i] / 3, d["width"][i] / 3, d["height"][i] / 3))
    return out


def norm_word(t):
    return re.sub(r"[^A-Z0-9-]", "", t.upper())


def prep(img, invert=False, binarize=True):
    g = ImageOps.grayscale(img)
    g = g.resize((g.width * 3, g.height * 3), Image.LANCZOS)
    g = ImageOps.autocontrast(g)
    if invert:
        g = ImageOps.invert(g)
    if not binarize:
        # Windows OCR likes a little white border and plain grey text
        return ImageOps.expand(g, border=12, fill=255 if invert else 0)
    return g.point(lambda v: 255 if v > 150 else 0)


def _read(img, inv, numeric):
    if _load_winocr():
        return _winocr(prep(img, inv, binarize=False))
    if pytesseract is None:
        return ""
    try:
        cfg = "--psm 7 -c tessedit_char_whitelist=0123456789" if numeric else "--psm 6"
        return pytesseract.image_to_string(prep(img, inv), config=cfg).strip()
    except Exception:
        return ""


def ocr_text(img):
    best = ""
    for inv in (False, True):
        t = _read(img, inv, False)
        if len(t) > len(best):
            best = t
    return best


def ocr_number(img):
    for inv in (False, True):
        m = re.search(r"\d{1,3}", _read(img, inv, True))
        if m:
            return int(m.group())
    return None


# ----------------------------------------------------------------------------
# The bot
# ----------------------------------------------------------------------------
class Stopped(Exception):
    pass


class Bot:
    def __init__(self, settings, ui_queue):
        self.s = settings
        self.q = ui_queue
        self.running = False
        self.paused = False
        self.stop_flag = threading.Event()
        self.thread = None
        self.hwnd = None
        self.stats = dict(matches=0, found=0, recoveries=0, gizmos=0, players=None, start=0.0,
                          paused_total=0.0)
        self._pause_started = 0.0

    # --- plumbing ---------------------------------------------------------
    def log(self, msg):
        line = f"{time.strftime('%H:%M:%S')}  {msg}"
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        self.q.put(("log", line))

    def status(self, headline, detail=""):
        self.q.put(("status", headline, detail))

    def push_stats(self):
        self.q.put(("stats", dict(self.stats)))

    def sleep(self, secs):
        end = time.time() + secs
        while True:
            self.check()
            left = end - time.time()
            if left <= 0:
                return
            time.sleep(min(0.1, left))

    def check(self):
        if self.stop_flag.is_set():
            raise Stopped()
        while self.paused:
            if self.stop_flag.is_set():
                raise Stopped()
            time.sleep(0.1)

    # --- control ----------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.stop_flag.clear()
        self.paused = False
        self.running = True
        self.stats.update(matches=0, found=0, recoveries=0, gizmos=0, players=None,
                          start=time.time(), paused_total=0.0)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.q.put(("state", "RUNNING"))

    def stop(self):
        self.stop_flag.set()
        self.paused = False

    def toggle_pause(self):
        if not self.running:
            return
        if self.paused:
            self.stats["paused_total"] += time.time() - self._pause_started
            self.paused = False
            self.q.put(("state", "RUNNING"))
            self.log("Resumed.")
        else:
            self._pause_started = time.time()
            self.paused = True
            self.q.put(("state", "PAUSED"))
            self.log("Paused.")

    def afk_seconds(self):
        if not self.running:
            return 0
        paused = self.stats["paused_total"] + (time.time() - self._pause_started if self.paused else 0)
        return int(time.time() - self.stats["start"] - paused)

    # --- geometry / capture ----------------------------------------------
    def rect(self):
        self.hwnd = find_fortnite()
        if not self.hwnd:
            raise RuntimeError("Fortnite window not found. Open Fortnite in windowed mode.")
        return client_rect(self.hwnd)

    def abs_point(self, name):
        x, y, w, h = self.rect()
        fx, fy = self.s.point(name)
        return x + fx * w, y + fy * h

    def zone_img(self, name):
        x, y, w, h = self.rect()
        x1, y1, x2, y2 = self.s.zone(name)
        box = (int(x + x1 * w), int(y + y1 * h), int(x + x2 * w), int(y + y2 * h))
        img = grab(box)
        if self.s.bool("options", "debug_shots"):
            img.save(os.path.join(DEBUG_DIR, f"{name}_{int(time.time())}.png"))
        return img

    def full_shot(self):
        x, y, w, h = self.rect()
        return grab((x, y, x + w, y + h))

    def click_abs(self, x, y):
        focus(self.hwnd or find_fortnite())
        click(x, y)

    def click_point(self, name):
        x, y = self.abs_point(name)
        self.click_abs(x, y)

    def scan_words(self, region=None, inv=False):
        """OCR a part of the game (fractions) -> words with absolute screen positions."""
        x, y, w, h = self.rect()
        fx1, fy1, fx2, fy2 = region or (0.0, 0.0, 1.0, 1.0)
        box = (int(x + fx1 * w), int(y + fy1 * h), int(x + fx2 * w), int(y + fy2 * h))
        img = grab(box)
        mine = own_window_rects()
        out = []
        for t, wx, wy, ww, wh in ocr_words(img, inv):
            cx, cy = box[0] + wx + ww / 2, box[1] + wy + wh / 2
            if any(l <= cx <= r and tp <= cy <= b for l, tp, r, b in mine):
                continue  # text from the bot's own window, not Fortnite
            out.append(dict(t=norm_word(t), raw=t, cx=cx, cy=cy, h=wh,
                            fx=(cx - x) / w, fy=(cy - y) / h))
        return out

    def find_text(self, targets, region=None, pick="largest", min_fy=0.0):
        """Look for a word on screen. Returns (hit or None, all words seen)."""
        targets = {norm_word(t) for t in targets}
        seen = []
        for inv in (False, True):
            ws = self.scan_words(region, inv)
            seen = seen or ws
            hits = [w for w in ws if w["t"] in targets and w["fy"] >= min_fy]
            if hits:
                if pick == "largest":
                    hits.sort(key=lambda w: (w["fx"] > 0.6, -w["h"]))
                else:
                    hits.sort(key=lambda w: w["fy"])
                return hits[0], ws
        return None, seen

    def click_text(self, targets, label, fallback=None, **kw):
        hit, seen = self.find_text(targets, **kw)
        if hit:
            self.log(f"Clicking {label} at ({int(hit['cx'])}, {int(hit['cy'])}) [found on screen]")
            self.click_abs(hit["cx"], hit["cy"])
            return True
        if fallback:
            x, y = self.abs_point(fallback)
            self.log(f"{label} not found by OCR - clicking calibrated spot ({int(x)}, {int(y)})")
            self.click_abs(x, y)
        else:
            self.log(f"{label} not found on screen.")
        return False

    def words_summary(self, ws, n=25):
        return " ".join(w["t"] for w in ws if w["t"])[:n * 8] or "(nothing readable)"

    def has_words(self, zone, words):
        text = ocr_text(self.zone_img(zone)).lower()
        return any(w.strip() and w.strip().lower() in text for w in words.split(","))

    def read_players(self):
        n = ocr_number(self.zone_img("players"))
        if n is not None and 0 < n <= 100:
            self.stats["players"] = n
            self.push_stats()
            return n
        return None

    NAV = {"SHOP", "LOCKER", "PASSES", "V-BUCKS", "VBUCKS", "PLAY", "BUCKS"}

    def in_lobby(self):
        """True when the main menu bar (PLAY / SHOP / LOCKER ...) is visible."""
        if not self.s.bool("options", "ocr_lobby"):
            return None
        for inv in (False, True):
            ws = self.scan_words(self.s.zone("lobby"), inv)
            if len({w["t"] for w in ws} & self.NAV) >= 2:
                return True
        return False

    def diagnose(self):
        """Used by Test OCR: report what the bot can actually see."""
        x, y, w, h = self.rect()
        self.log(f"Fortnite game area: {w}x{h} at ({x}, {y}).")
        if any(r[0] < x + w and r[2] > x and r[1] < y + h and r[3] > y for r in own_window_rects()):
            self.log("Note: a bot window overlaps Fortnite - press Position window first.")
        lobby = self.in_lobby()
        ws = self.scan_words()
        self.log(f"Lobby detected: {lobby}.  Words on screen: {self.words_summary(ws)}")
        hit, _ = self.find_text(["PLAY"], min_fy=0.12)
        if hit:
            self.log(f"PLAY button found at ({int(hit['cx'] - x)}, {int(hit['cy'] - y)}) in the game "
                     f"= {(hit['cx'] - x) / w:.3f}, {(hit['cy'] - y) / h:.3f}")
        else:
            self.log("No PLAY button found (open the lobby with the Play tab showing).")
        self.log(f"Players-left counter reads: {ocr_number(self.zone_img('players'))}")
        if OCR_ERROR:
            self.log(f"OCR engine error: {OCR_ERROR}")
        p = os.path.join(DEBUG_DIR, f"diag_{int(time.time())}.png")
        self.full_shot().save(p)
        self.log(f"Saved what the bot sees: {p}")

    # --- in-game actions ---------------------------------------------------
    def chat(self, text):
        focus(self.hwnd)
        tap("enter")
        self.sleep(0.4)
        type_text(text)
        self.sleep(0.2)
        tap("enter")
        self.log(f"Chat: {text}")

    def leave_match(self):
        self.status("Leaving match", "")
        self.log("Leaving the match.")
        focus(self.hwnd)
        tap("esc")
        self.sleep(1.2)
        self.click_text(["LEAVE"], "Leave match", fallback="leave_menu", pick="first")
        self.sleep(1.5)
        hit, _ = self.find_text(["LEAVE", "CONFIRM", "YES"], pick="first")
        if hit:
            self.log("Confirming leave.")
            self.click_abs(hit["cx"], hit["cy"])
        elif not self.in_lobby():
            self.click_point("leave_confirm")

    def move_once(self):
        pick, gun = self.s.get("options", "pickaxe_key"), self.s.get("options", "gun_key")
        r = random.random()
        if r < 0.40:
            k = random.choice(["w", "w", "a", "d", "s"])
            key_event(k, True)
            self.sleep(random.uniform(0.4, 2.0))
            key_event(k, False)
        elif r < 0.65:
            mouse_move_rel(random.randint(-400, 400), random.randint(-40, 40))
        elif r < 0.80:
            tap("space")
        elif r < 0.90 and pick:
            tap(pick)
            self.sleep(0.3)
            mouse_button(0x0002, 0x0004, hold=0.3)  # swing
        elif gun:
            tap(gun)
            self.sleep(0.3)
            mouse_button(0x0002, 0x0004, hold=0.2)
        else:
            return
        self.sleep(random.uniform(0.3, 1.5))

    def release_all(self):
        for k in ("w", "a", "s", "d", "shift", "ctrl", "space"):
            try:
                key_event(k, False)
            except Exception:
                pass

    # --- main loop --------------------------------------------------------
    def _run(self):
        try:
            self.log("Started.")
            if not ocr_ready():
                self.log("WARNING: no OCR engine available - OCR features will not work.")
            x, y, w, h = self.rect()
            if (w, h) != (TARGET_W, TARGET_H) or x > 20 or y > 60:
                x, y, w, h = position_fortnite(self.hwnd)
                self.log(f"Moved Fortnite to the top left ({w}x{h}).")
            covered = [r for r in own_window_rects() if r[0] < x + w and r[2] > x and r[1] < y + h and r[3] > y]
            if covered:
                self.log("Note: a bot window overlaps Fortnite - the bot cannot see under it.")
            while True:
                self.cycle()
        except Stopped:
            self.log("Stopped.")
        except Exception as e:  # keep the real reason in the feed
            self.log(f"ERROR: {e}")
        finally:
            self.release_all()
            self.running = False
            self.paused = False
            self.status("Stopped", "Ready. Press Start or Ctrl+Alt+1.")
            self.q.put(("state", "STOPPED"))

    def recover(self, why):
        self.stats["recoveries"] += 1
        self.push_stats()
        self.log(f"Recovering: {why}")
        try:
            ws = self.scan_words()
            self.log(f"On screen: {self.words_summary(ws)}")
            self.full_shot().save(os.path.join(DEBUG_DIR, f"stuck_{int(time.time())}.png"))
        except Exception:
            pass
        focus(self.hwnd)
        for _ in range(3):
            tap("esc")
            self.sleep(0.8)

    def wait_lobby(self):
        """Wait until the lobby is on screen (or handle the results screen)."""
        self.status("Waiting for lobby", "")
        t0 = time.time()
        while True:
            self.check()
            if self.s.bool("main", "play_again"):
                hit, _ = self.find_text(["AGAIN"])
                if hit:
                    self.log("Results screen - Play again.")
                    self.click_abs(hit["cx"], hit["cy"])
                    self.sleep(3)
            lobby = self.in_lobby()
            if lobby is None:  # OCR detection disabled: just give the game time
                self.sleep(self.s.int("match", "lobby_settle"))
                return
            if lobby:
                return
            if time.time() - t0 > 90:
                self.recover("lobby not detected after 90 seconds")
                t0 = time.time()
            self.sleep(2)

    def set_quads(self):
        self.log("Setting Quads.")
        self.click_point("mode")
        self.sleep(1.5)
        if not self.click_text(["QUADS"], "Quads"):
            self.log("Quads option not found - calibrate 'mode' (the button that opens the "
                     "mode list) in Settings > Tools. Skipping.")
            tap("esc")
            self.sleep(0.8)
        else:
            self.sleep(1.0)
            self.find_confirm_close()

    def find_confirm_close(self):
        hit, _ = self.find_text(["CONFIRM", "ACCEPT", "DONE", "OK"])
        if hit:
            self.click_abs(hit["cx"], hit["cy"])
            self.sleep(1.0)

    def queue_game(self):
        """Press PLAY and make sure the game really started queueing."""
        for attempt in range(1, 4):
            self.click_text(["PLAY"], "PLAY", fallback="play", min_fy=0.12)
            self.sleep(4)
            in_lobby = self.in_lobby()
            ws = self.scan_words()
            queued = {w["t"] for w in ws} & {"CANCEL", "SEARCHING", "LOADING", "QUEUE"}
            if in_lobby is False or queued:
                return True
            self.log(f"PLAY click {attempt}: still in the lobby. Saw: {self.words_summary(ws)}")
            self.sleep(2)
        try:
            self.full_shot().save(os.path.join(DEBUG_DIR, f"noplay_{int(time.time())}.png"))
        except Exception:
            pass
        self.log("Could not confirm the game started queueing. Run Test OCR and send me the log.")
        return False

    def cycle(self):
        # ---- lobby ----
        self.wait_lobby()
        self.status("In lobby", "Settling...")
        self.sleep(self.s.int("match", "lobby_settle"))
        if self.s.bool("options", "set_quads"):
            self.set_quads()
        self.queue_game()
        self.stats["matches"] += 1
        self.push_stats()
        self.status("Queueing", f"Match {self.stats['matches']}")
        self.log(f"Queued match {self.stats['matches']}.")

        # ---- wait for the game to load (menu bar disappears) ----
        t0 = time.time()
        gone = 0
        while True:
            self.check()
            if self.s.bool("options", "ocr_lobby"):
                gone = 0 if self.in_lobby() else gone + 1
                if time.time() - t0 > 300:
                    self.recover("still in lobby after queueing")
                    return
                if gone >= 2:
                    break
            elif self.read_players() is not None or time.time() - t0 > 240:
                break
            self.sleep(2)

        # ---- bus: wait, then jump ----
        self.status("In bus", "")
        self.sleep(self.s.int("match", "wait_before_jump"))
        proceed = self.s.int("match", "proceed_anyway")
        t1 = time.time()
        while self.read_players() is None:
            if proceed and time.time() - t1 > proceed:
                self.log("Counter not readable - proceeding anyway.")
                break
            self.sleep(2)
        focus(self.hwnd)
        tap("space")
        self.log("Jumped from the bus.")
        self.status("Dropping", "")
        self.sleep(self.s.int("match", "landing_wait"))

        up = self.s.int("options", "look_up")
        if up > 0:
            mouse_move_rel(0, -up)
        match_start = time.time()
        sent_first = sent_second = False
        team_out = 0
        last_banner = 0.0

        # ---- in match ----
        while True:
            self.check()
            elapsed = time.time() - match_start
            self.status("In match", f"{int(elapsed // 60)}m {int(elapsed % 60):02d}s")

            if self.s.bool("main", "afk_messages"):
                if not sent_first:
                    self.chat(self.s.get("text", "afk1"))
                    sent_first = True
                elif not sent_second and elapsed >= self.s.int("match", "afk_second_msg"):
                    self.chat(self.s.get("text", "afk2"))
                    sent_second = True

            players = self.read_players()
            if players is not None and players <= self.s.int("match", "leave_at_players"):
                self.log(f"{players} players left - leaving.")
                break
            if elapsed > self.s.int("match", "max_match_min") * 60:
                self.log("Max match length reached - leaving.")
                break

            if time.time() - last_banner > 4:
                last_banner = time.time()
                if self.has_words("banner", self.s.get("text", "banner_words")):
                    self.stats["gizmos"] += 1
                    self.stats["found"] += 1
                    self.push_stats()
                    self.log("Item banner detected.")
                    self.discord("Item found!", self.s.bool("discord", "shot_on_find"))
                    self.sleep(6)
                feed = ocr_text(self.zone_img("feed")).lower()
                if self.s.bool("main", "reboot_thanks") and \
                        any(w.strip() and w.strip() in feed
                            for w in self.s.get("text", "reboot_words").split(",")):
                    self.chat(self.s.get("text", "thanks"))
                    self.sleep(8)
                if self.s.bool("main", "leave_if_team_out"):
                    words = self.s.get("text", "team_out_words").split(",")
                    hits = sum(feed.count(w.strip()) for w in words if w.strip())
                    if hits:
                        team_out += hits
                        self.log(f"Team elimination seen ({team_out}/2).")
                        self.sleep(10)  # same feed line will still be visible
                    if team_out >= 2:
                        self.log("Team is out - leaving.")
                        break

            if self.s.bool("main", "movement"):
                self.move_once()
            else:
                self.sleep(2)

        self.release_all()
        self.leave_match()
        self.stats["players"] = None
        self.push_stats()
        self.sleep(6)

    # --- discord ----------------------------------------------------------
    def discord(self, text, with_shot=False):
        url = self.s.get("discord", "webhook").strip()
        if not valid_webhook(url) or requests is None:
            return False
        try:
            files = None
            if with_shot:
                buf = io.BytesIO()
                self.full_shot().save(buf, "PNG")
                buf.seek(0)
                files = {"file": ("shot.png", buf, "image/png")}
            r = requests.post(url, data={"content": text}, files=files, timeout=15)
            return r.status_code < 300
        except Exception as e:
            self.log(f"Discord error: {e}")
            return False


WEBHOOK_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+/?$")


def valid_webhook(url):
    return bool(WEBHOOK_RE.match(url.strip()))


# ----------------------------------------------------------------------------
# UI widgets
# ----------------------------------------------------------------------------
def round_rect(cv, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class RoundBtn(tk.Canvas):
    """Rounded button drawn on a canvas (Tk buttons cannot have rounded corners)."""

    def __init__(self, parent, text, command, bg=OFF, fg=FG, font=FONT, w=None, h=32, r=12):
        if w is None:
            import tkinter.font as tkfont
            w = tkfont.Font(font=font).measure(text) + S(30)
        else:
            w = S(w)
        h, r = S(h), S(r)
        super().__init__(parent, width=w, height=h, bg=BG, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._rb = dict(text=text, fg=fg, bg=bg, font=font, r=r, hover=False, cmd=command)
        self.bind("<Enter>", lambda _: self._hover(True))
        self.bind("<Leave>", lambda _: self._hover(False))
        self.bind("<Button-1>", lambda _: self._rb["cmd"]())
        self.bind("<Configure>", lambda _: self._draw())
        self._draw()

    def _hover(self, on):
        self._rb["hover"] = on
        self._draw()

    def _draw(self):
        d = self._rb
        w = max(self.winfo_width(), int(float(self.cget("width"))))
        h = max(self.winfo_height(), int(float(self.cget("height"))))
        self.delete("all")
        fill = d["bg"]
        if d["hover"]:
            fill = ACCENT_HI if fill == ACCENT else "#352f52"
        round_rect(self, 1, 1, w - 1, h - 1, d["r"], fill=fill, outline=fill)
        self.create_text(w / 2, h / 2, text=d["text"], fill=d["fg"], font=d["font"])

    def config(self, cnf=None, **kw):
        redraw = False
        for k in ("text", "fg", "bg"):
            if k in kw:
                self._rb[k] = kw.pop(k)
                redraw = True
        if kw or cnf:
            super().config(cnf, **kw)
        if redraw:
            self._draw()

    configure = config


class Toggle(tk.Canvas):
    def __init__(self, parent, var, command=None):
        super().__init__(parent, width=S(54), height=S(24), bg=BG, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.var, self.command = var, command
        self.bind("<Button-1>", self._flip)
        var.trace_add("write", lambda *_: self._paint())
        self._paint()

    def _flip(self, _=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def _paint(self):
        on = self.var.get()
        self.delete("all")
        round_rect(self, 1, 1, S(54) - 1, S(24) - 1, S(12), fill=ACCENT if on else OFF, outline="")
        self.create_text(S(54) // 2, S(24) // 2, text="On" if on else "Off", fill=FG if on else DIM,
                         font=("Segoe UI", 9, "bold"))


class Check(tk.Frame):
    def __init__(self, parent, text, var):
        super().__init__(parent, bg=BG)
        self.var = var
        self.box = tk.Canvas(self, width=S(20), height=S(20), bg=BG, highlightthickness=0, bd=0,
                             cursor="hand2")
        self.box.pack(side="left")
        self.lbl = tk.Label(self, text=text, bg=BG, fg=FG, font=FONT, cursor="hand2")
        self.lbl.pack(side="left", padx=8)
        for w in (self.box, self.lbl):
            w.bind("<Button-1>", lambda _: var.set(not var.get()))
        var.trace_add("write", lambda *_: self._paint())
        self._paint()

    def _paint(self):
        on = self.var.get()
        self.box.delete("all")
        round_rect(self.box, 1, 1, S(20) - 1, S(20) - 1, S(6), fill=PINK if on else OFF, outline="")
        if on:
            self.box.create_text(S(20) // 2, S(20) // 2, text="✓", fill="white", font=("Segoe UI", 10, "bold"))


def flat_button(parent, text, cmd, bg=OFF, fg=FG, w=None, h=32, font=FONT):
    return RoundBtn(parent, text, cmd, bg=bg, fg=fg, w=w, h=h, font=font, r=h // 2 - 2)


def dark_entry(parent, var, width=14):
    return tk.Entry(parent, textvariable=var, width=width, bg=PANEL, fg=FG, insertbackground=FG,
                    relief="flat", highlightthickness=1, highlightbackground=LINE,
                    highlightcolor=ACCENT, font=FONT)


def setup_style(root):
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure("TSpinbox", fieldbackground=PANEL, background="#2c2745", foreground=FG,
                 arrowcolor="#cfc8f0", bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                 insertcolor=FG, arrowsize=11, padding=3, selectbackground=ACCENT,
                 selectforeground="white")
    st.map("TSpinbox", background=[("active", "#3d3660"), ("pressed", ACCENT)],
           bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
           darkcolor=[("focus", ACCENT)])
    st.configure("TCombobox", fieldbackground=PANEL, background="#2c2745", foreground=FG,
                 arrowcolor="#cfc8f0", bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                 selectbackground=PANEL, selectforeground=FG, padding=4)
    st.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", FG)


# ----------------------------------------------------------------------------
# Settings window
# ----------------------------------------------------------------------------
class SettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app, self.s = app, app.s
        self.title(f"Settings — Ripple Reborn v{VERSION}")
        self.configure(bg=BG)
        set_icon(self)
        self.attributes("-topmost", self.s.bool("options", "always_on_top"))
        # footer first so it never gets squeezed out
        foot = tk.Frame(self, bg=BG)
        foot.pack(side="bottom", fill="x", padx=14)
        tk.Frame(foot, bg=LINE, height=1).pack(fill="x")
        tk.Label(foot, text="Changes are saved automatically.", bg=BG, fg=DIM,
                 font=FONT_S).pack(anchor="w", padx=4, pady=6)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=14, pady=(8, 0))
        tk.Frame(self, bg=LINE, height=1).pack(fill="x", padx=14)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(6, 0))
        self.tabs, self.tab_btns = {}, {}
        for name in ("Match", "Options", "Discord", "Tools"):
            cell = tk.Frame(bar, bg=BG)
            cell.pack(side="left", padx=(8, 30))
            lbl = tk.Label(cell, text=name, bg=BG, font=("Segoe UI", 12, "bold"), cursor="hand2",
                           padx=4, pady=6)
            lbl.pack()
            ul = tk.Frame(cell, bg=BG, height=3)
            ul.pack(fill="x")
            lbl.bind("<Button-1>", lambda _, n=name: self.select(n))
            self.tab_btns[name] = (lbl, ul)
            self.tabs[name] = tk.Frame(body, bg=BG)
        self.build_match()
        self.build_options()
        self.build_discord()
        self.build_tools()
        self.update_idletasks()
        mw = mh = 0
        for n in self.tabs:               # size the window to the biggest tab
            self.select(n)
            self.update_idletasks()
            mw, mh = max(mw, self.winfo_reqwidth()), max(mh, self.winfo_reqheight())
        self.select("Match")
        self.geometry(f"{max(mw, S(700))}x{mh}")
        dark_titlebar(self)

    def select(self, name):
        for n, f in self.tabs.items():
            f.pack_forget()
            lbl, ul = self.tab_btns[n]
            on = n == name
            lbl.config(fg=FG if on else "#9a8cc8")
            ul.config(bg=PINK if on else BG)
        self.tabs[name].pack(fill="both", expand=True)

    def spin(self, parent, label, sec, key, lo, hi, row, col):
        tk.Label(parent, text=label, bg=BG, fg=FG, font=FONT).grid(
            row=row, column=col * 2, sticky="w", padx=(10, 12), pady=5)
        var = tk.StringVar(value=str(self.s.int(sec, key)))
        sp = ttk.Spinbox(parent, from_=lo, to=hi, width=6, textvariable=var)
        sp.grid(row=row, column=col * 2 + 1, sticky="e", pady=5, padx=(0, 20))
        var.trace_add("write", lambda *_: self.save_num(sec, key, var, lo, hi))

    def save_num(self, sec, key, var, lo, hi):
        try:
            v = max(lo, min(hi, int(var.get())))
        except ValueError:
            return
        self.s.set(sec, key, v)

    def build_match(self):
        f = self.tabs["Match"]
        for c in range(4):
            f.columnconfigure(c, weight=1 if c % 2 == 0 else 0)
        self.spin(f, "Leave when players left are ≤", "match", "leave_at_players", 0, 100, 0, 0)
        self.spin(f, "Wait before jumping (seconds)", "match", "wait_before_jump", 0, 300, 1, 0)
        self.spin(f, "Proceed anyway after (seconds)", "match", "proceed_anyway", 0, 600, 2, 0)
        self.spin(f, "AFK 2nd message after (seconds)", "match", "afk_second_msg", 0, 600, 3, 0)
        self.spin(f, "Max match length (minutes)", "match", "max_match_min", 1, 60, 0, 1)
        self.spin(f, "Landing wait (seconds)", "match", "landing_wait", 0, 300, 1, 1)
        tk.Label(f, text="0 = always wait for the counter", bg=BG, fg=DIM, font=FONT_S).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=10)
        self.spin(f, "Lobby settle wait (seconds)", "match", "lobby_settle", 0, 120, 3, 1)
        tk.Label(f, text="Lobby settle wait: pause after returning to the lobby, before clicking "
                 "anything. Raise it if the bot clicks too fast for Fortnite to catch up.",
                 bg=BG, fg=DIM, font=FONT_S, wraplength=S(640), justify="left", anchor="w").grid(
            row=4, column=0, columnspan=4, sticky="w", padx=10, pady=14)

    def build_options(self):
        f = self.tabs["Options"]
        self.checks = {}
        items = [("Detect the lobby with OCR", "ocr_lobby", 0, 0),
                 ("Save debug screenshots (folder: debug)", "debug_shots", 1, 0),
                 ("Keep bot window always on top", "always_on_top", 0, 1),
                 ("Set Quads every cycle", "set_quads", 1, 1)]
        for text, key, r, c in items:
            var = tk.BooleanVar(value=self.s.bool("options", key))
            var.trace_add("write", lambda *_, k=key, v=var: self.opt_changed(k, v))
            Check(f, text, var).grid(row=r, column=c, sticky="w", padx=16, pady=6)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        row = tk.Frame(f, bg=BG)
        row.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 0))
        for label, key in (("Pickaxe key", "pickaxe_key"), ("Gun key", "gun_key")):
            tk.Label(row, text=label, bg=BG, fg=FG, font=FONT).pack(side="left")
            var = tk.StringVar(value=self.s.get("options", key))
            var.trace_add("write", lambda *_, k=key, v=var: self.s.set("options", k, v.get().strip()))
            e = dark_entry(row, var, width=5)
            e.pack(side="left", padx=(12, 30), ipady=4)
        tk.Label(f, text="Your slot keys for the random movement (e.g. 1, 2, q, F5). "
                 "Gun empty = never shoot.", bg=BG, fg=DIM, font=FONT_S).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=16, pady=4)
        row = tk.Frame(f, bg=BG)
        row.grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=10)
        tk.Label(row, text="Look up after landing (pixels)", bg=BG, fg=FG, font=FONT).pack(side="left")
        var = tk.StringVar(value=str(self.s.int("options", "look_up")))
        ttk.Spinbox(row, from_=0, to=2000, increment=10, width=7, textvariable=var).pack(
            side="left", padx=12)
        var.trace_add("write", lambda *_: self.save_num("options", "look_up", var, 0, 2000))
        tk.Label(row, text="Raises the camera after landing. 0 = off. Higher = more.",
                 bg=BG, fg=DIM, font=FONT_S).pack(side="left", padx=10)

    def opt_changed(self, key, var):
        self.s.set("options", key, var.get())
        if key == "always_on_top":
            self.app.root.attributes("-topmost", var.get())
            self.attributes("-topmost", var.get())

    def build_discord(self):
        f = self.tabs["Discord"]
        head = tk.Frame(f, bg=BG)
        head.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(head, text="WEBHOOK URL", bg=BG, fg="#9a94c0", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.hook_state = tk.Label(head, bg=BG, font=FONT_B)
        self.hook_state.pack(side="right")
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x", padx=16)
        self.hook = tk.StringVar(value=self.s.get("discord", "webhook"))
        dark_entry(row, self.hook, width=60).pack(side="left", fill="x", expand=True, ipady=6)
        flat_button(row, "Test webhook", self.app.test_discord, h=30).pack(side="left", padx=(8, 0))
        self.hook.trace_add("write", lambda *_: self.hook_changed())
        self.hook_changed()
        var = tk.BooleanVar(value=self.s.bool("discord", "shot_on_find"))
        var.trace_add("write", lambda *_: self.s.set("discord", "shot_on_find", var.get()))
        Check(f, "Screenshot when an item is found (banner)", var).pack(anchor="w", padx=16, pady=12)

    def hook_changed(self):
        url = self.hook.get().strip()
        self.s.set("discord", "webhook", url)
        if not url:
            self.hook_state.config(text="")
        elif valid_webhook(url):
            self.hook_state.config(text="● valid link", fg=GOOD)
        else:
            self.hook_state.config(text="● invalid link", fg=BAD)

    def build_tools(self):
        f = self.tabs["Tools"]
        top = tk.Frame(f, bg=BG)
        top.pack(fill="x", padx=14, pady=(10, 4))
        for text, cmd in (("Test OCR", self.app.test_ocr), ("Show zones", self.app.show_zones),
                          ("Test leave", self.app.test_leave),
                          ("Position window", self.app.position_window)):
            flat_button(top, text, cmd).pack(side="left", expand=True, fill="x", padx=4)
        cal = tk.Frame(f, bg=BG)
        cal.pack(fill="x", padx=14, pady=10)
        tk.Label(cal, text="Calibrate", bg=BG, fg=FG, font=FONT).pack(side="left", padx=(0, 18))
        self.cal_var = tk.StringVar(value=CAL_NAMES[0])
        cb = ttk.Combobox(cal, textvariable=self.cal_var, values=CAL_NAMES, state="readonly", width=16)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _: self.update_current())
        flat_button(cal, "Capture in 3s", self.capture, h=28).pack(side="left", padx=10)
        flat_button(cal, "Show", self.show_point, h=28).pack(side="left")
        self.cur = tk.Label(cal, bg=BG, fg=DIM, font=FONT)
        self.cur.pack(side="left", padx=10)
        self.update_current()
        tk.Label(f, text="Hotkeys (Ctrl+Alt+):  1 start · 2 stop · K kill · 3 save position · "
                 "4 test OCR · 5 show zones · 6 test Discord · 7 screenshot · 8 debug folder · "
                 "9 test chat\nCalibrate: pick a name, press Capture, then hover the mouse over the "
                 "spot inside Fortnite. *_tl / *_br are the top-left / bottom-right corners of a "
                 "zone.", bg=BG, fg=DIM, font=FONT_S, wraplength=S(640), justify="left").pack(
            anchor="w", padx=16, pady=6)

    def update_current(self):
        x, y = self.s.point(self.cal_var.get())
        self.cur.config(text=f"current: {x:.3f}, {y:.3f}")

    def capture(self):
        name = self.cal_var.get()
        self.cur.config(text="move the mouse over the spot...")
        self.after(3000, lambda: self._do_capture(name))

    def _do_capture(self, name):
        try:
            hwnd = find_fortnite()
            if not hwnd:
                self.cur.config(text="Fortnite not found")
                return
            x, y, w, h = client_rect(hwnd)
            mx, my = cursor_pos()
            fx, fy = (mx - x) / w, (my - y) / h
            if not (0 <= fx <= 1 and 0 <= fy <= 1):
                self.cur.config(text="mouse was outside Fortnite")
                return
            self.s.set("points", name, f"{fx:.4f},{fy:.4f}")
            self.app.log(f"Calibrated {name}: {fx:.3f}, {fy:.3f}")
            self.update_current()
        except Exception as e:
            self.cur.config(text=f"error: {e}")

    def show_point(self):
        self.app.show_marks([self.cal_var.get()], points=True)


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class App:
    def __init__(self):
        self.root = tk.Tk()
        global SCALE
        try:
            SCALE = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        except Exception:
            SCALE = 1.0
        self.s = Settings()
        self.q = queue.Queue()
        self.bot = Bot(self.s, self.q)
        self.settings_win = None
        self.root.title(f"Ripple Reborn v{VERSION} — STOPPED")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", self.s.bool("options", "always_on_top"))
        setup_style(self.root)
        set_icon(self.root)
        self.build()
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        ww = max(self.root.winfo_reqwidth(), S(430))
        wh = min(max(self.root.winfo_reqheight(), S(700)), sh - S(70))
        wx = TARGET_W + 10 if TARGET_W + 10 + ww <= sw else max(0, sw - ww)
        self.root.geometry(f"{ww}x{wh}+{wx}+10")
        self.root.minsize(ww, min(wh, S(560)))
        dark_titlebar(self.root)
        self.log(f"Script ready. Put Fortnite in windowed mode at {TARGET_W}x{TARGET_H} "
                 "('Position window' button).")
        self.log(f"Data folder (settings, log, debug): {DATA_DIR}")
        self.log(f"Settings file: {SETTINGS_FILE}  ({'loaded' if self.s.loaded else 'new'})")
        if not ocr_ready():
            self.log("WARNING: no OCR engine found (Windows OCR missing and no Tesseract).")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.poll()
        if IS_WIN:
            threading.Thread(target=self.hotkey_loop, daemon=True).start()

    # --- layout -----------------------------------------------------------
    def build(self):
        r = self.root
        top = tk.Frame(r, bg=BG)
        top.pack(fill="x", padx=16, pady=(12, 0))
        try:
            self.logo = tk.PhotoImage(file=resource("logo.png")).subsample(
                *(max(1, round(256 / S(50))),) * 2)
            tk.Label(top, image=self.logo, bg=BG).pack(side="left", padx=(0, 10))
        except Exception:
            pass
        left = tk.Frame(top, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="Ripple Reborn", bg=BG, fg=FG, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(left, text=f"v{VERSION}  ·  personal build", bg=BG, fg=DIM, font=FONT_S).pack(anchor="w")
        right = tk.Frame(top, bg=BG)
        right.pack(side="right")
        self.start_btn = RoundBtn(right, "▶  Start", self.toggle_start, bg=ACCENT, fg="white",
                                  font=FONT_B, w=140, h=34, r=15)
        self.start_btn.pack()
        flat_button(right, "⚙  Settings", self.open_settings, w=140, h=30).pack(pady=(5, 0))

        hk = tk.Frame(r, bg=BG)
        hk.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(hk, text="Ctrl+Alt+1 start · 2 stop · P pause · K kill", bg=BG, fg=DIM,
                 font=FONT_S).pack(side="left")
        self.pause_btn = flat_button(hk, "Pause", self.bot.toggle_pause, fg=DIM, w=72, h=22,
                                     font=FONT_S)
        self.pause_btn.pack(side="right")

        st = tk.Frame(r, bg=BG)
        st.pack(fill="x", padx=16, pady=(6, 2))
        self.dot = tk.Label(st, text="●", bg=BG, fg=PINK, font=("Segoe UI", 10))
        self.dot.pack(side="left")
        self.headline = tk.Label(st, text="Stopped", bg=BG, fg=FG, font=("Segoe UI", 13, "bold"))
        self.headline.pack(side="left", padx=8)
        self.detail = tk.Label(r, text="Ready. Press Start or Ctrl+Alt+1.", bg=BG, fg=DIM, font=FONT,
                               anchor="w")
        self.detail.pack(fill="x", padx=16)
        self.rule()

        stats = tk.Frame(r, bg=BG)
        stats.pack(fill="x", padx=16, pady=6)
        for i, name in enumerate(("Time AFK", "Players left", "Gizmos")):
            tk.Label(stats, text=name, bg=BG, fg="#9a94c0", font=FONT).grid(row=0, column=i, sticky="w")
        self.t_afk = tk.Label(stats, text="00:00:00", bg=BG, fg=FG, font=("Segoe UI", 19, "bold"))
        self.t_afk.grid(row=1, column=0, sticky="w", padx=(0, 28))
        self.t_players = tk.Label(stats, text="--", bg=BG, fg="#a98cff", font=("Segoe UI", 19, "bold"))
        self.t_players.grid(row=1, column=1, sticky="w", padx=(0, 28))
        self.t_gizmos = tk.Label(stats, text="0", bg=BG, fg=PINK, font=("Segoe UI", 19, "bold"))
        self.t_gizmos.grid(row=1, column=2, sticky="w")
        self.t_counts = tk.Label(stats, text="Matches 0  ·  found 0  ·  recoveries 0", bg=BG, fg=DIM,
                                 font=FONT_S)
        self.t_counts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.rule()

        self.vars = {}
        for key, title, sub in (
                ("movement", "Movement", "Walk, turn the camera, jump and pickaxe"),
                ("afk_messages", "AFK messages", "Two 'I'm away' messages in chat per match"),
                ("reboot_thanks", "Reboot thanks", "Says thanks in chat after a reboot"),
                ("play_again", "Play again", "Requeue from the results screen"),
                ("leave_if_team_out", "Leave if team is out", "Leaves when 2 teammates are eliminated")):
            row = tk.Frame(r, bg=BG)
            row.pack(fill="x", padx=16, pady=4)
            txt = tk.Frame(row, bg=BG)
            txt.pack(side="left")
            tk.Label(txt, text=title, bg=BG, fg=FG, font=("Segoe UI", 10)).pack(anchor="w")
            tk.Label(txt, text=sub, bg=BG, fg=DIM, font=FONT_S).pack(anchor="w")
            var = tk.BooleanVar(value=self.s.bool("main", key))
            var.trace_add("write", lambda *_, k=key, v=var: self.s.set("main", k, v.get()))
            self.vars[key] = var
            Toggle(row, var).pack(side="right")
            tk.Frame(r, bg=LINE, height=1).pack(fill="x", padx=16)

        tk.Label(r, text="Session feed", bg=BG, fg="#9a94c0", font=FONT_S).pack(anchor="w", padx=16,
                                                                              pady=(6, 3))
        box = tk.Frame(r, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.feed = tk.Text(box, bg=PANEL, fg="#c9c4e6", font=MONO, relief="flat", wrap="word",
                            height=6, state="disabled", bd=0, padx=8, pady=6)
        sb = tk.Scrollbar(box, command=self.feed.yview)
        self.feed.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.feed.pack(side="left", fill="both", expand=True)

    def rule(self):
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x", padx=16, pady=5)

    # --- logging / UI queue -----------------------------------------------
    def log(self, msg):
        self.bot.log(msg)

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                kind = m[0]
                if kind == "log":
                    self.feed.config(state="normal")
                    self.feed.insert("end", m[1] + "\n")
                    self.feed.see("end")
                    self.feed.config(state="disabled")
                elif kind == "status":
                    self.headline.config(text=m[1])
                    self.detail.config(text=m[2])
                elif kind == "state":
                    self.set_state(m[1])
                elif kind == "stats":
                    d = m[1]
                    self.t_players.config(text="--" if d["players"] is None else str(d["players"]))
                    self.t_gizmos.config(text=str(d["gizmos"]))
                    self.t_counts.config(text=f"Matches {d['matches']}  ·  found {d['found']}  ·  "
                                              f"recoveries {d['recoveries']}")
                elif kind == "call":
                    m[1]()
        except queue.Empty:
            pass
        sec = self.bot.afk_seconds()
        self.t_afk.config(text=f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}")
        self.root.after(250, self.poll)

    def set_state(self, state):
        self.root.title(f"Ripple Reborn v{VERSION} — {state}")
        running = state in ("RUNNING", "PAUSED")
        self.start_btn.config(text="■  Stop" if running else "▶  Start")
        self.pause_btn.config(fg=FG if running else DIM, text="Resume" if state == "PAUSED" else "Pause")
        self.dot.config(fg=GOOD if state == "RUNNING" else ("#ffcc4d" if state == "PAUSED" else PINK))
        if state == "PAUSED":
            self.headline.config(text="Paused")
            self.detail.config(text="Press P (Ctrl+Alt+P) to resume.")
        elif state == "STOPPED":
            self.headline.config(text="Stopped")

    # --- actions ----------------------------------------------------------
    def place_beside(self):
        """Put the bot window right of the 1280x720 Fortnite window."""
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        ww = self.root.winfo_width()
        wx = TARGET_W + 20 if TARGET_W + 20 + ww <= sw else max(0, sw - ww)
        self.root.geometry(f"+{wx}+10")

    def toggle_start(self):
        if self.bot.running:
            self.bot.stop()
        else:
            if self.settings_win and self.settings_win.winfo_exists():
                self.settings_win.destroy()  # don't let it cover the game
            self.place_beside()
            self.bot.start()

    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self.settings_win = SettingsWindow(self)

    def run_bg(self, fn):
        def wrap():
            try:
                fn()
            except Exception as e:
                self.log(f"ERROR: {e}")
        threading.Thread(target=wrap, daemon=True).start()

    def position_window(self):
        def go():
            if not find_fortnite():
                self.log("Fortnite window not found. Start Fortnite in windowed mode first.")
                return
            hwnd = find_fortnite()
            x, y, w, h = position_fortnite(hwnd)
            self.call(self.place_beside)
            self.log("Fortnite moved to the top left." if (w, h) == (TARGET_W, TARGET_H)
                     else f"Fortnite client is {w}x{h} (wanted {TARGET_W}x{TARGET_H}). "
                          "Set the in-game resolution to 1280x720 windowed.")
        self.run_bg(go)

    def test_ocr(self):
        def go():
            if not ocr_ready():
                self.log("No OCR engine available.")
                return
            self.log(f"OCR engine: {'Windows' if _load_winocr() else 'Tesseract'}")
            try:
                self.bot.diagnose()
            finally:
                self.call(self._show_settings)
        sw = self.settings_win
        if sw and sw.winfo_exists():
            sw.withdraw()
            self.root.update()
            time.sleep(0.3)
        self.run_bg(go)

    def _show_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.deiconify()

    def test_leave(self):
        def go():
            self.bot.rect()
            self.bot.stop_flag.clear()
            self.bot.leave_match()
        self.run_bg(go)

    def test_chat(self):
        def go():
            self.bot.rect()
            self.bot.stop_flag.clear()
            self.bot.chat("test")
        self.run_bg(go)

    def test_discord(self):
        def go():
            ok = self.bot.discord("Ripple Reborn: webhook test", with_shot=False)
            self.log("Discord test sent." if ok else "Discord test failed (check the URL).")
        self.run_bg(go)

    def screenshot(self):
        def go():
            self.bot.rect()
            p = os.path.join(DEBUG_DIR, f"shot_{int(time.time())}.png")
            self.bot.full_shot().save(p)
            self.log(f"Screenshot saved: {p}")
        self.run_bg(go)

    def open_debug(self):
        if IS_WIN:
            os.startfile(DEBUG_DIR)
        else:
            subprocess.Popen(["xdg-open", DEBUG_DIR])

    def save_position(self):
        self.position_window()

    def show_zones(self):
        self.show_marks(list(ZONES), points=False)

    def show_marks(self, names, points):
        """Draw outlines over Fortnite for a few seconds."""
        hwnd = find_fortnite()
        if not hwnd:
            self.log("Fortnite window not found.")
            return
        x, y, w, h = client_rect(hwnd)
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.attributes("-topmost", True)
        ov.geometry(f"{w}x{h}+{x}+{y}")
        key = "#010101"
        ov.configure(bg=key)
        try:
            ov.attributes("-transparentcolor", key)
        except tk.TclError:
            ov.attributes("-alpha", 0.5)
        cv = tk.Canvas(ov, bg=key, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        if points:
            for n in names:
                if n in ZONES or "_" in n and n.rsplit("_", 1)[0] in ZONES:
                    z = n.rsplit("_", 1)[0]
                    x1, y1, x2, y2 = self.s.zone(z)
                    cv.create_rectangle(x1 * w, y1 * h, x2 * w, y2 * h, outline=PINK, width=3)
                    cv.create_text(x1 * w + 4, y1 * h - 10, text=z, fill=PINK, anchor="w")
                else:
                    px, py = self.s.point(n)
                    cv.create_oval(px * w - 10, py * h - 10, px * w + 10, py * h + 10,
                                   outline=PINK, width=3)
                    cv.create_text(px * w + 14, py * h, text=n, fill=PINK, anchor="w")
        else:
            for n in names:
                x1, y1, x2, y2 = self.s.zone(n)
                cv.create_rectangle(x1 * w, y1 * h, x2 * w, y2 * h, outline=PINK, width=3)
                cv.create_text(x1 * w + 4, y1 * h - 10, text=n, fill=PINK, anchor="w")
            for n in POINTS:
                px, py = self.s.point(n)
                cv.create_oval(px * w - 8, py * h - 8, px * w + 8, py * h + 8, outline="#4dd0ff", width=3)
                cv.create_text(px * w + 12, py * h, text=n, fill="#4dd0ff", anchor="w")
        ov.after(6000, ov.destroy)

    # --- hotkeys ----------------------------------------------------------
    def hotkey_loop(self):
        MOD = 0x0001 | 0x0002 | 0x4000  # ALT | CTRL | NOREPEAT
        actions = {
            "1": lambda: self.call(self.bot.start),
            "2": lambda: self.call(self.bot.stop),
            "P": lambda: self.call(self.bot.toggle_pause),
            "K": lambda: self.call(self.kill),
            "3": lambda: self.call(self.save_position),
            "4": lambda: self.call(self.test_ocr),
            "5": lambda: self.call(self.show_zones),
            "6": lambda: self.call(self.test_discord),
            "7": lambda: self.call(self.screenshot),
            "8": lambda: self.call(self.open_debug),
            "9": lambda: self.call(self.test_chat),
        }
        ids = {}
        for i, ch in enumerate(actions, 1):
            if user32.RegisterHotKey(None, i, MOD, ord(ch)):
                ids[i] = ch
            else:
                self.log(f"Could not register Ctrl+Alt+{ch} (already used by another program).")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312 and msg.wParam in ids:
                actions[ids[msg.wParam]]()

    def call(self, fn):
        self.q.put(("call", fn))

    def kill(self):
        self.bot.stop()
        self.bot.release_all()
        self.root.after(200, self.quit)

    def quit(self):
        self.bot.stop()
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


def main():
    if not IS_WIN:
        print("This bot only runs on Windows.")
        return
    App().run()


if __name__ == "__main__":
    main()
