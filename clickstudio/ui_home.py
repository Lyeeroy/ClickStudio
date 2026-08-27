import html
import time

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QDrag, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QPlainTextEdit,
    QSplitter,
    QSplitterHandle,
    QStackedLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    PrimaryPushButton,
    PushButton,
    RoundMenu,
    SmoothScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TableWidget,
    ToolButton,
    themeColor,
)

from .editors import CmdEditor, KeyEditor, MouseEditor, SleepEditor, WindowEditor
from .models import step_action_text, step_type_name


class _SplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hover = False
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if not self._hover:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pen = QPen(themeColor())
        pen.setWidth(2)
        painter.setPen(pen)
        x = w // 2
        painter.drawLine(x, 10, x, h - 10)


class _HSplitter(QSplitter):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(8)
        self.setChildrenCollapsible(False)
        self.setContentsMargins(0, 0, 0, 0)

    def createHandle(self):
        return _SplitterHandle(Qt.Orientation.Horizontal, self)


class AddButtonSlot(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon, text: str, parent=None):
        super().__init__(parent)
        self.plain = PushButton(icon, text)
        self.accent = PrimaryPushButton(icon, text)
        lay = QStackedLayout(self)
        for b in (self.plain, self.accent):
            b.setFixedHeight(34)
            b.clicked.connect(self.clicked.emit)
            lay.addWidget(b)
        lay.setCurrentWidget(self.plain)

    def set_accent(self, on: bool) -> None:
        self.layout().setCurrentWidget(self.accent if on else self.plain)

    def set_slot_enabled(self, on: bool) -> None:
        self.plain.setEnabled(on)
        self.accent.setEnabled(on)


class _StepsTable(TableWidget):
    row_dropped = pyqtSignal(int, int)
    edit_row = pyqtSignal(int)
    duplicate_row = pyqtSignal(int)
    delete_row = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._drop_row = -1
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def startDrag(self, actions) -> None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        rect = self.visualRect(rows[0])
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(rows))
        drag.setPixmap(self.viewport().grab(rect))
        drag.setHotSpot(self.viewport().mapFromGlobal(QCursor.pos()) - rect.topLeft())
        drag.exec(Qt.DropAction.CopyAction)

    def _target_row(self, pos) -> int:
        tgt = self.rowAt(pos.y())
        if tgt < 0:
            tgt = self.rowCount()
        else:
            rect = self.visualRect(self.model().index(tgt, 0))
            if pos.y() > rect.center().y():
                tgt += 1
        return tgt

    def _set_drop_row(self, row: int) -> None:
        if row != self._drop_row:
            self._drop_row = row
            self.viewport().update()

    def dragEnterEvent(self, e) -> None:
        if e.source() is not self:
            e.ignore()
            return
        self._set_drop_row(self._target_row(e.position().toPoint()))
        e.acceptProposedAction()

    def dragMoveEvent(self, e) -> None:
        if e.source() is not self:
            e.ignore()
            return
        self._set_drop_row(self._target_row(e.position().toPoint()))
        e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:
        self._set_drop_row(-1)
        super().dragLeaveEvent(e)

    def dropEvent(self, e) -> None:
        if e.source() is not self:
            e.ignore()
            return
        src = self.currentRow()
        tgt = self._drop_row
        self._set_drop_row(-1)
        if not (0 <= src < self.rowCount()) or tgt < 0:
            e.ignore()
            return
        dst = tgt - 1 if tgt > src else tgt
        if dst == src:
            e.ignore()
            return
        e.acceptProposedAction()
        self.row_dropped.emit(src, dst)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        r = self._drop_row
        rows = self.rowCount()
        if r < 0 or rows == 0:
            return
        if r >= rows:
            rect = self.visualRect(self.model().index(rows - 1, 0))
            y = rect.bottom() + 1
        else:
            rect = self.visualRect(self.model().index(r, 0))
            y = rect.top()
        if not rect.isValid():
            return
        w = self.viewport().width()
        try:
            col = themeColor()
        except Exception:
            col = QColor(0, 159, 170)
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(col, 2))
        p.drawLine(3, int(y), w - 3, int(y))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(3, y - 4), QPointF(3, y + 4), QPointF(9, y)]))
        p.drawPolygon(
            QPolygonF([QPointF(w - 3, y - 4), QPointF(w - 3, y + 4), QPointF(w - 9, y)])
        )

    def contextMenuEvent(self, e) -> None:
        row = self.rowAt(e.pos().y())
        if row < 0:
            return
        self.selectRow(row)
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FIF.EDIT, "Edit", triggered=lambda: self.edit_row.emit(row)))
        menu.addAction(Action(FIF.COPY, "Duplicate", triggered=lambda: self.duplicate_row.emit(row)))
        menu.addAction(Action(FIF.DELETE, "Delete", triggered=lambda: self.delete_row.emit(row)))
        menu.exec(e.globalPos())


class ConsolePanel(QFrame):
    MIN_H = 26
    DEFAULT_H = 110
    _ERR_KEYS = ("error", "cannot", "fail", "invalid")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consolePanel")
        self._drag_y = None
        self._start_h = self.DEFAULT_H

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("consoleHeader")
        self.header.setFixedHeight(26)
        self.header.setCursor(Qt.CursorShape.SizeVerCursor)
        h = QHBoxLayout(self.header)
        h.setContentsMargins(14, 0, 8, 0)
        h.setSpacing(6)
        self.lbl_title = CaptionLabel("CONSOLE")
        f = self.lbl_title.font()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
        f.setPointSize(9)
        self.lbl_title.setFont(f)
        h.addWidget(self.lbl_title)
        h.addStretch(1)
        self.btn_clear = ToolButton(FIF.ERASE_TOOL, self)
        self.btn_clear.setToolTip("Clear console")
        self.btn_clear.setFixedSize(22, 22)
        self.btn_clear.setIconSize(self.btn_clear.icon().actualSize(self.btn_clear.iconSize()))
        self.btn_clear.clicked.connect(lambda: self.output.clear())
        h.addWidget(self.btn_clear)

        self.output = QPlainTextEdit(self)
        self.output.setObjectName("consoleOutput")
        self.output.setReadOnly(True)
        self.output.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.output.setFrameShape(QFrame.Shape.NoFrame)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.output.setFont(font)
        self.output.setMaximumBlockCount(500)
        self.output.document().setDocumentMargin(0)

        v.addWidget(self.header)
        v.addWidget(self.output, 1)

        self.setStyleSheet(
            """
            #consolePanel {
                border-top: 1px solid rgba(0, 0, 0, 24);
                background-color: #ffffff;
            }
            #consoleHeader {
                border-bottom: 1px solid rgba(0, 0, 0, 12);
                background-color: rgba(250, 250, 250, 0.6);
            }
            #consoleOutput {
                background: transparent;
                color: #3b3b3b;
                border: none;
                padding: 4px 10px 6px 14px;
                selection-background-color: rgba(0, 159, 170, 0.30);
            }
            #consoleOutput QScrollBar:vertical {
                width: 7px;
                margin: 2px;
                background: transparent;
            }
            #consoleOutput QScrollBar::handle:vertical {
                min-height: 24px;
                border-radius: 2px;
                background: rgba(0, 0, 0, 60);
            }
            #consoleOutput QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 105);
            }
            #consoleOutput QScrollBar::sub-line:vertical,
            #consoleOutput QScrollBar::add-line:vertical {
                height: 0;
            }
            #consoleOutput QScrollBar::sub-page:vertical,
            #consoleOutput QScrollBar::add-page:vertical {
                background: transparent;
            }
            """
        )
        self.setFixedHeight(self.DEFAULT_H)

    def append_line(self, text: str) -> None:
        low = text.lower()
        color = "#c42b1c" if any(k in low for k in self._ERR_KEYS) else "#3b3b3b"
        stamp = time.strftime("%H:%M:%S")
        msg = html.escape(text)
        self.output.appendHtml(
            f'<span style="color:#9d9d9d;">[{stamp}]</span> '
            f'<span style="color:{color};">{msg}</span>'
        )
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _in_header(self, pos) -> bool:
        return pos.y() <= self.header.height() and pos.x() <= self.width()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._in_header(e.position().toPoint()):
            self._drag_y = e.globalPosition().toPoint().y()
            self._start_h = self.height()
            e.accept()
            return
        super().mousePressEvent(e)

    def _max_height(self) -> int:
        p = self.parentWidget()
        if p is None:
            return 480
        lay = p.layout()
        others_min = 0
        if lay is not None:
            others_min = max(0, lay.minimumSize().height() - self.height())
        return max(self.MIN_H + 40, p.height() - others_min)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_y is not None:
            dy = self._drag_y - e.globalPosition().toPoint().y()
            new_h = max(self.MIN_H, min(self._start_h + dy, self._max_height()))
            self.setFixedHeight(new_h)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_y = None
        super().mouseReleaseEvent(e)


class HomeInterface(QWidget):
    add_mouse_clicked = pyqtSignal()
    add_key_clicked = pyqtSignal()
    add_sleep_clicked = pyqtSignal()
    add_cmd_clicked = pyqtSignal()
    add_window_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    duplicate_clicked = pyqtSignal()
    up_clicked = pyqtSignal()
    down_clicked = pyqtSignal()
    run_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    import_clicked = pyqtSignal()
    export_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    help_clicked = pyqtSignal()
    editor_finished = pyqtSignal(bool)
    mouse_auto_added = pyqtSignal(object)
    row_dropped = pyqtSignal(int, int)

    def __init__(self, cap_hk: str, parent=None):
        super().__init__(parent)
        self.setObjectName("home-interface")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 16)
        root.setSpacing(12)

        self.table = _StepsTable(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Type", "Action", "Delay (ms)"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setWordWrap(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col, w in ((0, 44), (1, 72), (3, 92)):
            self.table.setColumnWidth(col, w)
        self.table.doubleClicked.connect(self.edit_clicked.emit)
        self.table.row_dropped.connect(self.row_dropped.emit)
        self.table.edit_row.connect(lambda _: self.edit_clicked.emit())
        self.table.duplicate_row.connect(self.duplicate_clicked.emit)
        self.table.delete_row.connect(lambda _: self.delete_clicked.emit())
        self.table.setMinimumHeight(320)

        self.console = ConsolePanel(self)

        self.mouse_editor = MouseEditor(cap_hk, self)
        self.key_editor = KeyEditor(self)
        self.sleep_editor = SleepEditor(self)
        self.cmd_editor = CmdEditor(self)
        self.window_editor = WindowEditor(self)
        self.mouse_editor.committed.connect(lambda: self.editor_finished.emit(True))
        self.mouse_editor.step_captured.connect(self.mouse_auto_added.emit)
        self.key_editor.committed.connect(lambda: self.editor_finished.emit(True))
        self.sleep_editor.committed.connect(lambda: self.editor_finished.emit(True))
        self.cmd_editor.committed.connect(lambda: self.editor_finished.emit(True))
        self.window_editor.committed.connect(lambda: self.editor_finished.emit(True))
        self.mouse_editor.cancelled.connect(lambda: self._editor_done())
        self.key_editor.cancelled.connect(lambda: self._editor_done())
        self.sleep_editor.cancelled.connect(lambda: self._editor_done())
        self.cmd_editor.cancelled.connect(lambda: self._editor_done())
        self.window_editor.cancelled.connect(lambda: self._editor_done())

        side_panel = QWidget(self)
        side_panel.setMinimumWidth(236)
        side_panel.setStyleSheet("background: transparent;")
        side = QVBoxLayout(side_panel)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)

        self.btn_add_mouse = AddButtonSlot(FIF.MOVE, "Add Mouse")
        self.btn_add_key = AddButtonSlot(FIF.COMMAND_PROMPT, "Add Keyboard")
        self.btn_add_sleep = AddButtonSlot(FIF.STOP_WATCH, "Add Sleep")
        self.btn_add_cmd = AddButtonSlot(FIF.DEVELOPER_TOOLS, "Add Cmd")
        self.btn_add_window = AddButtonSlot(FIF.BACK_TO_WINDOW, "Add Window")

        play_card = CardWidget(self)
        pv = QVBoxLayout(play_card)
        pv.setContentsMargins(16, 12, 16, 12)
        pv.setSpacing(8)
        pv.addWidget(SubtitleLabel("Playback"))
        prow = QHBoxLayout()
        self.btn_run = PrimaryPushButton(FIF.PLAY, "Run")
        self.btn_pause = PushButton(FIF.PAUSE, "Pause")
        prow.addWidget(self.btn_run)
        prow.addWidget(self.btn_pause)
        pv.addLayout(prow)
        self.btn_stop = PushButton(FIF.CLOSE, "STOP (ESC)")

        file_card = CardWidget(self)
        fv = QVBoxLayout(file_card)
        fv.setContentsMargins(16, 12, 16, 12)
        fv.setSpacing(8)
        fv.addWidget(SubtitleLabel("Files"))
        frow = QHBoxLayout()
        self.btn_import = PushButton(FIF.FOLDER_ADD, "Import")
        self.btn_export = PushButton(FIF.SAVE, "Export")
        frow.addWidget(self.btn_import)
        frow.addWidget(self.btn_export)
        fv.addLayout(frow)
        srow = QHBoxLayout()
        self.btn_settings = PushButton(FIF.SETTING, "Settings")
        self.btn_help = PushButton(FIF.INFO, "Help")
        srow.addWidget(self.btn_settings)
        srow.addWidget(self.btn_help)
        fv.addLayout(srow)

        side.addWidget(self.btn_add_mouse)
        side.addWidget(self.mouse_editor)
        side.addWidget(self.btn_add_key)
        side.addWidget(self.key_editor)
        side.addWidget(self.btn_add_sleep)
        side.addWidget(self.sleep_editor)
        side.addWidget(self.btn_add_cmd)
        side.addWidget(self.cmd_editor)
        side.addWidget(self.btn_add_window)
        side.addWidget(self.window_editor)

        ud = QHBoxLayout()
        self.btn_edit = PushButton(FIF.EDIT, "Edit")
        self.btn_delete = PushButton(FIF.DELETE, "Delete")
        ud.addWidget(self.btn_edit)
        ud.addWidget(self.btn_delete)
        side.addLayout(ud)
        ud2 = QHBoxLayout()
        self.btn_up = PushButton(FIF.UP, "Up")
        self.btn_down = PushButton(FIF.DOWN, "Down")
        ud2.addWidget(self.btn_up)
        ud2.addWidget(self.btn_down)
        side.addLayout(ud2)

        side.addSpacing(10)
        side.addWidget(play_card)
        side.addWidget(file_card)
        side.addStretch(1)

        scroll = SmoothScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(side_panel)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setMinimumWidth(258)

        top = _HSplitter(self)
        top.addWidget(self.table)
        top.addWidget(scroll)
        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 0)
        top.setCollapsible(0, False)
        top.setCollapsible(1, False)
        self.table.setMinimumWidth(360)
        root.addWidget(top)
        root.addWidget(self.console)

        self.btn_add_mouse.clicked.connect(self.add_mouse_clicked.emit)
        self.btn_add_key.clicked.connect(self.add_key_clicked.emit)
        self.btn_add_sleep.clicked.connect(self.add_sleep_clicked.emit)
        self.btn_add_cmd.clicked.connect(self.add_cmd_clicked.emit)
        self.btn_add_window.clicked.connect(self.add_window_clicked.emit)
        self.btn_edit.clicked.connect(self.edit_clicked.emit)
        self.btn_delete.clicked.connect(self.delete_clicked.emit)
        self.btn_up.clicked.connect(self.up_clicked.emit)
        self.btn_down.clicked.connect(self.down_clicked.emit)
        self.btn_run.clicked.connect(self.run_clicked.emit)
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_import.clicked.connect(self.import_clicked.emit)
        self.btn_export.clicked.connect(self.export_clicked.emit)
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        self.btn_help.clicked.connect(self.help_clicked.emit)

    def _editor_done(self) -> None:
        self.close_editors()
        self.editor_finished.emit(False)

    def editor_open(self) -> bool:
        return (
            self.mouse_editor.is_open()
            or self.key_editor.is_open()
            or self.sleep_editor.is_open()
            or self.cmd_editor.is_open()
            or self.window_editor.is_open()
        )

    def close_editors(self) -> None:
        if self.mouse_editor.is_open():
            self.mouse_editor.close_editor()
        if self.key_editor.is_open():
            self.key_editor.close_editor()
        if self.sleep_editor.is_open():
            self.sleep_editor.close_editor()
        if self.cmd_editor.is_open():
            self.cmd_editor.close_editor()
        if self.window_editor.is_open():
            self.window_editor.close_editor()

    def show_mouse_editor(self, step, ok_text: str = "Add") -> None:
        self.key_editor.close_editor()
        self.sleep_editor.close_editor()
        self.cmd_editor.close_editor()
        self.window_editor.close_editor()
        self.mouse_editor.open_for(step, ok_text)

    def show_key_editor(self, step, ok_text: str = "Add") -> None:
        self.mouse_editor.close_editor()
        self.sleep_editor.close_editor()
        self.cmd_editor.close_editor()
        self.window_editor.close_editor()
        self.key_editor.open_for(step, ok_text)

    def show_sleep_editor(self, step, ok_text: str = "Add") -> None:
        self.mouse_editor.close_editor()
        self.key_editor.close_editor()
        self.cmd_editor.close_editor()
        self.window_editor.close_editor()
        self.sleep_editor.open_for(step, ok_text)

    def show_cmd_editor(self, step, ok_text: str = "Add") -> None:
        self.mouse_editor.close_editor()
        self.key_editor.close_editor()
        self.sleep_editor.close_editor()
        self.window_editor.close_editor()
        self.cmd_editor.open_for(step, ok_text)

    def show_window_editor(self, step, ok_text: str = "Add") -> None:
        self.mouse_editor.close_editor()
        self.key_editor.close_editor()
        self.sleep_editor.close_editor()
        self.cmd_editor.close_editor()
        self.window_editor.open_for(step, ok_text)

    def update_add_accents(self) -> None:
        self.btn_add_mouse.set_accent(self.mouse_editor.is_open())
        self.btn_add_key.set_accent(self.key_editor.is_open())
        self.btn_add_sleep.set_accent(self.sleep_editor.is_open())
        self.btn_add_cmd.set_accent(self.cmd_editor.is_open())
        self.btn_add_window.set_accent(self.window_editor.is_open())

    def fill_mouse_coords(self, x: int, y: int) -> None:
        self.mouse_editor.fill_coords(x, y)

    def refresh_rows(self, steps: list, sel: int = -1) -> None:
        self.table.setRowCount(len(steps))
        for i, s in enumerate(steps):
            vals = [str(i + 1), step_type_name(s), step_action_text(s), str(s.delay)]
            for c, vtxt in enumerate(vals):
                item = QTableWidgetItem(vtxt)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, c, item)
        if 0 <= sel < len(steps):
            self.table.selectRow(sel)
        else:
            self.table.clearSelection()

    def selected_row(self) -> int:
        i = self.table.currentRow()
        return i if 0 <= i < self.table.rowCount() else -1

    def set_running(self, running: bool) -> None:
        for slot in (
            self.btn_add_mouse,
            self.btn_add_key,
            self.btn_add_sleep,
            self.btn_add_cmd,
            self.btn_add_window,
        ):
            slot.set_slot_enabled(not running)
        for b in (
            self.btn_edit,
            self.btn_delete,
            self.btn_up,
            self.btn_down,
            self.btn_import,
            self.btn_export,
            self.btn_run,
            self.btn_settings,
            self.btn_help,
        ):
            b.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_pause.setEnabled(running)

    def set_pause_label(self, paused: bool) -> None:
        self.btn_pause.setText("Resume" if paused else "Pause")

    def set_status(self, text: str) -> None:
        self.console.append_line(text)
