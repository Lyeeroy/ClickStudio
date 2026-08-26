import math
import random
import subprocess
import threading
import time
import traceback

import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal

from .models import CmdStep, KeyStep, MouseStep, SleepStep, WindowStep, do_send
from .winman import apply_window_action, find_window
from .settings import ERROR_LOG


def human_move_to(tx: int, ty: int, stop_check=None, step_sleep: float = 0.004) -> None:
    """Move the mouse the way a person would: a curved, jittery path with
    uneven speed and a small overshoot that gets corrected at the end."""
    cur = pyautogui.position()
    sx, sy = cur.x, cur.y
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy)

    if dist < 2:
        if dist >= 1:
            pyautogui.moveTo(tx, ty, duration=0.0, _pause=False)
        return

    # perpendicular unit vector, used to bend the path away from the straight line
    nx, ny = -dy / dist, dx / dist
    curve = dist * random.uniform(0.15, 0.5) * random.choice((-1, 1))

    c1x = sx + dx * random.uniform(0.25, 0.4) + nx * curve * random.uniform(0.4, 1.0)
    c1y = sy + dy * random.uniform(0.25, 0.4) + ny * curve * random.uniform(0.4, 1.0)
    c2x = sx + dx * random.uniform(0.6, 0.75) + nx * curve * random.uniform(0.4, 1.0)
    c2y = sy + dy * random.uniform(0.6, 0.75) + ny * curve * random.uniform(0.4, 1.0)

    def bez(t: float):
        u = 1.0 - t
        bx = u * u * u * sx + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * tx
        by = u * u * u * sy + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * ty
        return bx, by

    steps = max(18, int(dist / 7))
    t = 0.0
    prevx, prevy = sx, sy
    while t < 1.0:
        if stop_check and stop_check():
            return
        # ease in/out: slow at the ends, faster in the middle, plus random noise
        speed = 0.2 + 4.0 * t * (1.0 - t)
        t += random.uniform(0.008, 0.03) * speed
        if t > 1.0:
            t = 1.0
        bx, by = bez(t)
        # jitter, fading out as we approach the target so we land precisely
        j = max(0.0, 1.0 - t * 1.2) * random.uniform(0.0, 3.0)
        ang = random.uniform(0.0, math.tau)
        px = bx + math.cos(ang) * j
        py = by + math.sin(ang) * j
        pyautogui.moveTo(px, py, duration=0.0, _pause=False)
        # occasional hesitation, like a person re-aiming
        if random.random() < 0.04:
            time.sleep(random.uniform(0.02, 0.09))
        else:
            time.sleep(step_sleep)
        prevx, prevy = px, py

    # overshoot the target a little, then correct back onto it
    if dist > 60 and random.random() < 0.6:
        vx, vy = tx - prevx, ty - prevy
        mlen = math.hypot(vx, vy) or 1.0
        ov = dist * random.uniform(0.02, 0.06)
        ox = tx + vx / mlen * ov * random.choice((-1, 1))
        oy = ty + vy / mlen * ov * random.choice((-1, 1))
        for k in range(1, 5):
            pyautogui.moveTo(
                tx + (ox - tx) * (k / 5.0), ty + (oy - ty) * (k / 5.0),
                duration=0.0, _pause=False,
            )
            time.sleep(step_sleep)
        for k in range(1, 5):
            pyautogui.moveTo(
                ox + (tx - ox) * (k / 5.0), oy + (ty - oy) * (k / 5.0),
                duration=0.0, _pause=False,
            )
            time.sleep(step_sleep)
    else:
        pyautogui.moveTo(tx, ty, duration=0.0, _pause=False)


class Player(QThread):
    progress = pyqtSignal(str)
    finished_run = pyqtSignal(str)

    def __init__(self, steps, loop_inf: bool, loop_count: int, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.loop_inf = loop_inf
        self.loop_count = max(1, loop_count)
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()

    @property
    def paused(self) -> bool:
        return self._pause_evt.is_set()

    def toggle_pause(self) -> bool:
        if self._pause_evt.is_set():
            self._pause_evt.clear()
        else:
            self._pause_evt.set()
        return self.paused

    def request_stop(self) -> None:
        self._stop_evt.set()
        self._pause_evt.clear()

    def _wait(self, ms: int) -> bool:
        if ms <= 0:
            return not self._stop_evt.is_set()
        deadline = time.monotonic() + ms / 1000.0
        while True:
            if self._stop_evt.is_set():
                return False
            if self._pause_evt.is_set():
                deadline += 0.02
            elif time.monotonic() >= deadline:
                return True
            time.sleep(0.01)

    def _exec(self, s) -> None:
        if isinstance(s, MouseStep):
            if s.human:
                human_move_to(s.x, s.y, stop_check=self._stop_evt.is_set)
            else:
                pyautogui.moveTo(s.x, s.y, duration=0.05, _pause=False)
            for c in range(s.clicks):
                pyautogui.mouseDown(button=s.button, _pause=False)
                ok = self._wait(max(0, s.hold))
                pyautogui.mouseUp(button=s.button, _pause=False)
                if not ok:
                    return
                if c < s.clicks - 1 and not self._wait(60):
                    return
        elif isinstance(s, KeyStep):
            for c in range(s.count):
                do_send(s.key)
                if c < s.count - 1 and not self._wait(s.interval):
                    return
        elif isinstance(s, SleepStep):
            dur = s.duration
            if s.random:
                lo = min(s.duration, s.duration_max)
                hi = max(s.duration, s.duration_max)
                dur = random.randint(lo, hi)
            self._wait(dur)
        elif isinstance(s, CmdStep):
            subprocess.run(s.command, shell=True)
        elif isinstance(s, WindowStep):
            hwnd = find_window(s.title)
            if hwnd:
                apply_window_action(hwnd, s.action)

    def run(self) -> None:
        total = len(self.steps)
        loops = 0
        try:
            while not self._stop_evt.is_set():
                for idx, s in enumerate(self.steps):
                    if not self._wait(s.delay):
                        self.finished_run.emit("Stopped")
                        return
                    self._exec(s)
                    self.progress.emit(f"Running step {idx + 1}/{total}  loop {loops + 1}")
                loops += 1
                if not self.loop_inf and loops >= self.loop_count:
                    self.finished_run.emit(f"Finished - {loops} loop(s)")
                    return
                if not self._wait(120):
                    break
        except Exception:
            try:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write(traceback.format_exc() + "\n")
            except OSError:
                pass
            self.finished_run.emit("Error during playback - see clickstudio_error.log")
            return
        self.finished_run.emit("Stopped")
