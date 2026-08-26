import ctypes
import ctypes.wintypes
import queue
import re
import threading

import keyboard
import pyautogui
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    CompactSpinBox,
    FluentIcon as FIF,
    InfoBar,
    LineEdit,
    PrimaryPushButton,
    PrimaryToolButton,
    PushButton,
    SubtitleLabel,
    SwitchButton,
    ToolButton,
    isDarkTheme,
)
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .models import KeyStep, MouseStep, WINDOW_ACTIONS


class _QuietSpinBox(CompactSpinBox):
    def focusInEvent(self, e) -> None:
        QAbstractSpinBox.focusInEvent(self, e)


def _spin(lo: int, hi: int) -> CompactSpinBox:
    s = _QuietSpinBox()
    s.setRange(lo, hi)
    s.setAlignment(Qt.AlignmentFlag.AlignCenter)
    s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    s.setSymbolVisible(False)
    return s

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32")

WM_LBUTTONDOWN = 0x0201
WM_QUIT = 0x0012
WH_MOUSE_LL = 14


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.LPARAM,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
)

user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    _HOOKPROC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
user32.CallNextHookEx.restype = ctypes.wintypes.LPARAM
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
GA_ROOT = 2
user32.WindowFromPoint.restype = ctypes.wintypes.HWND
user32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
user32.GetAncestor.restype = ctypes.wintypes.HWND
user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]


def _root_hwnd_at(x: int, y: int):
    pt = ctypes.wintypes.POINT(x, y)
    return user32.GetAncestor(user32.WindowFromPoint(pt), GA_ROOT)


class _WinMouseHook:
    def __init__(self, on_left_down):
        self.on_left_down = on_left_down
        self._thread = None
        self._tid = 0
        self._hook = None
        self._proc = None
        self._active = False
        self._ready = threading.Event()

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        self._ready.set()
        self._proc = _HOOKPROC(self._cb)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        if not self._hook:
            self._active = False
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
            return
        self._active = True
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        self._active = False

    def _cb(self, ncode, wparam, lparam):
        if ncode >= 0 and wparam == WM_LBUTTONDOWN:
            info = ctypes.cast(lparam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
            try:
                self.on_left_down(int(info.pt.x), int(info.pt.y))
            except Exception:
                pass
        return user32.CallNextHookEx(None, ncode, wparam, lparam)

    def stop(self) -> None:
        self._ready.wait(timeout=1)
        tid = self._tid
        if tid:
            user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._tid = 0
        self._active = False


def _field_label(text: str) -> BodyLabel:
    lbl = BodyLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _field_row(label: str, widget, minw: int = 100) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(8)
    h.addWidget(_field_label(label))
    widget.setMinimumWidth(minw)
    h.addWidget(widget, 1)
    return h


def _set_row_visible(row: QHBoxLayout, on: bool) -> None:
    for i in range(row.count()):
        w = row.itemAt(i).widget()
        if w is not None:
            w.setVisible(on)


def _tip(text: str) -> QLabel:
    tip = BodyLabel(text)
    tip.setWordWrap(True)
    tip.setStyleSheet("color: gray; font-size: 12px;")
    return tip


def _button_row(ok_text: str, ok_cb, cancel_cb) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addStretch(1)
    ok = PrimaryPushButton(ok_text)
    ok.setFixedWidth(86)
    ok.clicked.connect(ok_cb)
    cancel = PushButton("Cancel")
    cancel.setFixedWidth(86)
    cancel.clicked.connect(cancel_cb)
    row.addWidget(ok)
    row.addWidget(cancel)
    return row


_REC_MOD_ORDER = ("ctrl", "alt", "shift", "win")
_REC_MOD_PREFIX = {"ctrl": "^", "alt": "!", "shift": "+", "win": "#"}
_REC_MODS = frozenset(_REC_MOD_ORDER)
_REC_SPECIAL = {
    "enter": "ENTER",
    "tab": "TAB",
    "space": "SPACE",
    "esc": "ESC",
    "delete": "DEL",
    "backspace": "BACKSPACE",
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "home": "HOME",
    "end": "END",
    "pageup": "PGUP",
    "pagedown": "PGDN",
    "insert": "INSERT",
}


def _rec_key_name(raw: str) -> str:
    n = raw.strip().lower()
    for p in ("left ", "right "):
        if n.startswith(p):
            n = n[len(p):]
            break
    return {"windows": "win", "return": "enter"}.get(n, n)


def _rec_token_spec(mods, name) -> str:
    spec = "".join(_REC_MOD_PREFIX[m] for m in _REC_MOD_ORDER if m in mods)
    if len(name) == 1:
        return spec + name
    token = _REC_SPECIAL.get(name)
    if token is None and re.fullmatch(r"f\d+", name):
        token = name.upper()
    if token is None:
        return ""
    return f"{spec}{{{token}}}"


class MouseCaptureSession(QObject):
    position_changed = pyqtSignal(int, int)
    captured = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events = queue.Queue()
        self._hook = None
        self._hwnd = None
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._drain)

    def _update_hwnd(self) -> None:
        p = self.parent()
        if p is None:
            return
        try:
            wid = p.window().winId()
            self._hwnd = int(wid) if wid else None
        except Exception:
            pass

    def start(self) -> None:
        if self._hook is not None:
            return
        self._update_hwnd()
        events = self._events

        def on_left_down(x: int, y: int) -> None:
            events.put(("cap", x, y))

        self._hook = _WinMouseHook(on_left_down)
        self._hook.start()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        hook = self._hook
        self._hook = None
        if hook is not None:
            try:
                hook.stop()
            except Exception:
                pass

    @property
    def running(self) -> bool:
        return self._hook is not None and self._hook.active

    def _drain(self) -> None:
        self._update_hwnd()
        try:
            pos = pyautogui.position()
            self.position_changed.emit(pos.x, pos.y)
        except Exception:
            pass
        while True:
            try:
                kind, x, y = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "cap":
                if self._hwnd is not None:
                    try:
                        if _root_hwnd_at(x, y) == self._hwnd:
                            continue
                    except Exception:
                        pass
                self.captured.emit(x, y)


class _StepEditorCard(CardWidget):
    def _normalBackgroundColor(self):
        return QColor(0, 0, 0, 70) if isDarkTheme() else QColor(243, 243, 243)

    def _hoverBackgroundColor(self):
        return self._normalBackgroundColor()

    def _pressedBackgroundColor(self):
        return self._normalBackgroundColor()


class MouseEditor(_StepEditorCard):
    committed = pyqtSignal()
    cancelled = pyqtSignal()
    step_captured = pyqtSignal(object)

    def __init__(self, cap_hk: str, parent=None):
        super().__init__(parent)
        self.step: MouseStep | None = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        v.addWidget(SubtitleLabel("Mouse Step"))

        self.lbl_live = BodyLabel("")
        self.lbl_live.setStyleSheet("color: gray;")
        v.addWidget(self.lbl_live)

        auto_row = QHBoxLayout()
        self.sw_auto = SwitchButton("Auto-add")
        self.sw_auto.setOnText("Auto-add")
        self.sw_auto.setOffText("Auto-add")
        self.sw_auto.checkedChanged.connect(self._set_auto)
        auto_row.addWidget(self.sw_auto)
        auto_row.addStretch(1)
        v.addLayout(auto_row)
        self._auto = False

        human_row = QHBoxLayout()
        self.sw_human = SwitchButton("Simulate human movement")
        self.sw_human.setOnText("Simulate human movement")
        self.sw_human.setOffText("Simulate human movement")
        human_row.addWidget(self.sw_human)
        human_row.addStretch(1)
        v.addLayout(human_row)

        self.in_x = _spin(-100000, 100000)
        self.in_y = _spin(-100000, 100000)
        xy = QHBoxLayout()
        xy.setSpacing(8)
        xy.addWidget(_field_label("X:"), 0)
        xy.addWidget(self.in_x, 1)
        xy.addSpacing(6)
        xy.addWidget(_field_label("Y:"), 0)
        xy.addWidget(self.in_y, 1)
        v.addLayout(xy)

        self.cb_btn = ComboBox()
        self.cb_btn.addItems(["left", "right", "middle"])
        self.clk = _spin(0, 99)
        self.in_hold = _spin(0, 60000)
        self.in_delay = _spin(0, 600000)

        v.addLayout(_field_row("Button:", self.cb_btn))
        v.addLayout(_field_row("Clicks:", self.clk))
        self.row_hold = _field_row("Hold (ms):", self.in_hold)
        v.addLayout(self.row_hold)
        v.addLayout(_field_row("Delay (ms):", self.in_delay))
        v.addWidget(_tip(f"left-click anywhere to grab coords (or press {cap_hk})"))
        v.addLayout(_button_row("Add", self.commit, self.cancelled.emit))
        self.clk.valueChanged.connect(lambda v: _set_row_visible(self.row_hold, v > 1))
        _set_row_visible(self.row_hold, False)

        self.session = MouseCaptureSession(self)
        self.session.position_changed.connect(self._on_pos)
        self.session.captured.connect(self._on_captured)
        self.hide()

    def open_for(self, step: MouseStep, ok_text: str = "Add") -> None:
        self.step = step
        for b in self.findChildren(PrimaryPushButton):
            b.setText(ok_text)
            break
        self.fields_load(step)
        pos = pyautogui.position()
        self._on_pos(pos.x, pos.y)
        if self._auto:
            self.lbl_live.setText("AUTO: every click adds a step")
        self.setVisible(True)

    def fields_load(self, s: MouseStep) -> None:
        self.in_x.setValue(s.x)
        self.in_y.setValue(s.y)
        self.cb_btn.setCurrentText(s.button if s.button in ("left", "right", "middle") else "left")
        self.clk.setValue(max(0, s.clicks))
        self.in_hold.setValue(max(0, s.hold))
        self.in_delay.setValue(max(0, s.delay))
        self.sw_human.setChecked(bool(s.human))
        _set_row_visible(self.row_hold, self.clk.value() > 1)

    def close_editor(self) -> None:
        self.setVisible(False)
        self.session.stop()
        self.step = None

    def is_open(self) -> bool:
        return self.isVisible()

    def fill_coords(self, x: int, y: int) -> None:
        self.in_x.setValue(x)
        self.in_y.setValue(y)
        self._on_pos(x, y)

    def commit(self) -> None:
        if self.step is None:
            return
        self.step.x = self.in_x.value()
        self.step.y = self.in_y.value()
        self.step.button = self.cb_btn.currentText()
        self.step.clicks = self.clk.value()
        self.step.hold = self.in_hold.value()
        self.step.delay = self.in_delay.value()
        self.step.human = self.sw_human.isChecked()
        self.committed.emit()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.session.start()

    def hideEvent(self, e) -> None:
        self.session.stop()
        super().hideEvent(e)

    def _set_auto(self, on: bool) -> None:
        self._auto = bool(on)
        if on and self.isVisible():
            self.lbl_live.setText("AUTO: every click adds a step")

    def _on_pos(self, x: int, y: int) -> None:
        self.lbl_live.setText(f"cursor at  X {x}   Y {y}")

    def _on_captured(self, x: int, y: int) -> None:
        if self.step is None:
            return
        if self._auto:
            step = MouseStep(
                x=x,
                y=y,
                button=self.cb_btn.currentText(),
                clicks=self.clk.value(),
                hold=self.in_hold.value(),
                delay=self.in_delay.value(),
                human=self.sw_human.isChecked(),
            )
            self.lbl_live.setText(f"auto-added  X {x}  Y {y}")
            self.step_captured.emit(step)
        else:
            self.step.x = x
            self.step.y = y
            self.fill_coords(x, y)


class KeyEditor(_StepEditorCard):
    committed = pyqtSignal()
    cancelled = pyqtSignal()
    rec_preview = pyqtSignal(str)
    rec_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step: KeyStep | None = None
        self._rec_hook = None
        self._rec_mods = set()
        self._rec_tokens = []
        self._rec_last = None
        self._rec_held = set()
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        v.addWidget(SubtitleLabel("Keyboard Step"))

        self.lbl_rec = BodyLabel("")
        self.lbl_rec.setStyleSheet("color: gray;")
        v.addWidget(self.lbl_rec)

        self.in_key = LineEdit()
        self.in_cnt = _spin(1, 999)
        self.in_ivl = _spin(0, 60000)
        self.in_delay = _spin(0, 600000)

        krow = QHBoxLayout()
        krow.setSpacing(8)
        krow.addWidget(_field_label("Key(s):"))
        self.in_key.setMinimumWidth(100)
        krow.addWidget(self.in_key, 1)
        self.btn_rec_idle = ToolButton()
        self.btn_rec_idle.setText("REC")
        self.btn_rec_idle.setFixedWidth(58)
        self.btn_rec_idle.setToolTip("Record keys - ESC or pause finishes")
        self.btn_rec_idle.clicked.connect(self._toggle_record)
        self.btn_rec_live = PrimaryToolButton()
        self.btn_rec_live.setText("REC")
        self.btn_rec_live.setFixedWidth(58)
        self.btn_rec_live.setToolTip("Finish & insert")
        self.btn_rec_live.clicked.connect(self._toggle_record)
        self._rec_stack = QWidget(self)
        self._rec_lay = QStackedLayout(self._rec_stack)
        self._rec_lay.addWidget(self.btn_rec_idle)
        self._rec_lay.addWidget(self.btn_rec_live)
        self._rec_lay.setCurrentWidget(self.btn_rec_idle)
        krow.addWidget(self._rec_stack)
        v.addLayout(krow)

        v.addLayout(_field_row("Times:", self.in_cnt))
        self.row_every = _field_row("Every (ms):", self.in_ivl)
        v.addLayout(self.row_every)
        v.addLayout(_field_row("Delay (ms):", self.in_delay))
        v.addWidget(_tip("(e.g. a, {ENTER}, {F5}, ^c)"))
        v.addLayout(_button_row("Add", self.commit, self.cancelled.emit))
        self.in_cnt.valueChanged.connect(lambda v: _set_row_visible(self.row_every, v > 1))
        _set_row_visible(self.row_every, False)
        self.rec_preview.connect(
            lambda s: self.lbl_rec.setText(f"{s}   (release all keys to insert)")
        )
        self.rec_finished.connect(lambda: self._stop_record(True))
        self.hide()

    def open_for(self, step: KeyStep, ok_text: str = "Add") -> None:
        self.step = step
        for b in self.findChildren(PrimaryPushButton):
            b.setText(ok_text)
            break
        self.in_key.setText(step.key)
        self.in_cnt.setValue(max(1, step.count))
        self.in_ivl.setValue(max(0, step.interval))
        self.in_delay.setValue(max(0, step.delay))
        _set_row_visible(self.row_every, self.in_cnt.value() > 1)
        self.setVisible(True)

    def close_editor(self) -> None:
        self._stop_record(False)
        self.setVisible(False)
        self.step = None

    def is_open(self) -> bool:
        return self.isVisible()

    def _toggle_record(self) -> None:
        if self._rec_hook is None:
            self._start_record()
        else:
            self._stop_record(True)

    def _start_record(self) -> None:
        if self._rec_hook is not None:
            return
        self._rec_mods.clear()
        self._rec_tokens.clear()
        self._rec_last = None
        self._rec_held.clear()

        def on_event(e):
            name = _rec_key_name(e.name)
            if not name:
                return
            if e.event_type == "down":
                self._rec_held.add(name)
                if name in _REC_MODS:
                    self._rec_mods.add(name)
                else:
                    tok = (frozenset(self._rec_mods), name)
                    if tok != self._rec_last:
                        self._rec_last = tok
                        self._rec_tokens.append(tok)
                        self.rec_preview.emit(
                            "".join(_rec_token_spec(m, n) for m, n in self._rec_tokens)
                        )
            else:
                self._rec_held.discard(name)
                self._rec_mods.discard(name)
                self._rec_last = None
                if not self._rec_held and self._rec_tokens:
                    self.rec_finished.emit()

        try:
            self._rec_hook = keyboard.hook(on_event)
        except Exception:
            return
        self._rec_lay.setCurrentWidget(self.btn_rec_live)
        self.lbl_rec.setText("REC: press and hold keys - release all to insert")

    def _stop_record(self, commit: bool) -> None:
        if self._rec_hook is None:
            return
        handle = self._rec_hook
        self._rec_hook = None
        spec = "".join(_rec_token_spec(m, n) for m, n in self._rec_tokens)
        self._rec_mods.clear()
        self._rec_tokens.clear()
        try:
            keyboard.unhook(handle)
        except Exception:
            pass
        self._rec_lay.setCurrentWidget(self.btn_rec_idle)
        if commit and spec:
            self.in_key.setText(spec)
            self.lbl_rec.setText(f"captured {spec}")

    def commit(self) -> None:
        if self.step is None:
            return
        key = self.in_key.text().strip()
        if not key:
            InfoBar.warning(title="Click Studio", content="Enter a key.", parent=self, duration=2000)
            return
        self.step.key = key
        self.step.count = self.in_cnt.value()
        self.step.interval = self.in_ivl.value()
        self.step.delay = self.in_delay.value()
        self.committed.emit()


class SleepEditor(_StepEditorCard):
    committed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        v.addWidget(SubtitleLabel("Sleep Step"))

        self.in_dur = _spin(0, 3600000)
        self.in_dur_min = _spin(0, 3600000)
        self.in_dur_max = _spin(0, 3600000)
        self.in_delay = _spin(0, 600000)

        rand_row = QHBoxLayout()
        self.sw_rand = SwitchButton("Random duration")
        self.sw_rand.setOnText("Random duration")
        self.sw_rand.setOffText("Random duration")
        self.sw_rand.checkedChanged.connect(self._on_rand)
        rand_row.addWidget(self.sw_rand)
        rand_row.addStretch(1)
        v.addLayout(rand_row)

        self.row_dur = _field_row("Duration (ms):", self.in_dur)
        self.row_dmin = _field_row("Min (ms):", self.in_dur_min)
        self.row_dmax = _field_row("Max (ms):", self.in_dur_max)
        v.addLayout(self.row_dur)
        v.addLayout(self.row_dmin)
        v.addLayout(self.row_dmax)
        _set_row_visible(self.row_dmin, False)
        _set_row_visible(self.row_dmax, False)
        v.addLayout(_field_row("Delay (ms):", self.in_delay))
        v.addWidget(_tip("pauses the sequence before continuing"))
        v.addLayout(_button_row("Add", self.commit, self.cancelled.emit))
        self.hide()

    def _on_rand(self, on: bool) -> None:
        _set_row_visible(self.row_dur, not on)
        _set_row_visible(self.row_dmin, on)
        _set_row_visible(self.row_dmax, on)
        if on:
            self.in_dur_min.setValue(self.in_dur.value())
            if self.in_dur_max.value() < self.in_dur_min.value():
                self.in_dur_max.setValue(self.in_dur_min.value())

    def open_for(self, step, ok_text: str = "Add") -> None:
        self.step = step
        for b in self.findChildren(PrimaryPushButton):
            b.setText(ok_text)
            break
        self.in_dur.setValue(max(0, step.duration))
        self.in_dur_min.setValue(max(0, step.duration))
        self.in_dur_max.setValue(max(0, step.duration_max))
        self.in_delay.setValue(max(0, step.delay))
        self.sw_rand.setChecked(bool(step.random))
        self._on_rand(self.sw_rand.isChecked())
        self.setVisible(True)

    def close_editor(self) -> None:
        self.setVisible(False)
        self.step = None

    def is_open(self) -> bool:
        return self.isVisible()

    def commit(self) -> None:
        if self.step is None:
            return
        self.step.duration = self.in_dur.value()
        self.step.duration_max = self.in_dur_max.value()
        self.step.random = self.sw_rand.isChecked()
        self.step.delay = self.in_delay.value()
        self.committed.emit()


class CmdEditor(_StepEditorCard):
    committed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        v.addWidget(SubtitleLabel("Command Step"))

        self.in_cmd = LineEdit()
        self.in_cmd.setPlaceholderText("e.g. notepad.exe")
        self.in_delay = _spin(0, 600000)

        v.addLayout(_field_row("Command:", self.in_cmd))
        v.addLayout(_field_row("Delay (ms):", self.in_delay))
        v.addWidget(_tip("runs in cmd.exe and waits until it exits"))
        v.addLayout(_button_row("Add", self.commit, self.cancelled.emit))
        self.hide()

    def open_for(self, step, ok_text: str = "Add") -> None:
        self.step = step
        for b in self.findChildren(PrimaryPushButton):
            b.setText(ok_text)
            break
        self.in_cmd.setText(step.command)
        self.in_delay.setValue(max(0, step.delay))
        self.setVisible(True)

    def close_editor(self) -> None:
        self.setVisible(False)
        self.step = None

    def is_open(self) -> bool:
        return self.isVisible()

    def commit(self) -> None:
        if self.step is None:
            return
        cmd = self.in_cmd.text().strip()
        if not cmd:
            InfoBar.warning(title="Click Studio", content="Enter a command.", parent=self, duration=2000)
            return
        self.step.command = cmd
        self.step.delay = self.in_delay.value()
        self.committed.emit()


class WindowEditor(_StepEditorCard):
    committed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)

        v.addWidget(SubtitleLabel("Window Step"))

        self.in_title = LineEdit()
        self.in_title.setPlaceholderText("e.g. Minecraft")
        self.cb_action = ComboBox()
        self.cb_action.addItems(list(WINDOW_ACTIONS))
        self.in_delay = _spin(0, 600000)

        v.addLayout(_field_row("Title:", self.in_title))
        v.addLayout(_field_row("Action:", self.cb_action))
        v.addLayout(_field_row("Delay (ms):", self.in_delay))
        v.addWidget(_tip("partial title match, not case-sensitive"))
        v.addLayout(_button_row("Add", self.commit, self.cancelled.emit))
        self.hide()

    def open_for(self, step, ok_text: str = "Add") -> None:
        self.step = step
        for b in self.findChildren(PrimaryPushButton):
            b.setText(ok_text)
            break
        self.in_title.setText(step.title)
        self.cb_action.setCurrentText(step.action if step.action in WINDOW_ACTIONS else "focus")
        self.in_delay.setValue(max(0, step.delay))
        self.setVisible(True)

    def close_editor(self) -> None:
        self.setVisible(False)
        self.step = None

    def is_open(self) -> bool:
        return self.isVisible()

    def commit(self) -> None:
        if self.step is None:
            return
        title = self.in_title.text().strip()
        if not title:
            InfoBar.warning(title="Click Studio", content="Enter a window title.", parent=self, duration=2000)
            return
        self.step.title = title
        self.step.action = self.cb_action.currentText()
        self.step.delay = self.in_delay.value()
        self.committed.emit()
