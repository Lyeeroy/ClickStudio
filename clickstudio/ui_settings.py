import keyboard
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    RadioButton,
    SpinBox,
    TitleLabel,
    ToolButton,
)

from .editors import _REC_MODS, _rec_key_name, _rec_token_spec
from .settings import AppSettings


class _HotkeyField(QWidget):
    def __init__(self, initial: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.inp = LineEdit()
        self.inp.setText(initial)
        self.inp.setMinimumWidth(120)
        lay.addWidget(self.inp, 1)
        self.btn = ToolButton()
        self.btn.setText("REC")
        self.btn.setFixedWidth(58)
        self.btn.setToolTip("Press REC, then the hotkey (ESC cancels)")
        self.btn.clicked.connect(self._toggle)
        lay.addWidget(self.btn)
        self._hook = None
        self._mods = set()
        self._held = set()

    def value(self) -> str:
        return self.inp.text().strip()

    def _toggle(self) -> None:
        if self._hook is None:
            self._start()
        else:
            self._stop(False)

    def _start(self) -> None:
        if self._hook is not None:
            return
        self._mods.clear()
        self._held.clear()

        def on_event(e):
            name = _rec_key_name(e.name)
            if not name:
                return
            if e.event_type == "down":
                self._held.add(name)
                if name == "esc":
                    self._stop(False)
                    return
                if name in _REC_MODS:
                    self._mods.add(name)
                else:
                    self._stop(True, _rec_token_spec(self._mods, name))
            else:
                self._held.discard(name)
                self._mods.discard(name)

        try:
            self._hook = keyboard.hook(on_event)
        except Exception:
            return
        self.btn.setText("...")
        self.btn.setToolTip("Recording - press a key (ESC cancels)")

    def _stop(self, commit: bool, spec: str = "") -> None:
        if self._hook is None:
            return
        h = self._hook
        self._hook = None
        try:
            keyboard.unhook(h)
        except Exception:
            pass
        self.btn.setText("REC")
        self.btn.setToolTip("Press REC, then the hotkey (ESC cancels)")
        if commit and spec:
            self.inp.setText(spec)


class SettingsInterface(QWidget):
    saved = pyqtSignal(object)

    def __init__(self, current: AppSettings, parent=None):
        super().__init__(parent)
        self.setObjectName("settings-interface")
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 36, 36, 24)
        root.setSpacing(14)
        root.addWidget(TitleLabel("Settings"))

        card = CardWidget(self)
        g = QGridLayout(card)
        g.setVerticalSpacing(14)
        g.setHorizontalSpacing(18)

        g.addWidget(BodyLabel("Capture coords hotkey:"), 0, 0)
        self.cap_field = _HotkeyField(current.cap_hk)
        g.addWidget(self.cap_field, 0, 1)

        g.addWidget(BodyLabel("Play/Pause hotkey:"), 1, 0)
        self.play_field = _HotkeyField(current.play_hk)
        g.addWidget(self.play_field, 1, 1)

        g.addWidget(BodyLabel("Stop is always ESC."), 2, 0, 1, 2)

        self.rb_inf = RadioButton("Loop forever")
        self.rb_n = RadioButton("Loop this many times:")
        self.in_loop = SpinBox()
        self.in_loop.setRange(1, 999999)
        self.in_loop.setValue(current.loop_count)
        (self.rb_inf if current.loop_inf else self.rb_n).setChecked(True)
        g.addWidget(self.rb_inf, 3, 0, 1, 2)
        g.addWidget(self.rb_n, 4, 0)
        g.addWidget(self.in_loop, 4, 1)
        self.rb_inf.toggled.connect(lambda on: self.in_loop.setEnabled(not on))
        self.in_loop.setEnabled(not current.loop_inf)

        save_btn = PrimaryPushButton(FIF.SAVE, "Save")
        save_btn.clicked.connect(self._emit_saved)
        g.addWidget(save_btn, 5, 0, 1, 2)

        root.addWidget(card)
        root.addStretch(1)

    def _emit_saved(self) -> None:
        s = AppSettings(
            cap_hk=self.cap_field.value(),
            play_hk=self.play_field.value(),
            loop_inf=self.rb_inf.isChecked(),
            loop_count=self.in_loop.value(),
        )
        self.saved.emit(s)
