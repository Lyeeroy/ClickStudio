from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    PrimaryPushButton,
    RadioButton,
    SpinBox,
    TitleLabel,
)

from .settings import CAP_CHOICES, PLAY_CHOICES, AppSettings


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
        self.cb_cap = ComboBox()
        self.cb_cap.addItems(CAP_CHOICES)
        self.cb_cap.setCurrentText(current.cap_hk)
        g.addWidget(self.cb_cap, 0, 1)

        g.addWidget(BodyLabel("Play/Pause hotkey:"), 1, 0)
        self.cb_play = ComboBox()
        self.cb_play.addItems([p if p == "pause" else p.upper() for p in PLAY_CHOICES])
        cur = current.play_hk
        self.cb_play.setCurrentText(cur if cur == "pause" else cur.upper())
        g.addWidget(self.cb_play, 1, 1)

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
            cap_hk=self.cb_cap.currentText(),
            play_hk=self.cb_play.currentText(),
            loop_inf=self.rb_inf.isChecked(),
            loop_count=self.in_loop.value(),
        )
        self.saved.emit(s)
