from dataclasses import asdict, dataclass
import re

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

SEND_SPECIAL = {
    "ENTER": "enter",
    "TAB": "tab",
    "SPACE": "space",
    "ESC": "esc",
    "DEL": "delete",
    "BACKSPACE": "backspace",
    "UP": "up",
    "DOWN": "down",
    "LEFT": "left",
    "RIGHT": "right",
    "HOME": "home",
    "END": "end",
    "PGUP": "pageup",
    "PGDN": "pagedn",
    "INSERT": "insert",
}
SEND_MODS = {"^": "ctrl", "!": "alt", "+": "shift", "#": "win"}


@dataclass
class MouseStep:
    x: int = 0
    y: int = 0
    button: str = "left"
    clicks: int = 1
    hold: int = 60
    delay: int = 0
    human: bool = False


@dataclass
class KeyStep:
    key: str = "a"
    count: int = 1
    interval: int = 100
    delay: int = 0


@dataclass
class SleepStep:
    duration: int = 1000
    duration_max: int = 1000
    random: bool = False
    delay: int = 0


@dataclass
class CmdStep:
    command: str = ""
    delay: int = 0


WINDOW_ACTIONS = ("focus", "minimize", "maximize", "restore", "close")


@dataclass
class WindowStep:
    title: str = ""
    action: str = "focus"
    delay: int = 0


def step_to_dict(s) -> dict:
    d = asdict(s)
    d["type"] = type(s).__name__.removesuffix("Step").lower()
    return d


def step_from_dict(d: dict):
    try:
        t = d.get("type")
        if t == "mouse":
            btn = str(d.get("button", "left"))
            return MouseStep(
                x=int(d.get("x", 0)),
                y=int(d.get("y", 0)),
                button=btn if btn in ("left", "right", "middle") else "left",
                clicks=max(0, int(d.get("clicks", 1))),
                hold=max(0, int(d.get("hold", 60))),
                delay=max(0, int(d.get("delay", 0))),
                human=bool(d.get("human", False)),
            )
        if t == "key":
            key = str(d.get("key", "")).strip()
            if not key:
                return None
            return KeyStep(
                key=key,
                count=max(1, int(d.get("count", 1))),
                interval=max(0, int(d.get("interval", 100))),
                delay=max(0, int(d.get("delay", 0))),
            )
        if t == "sleep":
            return SleepStep(
                duration=max(0, int(d.get("duration", 1000))),
                duration_max=max(0, int(d.get("duration_max", d.get("duration", 1000)))),
                random=bool(d.get("random", False)),
                delay=max(0, int(d.get("delay", 0))),
            )
        if t == "cmd":
            command = str(d.get("command", "")).strip()
            if not command:
                return None
            return CmdStep(
                command=command,
                delay=max(0, int(d.get("delay", 0))),
            )
        if t == "window":
            title = str(d.get("title", "")).strip()
            if not title:
                return None
            action = str(d.get("action", "focus"))
            return WindowStep(
                title=title,
                action=action if action in WINDOW_ACTIONS else "focus",
                delay=max(0, int(d.get("delay", 0))),
            )
    except (TypeError, ValueError):
        return None
    return None


def step_type_name(s) -> str:
    if isinstance(s, MouseStep):
        return "Mouse"
    if isinstance(s, KeyStep):
        return "Key"
    if isinstance(s, CmdStep):
        return "CMD"
    if isinstance(s, WindowStep):
        return "Window"
    return "Sleep"


def step_action_text(s) -> str:
    if isinstance(s, MouseStep):
        b = s.button[0].lower()
        bname = "Left" if b == "l" else ("Right" if b == "r" else "Middle")
        if s.clicks == 0:
            return f"Move to ({s.x},{s.y})" + (" human" if s.human else "")
        return f"{bname} x{s.clicks} @ ({s.x},{s.y}) hold {s.hold}ms" + (" human" if s.human else "")
    if isinstance(s, KeyStep):
        if s.count <= 1:
            return f"'{s.key}'"
        return f"'{s.key}' x{s.count} every {s.interval}ms"
    if isinstance(s, CmdStep):
        cmd = s.command if len(s.command) <= 40 else s.command[:39] + "…"
        return cmd
    if isinstance(s, WindowStep):
        title = s.title if len(s.title) <= 28 else s.title[:27] + "…"
        return f"{s.action} '{title}'"
    if isinstance(s, SleepStep):
        if s.random:
            return f"{s.duration}-{s.duration_max}ms random"
        return f"{s.duration}ms"
    return f"{s.duration}ms"


def parse_send(spec: str):
    out = []
    mods = []
    i = 0
    while i < len(spec):
        ch = spec[i]
        if ch in SEND_MODS:
            mods.append(SEND_MODS[ch])
            i += 1
            continue
        if ch == "{":
            j = spec.find("}", i)
            if j == -1:
                break
            name = spec[i + 1 : j].upper()
            key = SEND_SPECIAL.get(name)
            if key is None and re.fullmatch(r"F\d+", name):
                key = name.lower()
            if key is None:
                mods = []
            else:
                out.append((tuple(mods), key))
                mods = []
            i = j + 1
            continue
        out.append((tuple(mods), ch))
        mods = []
        i += 1
    return out


def do_send(spec: str) -> None:
    for mods, key in parse_send(spec):
        if mods:
            pyautogui.hotkey(*mods, key, _pause=False)
        else:
            pyautogui.press(key, _pause=False)
