import configparser
import sys
from dataclasses import dataclass
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]
CFG_FILE = ROOT_DIR / "clickstudio_settings.ini"
ERROR_LOG = ROOT_DIR / "clickstudio_error.log"

CAP_CHOICES = ["F2", "F4", "F8", "F9"]
PLAY_CHOICES = ["F10", "F11", "F12", "pause"]


@dataclass
class AppSettings:
    cap_hk: str = "F9"
    play_hk: str = "F10"
    loop_inf: bool = False
    loop_count: int = 1


def load_settings() -> AppSettings:
    s = AppSettings()
    cp = configparser.ConfigParser()
    if not cp.read(CFG_FILE, encoding="utf-8"):
        return s
    sec = cp["settings"]
    cap = sec.get("CaptureHK", "F9").strip()
    play = sec.get("PlayHK", "F10").strip()
    if cap.upper() in CAP_CHOICES:
        s.cap_hk = cap.upper()
    if play.lower() in PLAY_CHOICES:
        s.play_hk = play if play.lower() == "pause" else play.upper()
    s.loop_inf = sec.get("LoopInfinite", "0") == "1"
    try:
        s.loop_count = max(1, int(sec.get("LoopCount", "1")))
    except ValueError:
        s.loop_count = 1
    return s


def save_settings(s: AppSettings) -> None:
    cp = configparser.ConfigParser()
    cp["settings"] = {
        "CaptureHK": s.cap_hk,
        "PlayHK": s.play_hk,
        "LoopInfinite": "1" if s.loop_inf else "0",
        "LoopCount": str(s.loop_count),
    }
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        cp.write(f)
