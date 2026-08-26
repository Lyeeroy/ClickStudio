import subprocess
import threading
import time
import traceback

import pyautogui
from PyQt6.QtCore import QThread, pyqtSignal

from .models import CmdStep, KeyStep, MouseStep, SleepStep, WindowStep, do_send
from .winman import apply_window_action, find_window
from .settings import ERROR_LOG


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
            self._wait(s.duration)
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
