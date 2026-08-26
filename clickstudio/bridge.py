import queue

from PyQt6.QtCore import QObject, pyqtSignal


class EventBridge(QObject):
    def __init__(self, parent=None, interval_ms: int = 25):
        super().__init__(parent)
        self.queue = queue.Queue()
        self._timer = None
        self._interval_ms = interval_ms

    def start(self) -> None:
        if self._timer is None:
            from PyQt6.QtCore import QTimer

            self._timer = QTimer(self)
            self._timer.setInterval(self._interval_ms)
            self._timer.timeout.connect(self._drain)
        self._timer.start()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def push(self, item) -> None:
        self.queue.put(item)

    def _drain(self) -> None:
        raise NotImplementedError
