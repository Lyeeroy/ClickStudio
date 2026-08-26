from PyQt6.QtCore import QObject, pyqtSignal, QTimer

import keyboard

from .bridge import EventBridge


class Hotkeys(QObject):
    capture_pressed = pyqtSignal()
    play_pressed = pyqtSignal()
    stop_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handles = []
        self._bridge = _HotkeyBridge(self)

    def register(self, cap: str, play: str) -> None:
        self.unregister()
        push = self._bridge.push
        self._handles.append(keyboard.add_hotkey(cap.lower(), lambda: push("cap")))
        self._handles.append(keyboard.add_hotkey(play.lower(), lambda: push("play")))
        self._handles.append(keyboard.add_hotkey("esc", lambda: push("stop")))
        self._bridge.start()

    def unregister(self) -> None:
        self._bridge.stop()
        for h in self._handles:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        self._handles = []


class _HotkeyBridge(EventBridge):
    def __init__(self, owner: "Hotkeys"):
        super().__init__(owner)
        self.owner = owner

    def _drain(self) -> None:
        while True:
            try:
                item = self.queue.get_nowait()
            except Exception:
                break
            if item == "cap":
                self.owner.capture_pressed.emit()
            elif item == "play":
                self.owner.play_pressed.emit()
            elif item == "stop":
                self.owner.stop_pressed.emit()
