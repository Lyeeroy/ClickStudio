import copy
import json
import sys
import threading
import traceback

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from qfluentwidgets import Action, Dialog, FluentIcon as FIF, FluentWindow, InfoBar, RoundMenu

from .help import HelpBox, help_text
from .hotkeys import Hotkeys
from .models import CmdStep, KeyStep, MouseStep, SleepStep, WindowStep, step_from_dict, step_to_dict
from .playback import Player
from .scriptgen import build_sequence_script, steps_payload_from_script
from .settings import CFG_FILE, AppSettings, ERROR_LOG, load_settings, save_settings
from .ui_home import HomeInterface
from .ui_settings import SettingsInterface
from qfluentwidgets import Dialog, FluentIcon as FIF, FluentWindow, InfoBar


def install_excepthook() -> None:
    def _write(t, v, tb):
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write("".join(traceback.format_exception(t, v, tb)))
                f.write("\n")
        except OSError:
            pass

    def hook(t, v, tb):
        _write(t, v, tb)
        try:
            QMessageBox.critical(
                None,
                "Click Studio - Error",
                "An error occurred (details in clickstudio_error.log):\n\n"
                + "".join(traceback.format_exception_only(t, v)),
            )
        except Exception:
            pass
        sys.__excepthook__(t, v, tb)

    def thread_hook(args):
        _write(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = hook
    threading.excepthook = thread_hook


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Click Studio")
        self.settings = load_settings()
        self.steps = []
        self.player = None
        self.hotkeys = Hotkeys(self)
        self._editor_mode = None

        self.home = HomeInterface(self.settings.cap_hk, self)
        self.home.setObjectName("home-interface")
        self.settings_page = SettingsInterface(self.settings, self)
        self._wire_home()
        self.addSubInterface(self.home, FIF.HOME, "Home")
        self.addSubInterface(self.settings_page, FIF.SETTING, "Settings")

        self.hotkeys.capture_pressed.connect(self._hk_capture)
        self.hotkeys.play_pressed.connect(self._hk_play)
        self.hotkeys.stop_pressed.connect(self._hk_stop)
        self.hotkeys.register(self.settings.cap_hk, self.settings.play_hk)

        self.home.set_running(False)
        self.home.refresh_rows(self.steps)
        self.home.set_status(f"Idle - add steps, then Run ({self.settings.play_hk})")

    def _wire_home(self) -> None:
        h = self.home
        h.add_mouse_clicked.connect(self.on_add_mouse)
        h.add_key_clicked.connect(self.on_add_key)
        h.add_sleep_clicked.connect(self.on_add_sleep)
        h.add_cmd_clicked.connect(self.on_add_cmd)
        h.add_window_clicked.connect(self.on_add_window)
        h.edit_clicked.connect(self.edit_selected)
        h.delete_clicked.connect(self.delete_selected)
        h.duplicate_clicked.connect(self.on_duplicate_clicked)
        h.up_clicked.connect(lambda: self.move_selected(-1))
        h.down_clicked.connect(lambda: self.move_selected(1))
        h.run_clicked.connect(self.start_run)
        h.pause_clicked.connect(self.toggle_pause)
        h.stop_clicked.connect(self.stop_playback)
        h.import_clicked.connect(self.import_steps)
        h.export_clicked.connect(self.export_menu)
        h.settings_clicked.connect(lambda: self.switchTo(self.settings_page))
        h.help_clicked.connect(self.show_help)
        h.editor_finished.connect(self._on_editor_finished)
        h.mouse_auto_added.connect(self._on_auto_added)
        h.row_dropped.connect(self.move_row)
        self.settings_page.saved.connect(self.save_settings)

    def _busy(self) -> bool:
        return (
            self.player is not None
            or self.home.editor_open()
            or QApplication.activeModalWidget() is not None
        )

    def on_add_mouse(self) -> None:
        if self.player is not None:
            return
        if self.home.mouse_editor.is_open():
            self.home.close_editors()
        else:
            pos_x, pos_y = _cursor_pos()
            self._editor_mode = ("add", None)
            self.home.show_mouse_editor(MouseStep(x=pos_x, y=pos_y))
        self.home.update_add_accents()

    def on_add_key(self) -> None:
        if self.player is not None:
            return
        if self.home.key_editor.is_open():
            self.home.close_editors()
        else:
            self._editor_mode = ("add", None)
            self.home.show_key_editor(KeyStep())
        self.home.update_add_accents()

    def on_add_sleep(self) -> None:
        if self.player is not None:
            return
        if self.home.sleep_editor.is_open():
            self.home.close_editors()
        else:
            self._editor_mode = ("add", None)
            self.home.show_sleep_editor(SleepStep())
        self.home.update_add_accents()

    def on_add_cmd(self) -> None:
        if self.player is not None:
            return
        if self.home.cmd_editor.is_open():
            self.home.close_editors()
        else:
            self._editor_mode = ("add", None)
            self.home.show_cmd_editor(CmdStep())
        self.home.update_add_accents()

    def on_add_window(self) -> None:
        if self.player is not None:
            return
        if self.home.window_editor.is_open():
            self.home.close_editors()
        else:
            self._editor_mode = ("add", None)
            self.home.show_window_editor(WindowStep())
        self.home.update_add_accents()

    def _hk_capture(self) -> None:
        if self.player is not None or QApplication.activeModalWidget() is not None:
            return
        x, y = _cursor_pos()
        if self.home.mouse_editor.is_open():
            self.home.fill_mouse_coords(x, y)
            return
        if self.home.key_editor.is_open():
            return
        self._editor_mode = ("add", None)
        self.home.show_mouse_editor(MouseStep(x=x, y=y))
        self.home.update_add_accents()
        self.switchTo(self.home)

    def _hk_play(self) -> None:
        if QApplication.activeModalWidget() is not None or self.home.editor_open():
            return
        if self.player is None:
            self.start_run()
        else:
            self.toggle_pause()

    def _hk_stop(self) -> None:
        if QApplication.activeModalWidget() is not None or self.home.editor_open():
            return
        if self.player is not None:
            self.stop_playback()

    def edit_selected(self) -> None:
        i = self.home.selected_row()
        if i < 0 or i >= len(self.steps):
            return
        s = self.steps[i]
        if isinstance(s, MouseStep):
            self._editor_mode = ("edit", i)
            self.home.show_mouse_editor(s, "Save")
        elif isinstance(s, KeyStep):
            self._editor_mode = ("edit", i)
            self.home.show_key_editor(s, "Save")
        elif isinstance(s, CmdStep):
            self._editor_mode = ("edit", i)
            self.home.show_cmd_editor(s, "Save")
        elif isinstance(s, WindowStep):
            self._editor_mode = ("edit", i)
            self.home.show_window_editor(s, "Save")
        else:
            self._editor_mode = ("edit", i)
            self.home.show_sleep_editor(s, "Save")
        self.home.update_add_accents()

    def _on_auto_added(self, step) -> None:
        self.steps.append(step)
        self.home.refresh_rows(self.steps, len(self.steps) - 1)
        self.home.set_status(f"Auto-added step {len(self.steps)} @ ({step.x},{step.y})")

    def _on_editor_finished(self, committed: bool) -> None:
        mode = self._editor_mode
        self._editor_mode = None
        if committed and mode is not None:
            kind, idx = mode
            if kind == "add":
                step = (
                    self.home.mouse_editor.step
                    or self.home.key_editor.step
                    or self.home.sleep_editor.step
                    or self.home.cmd_editor.step
                    or self.home.window_editor.step
                )
                if step is not None:
                    self.steps.append(step)
                    self.home.refresh_rows(self.steps, len(self.steps) - 1)
            else:
                self.home.refresh_rows(self.steps, idx)
        self.home.close_editors()
        self.home.update_add_accents()

    def delete_selected(self) -> None:
        i = self.home.selected_row()
        if i < 0 or i >= len(self.steps):
            return
        del self.steps[i]
        self.home.refresh_rows(self.steps, min(i, len(self.steps) - 1))

    def on_duplicate_clicked(self) -> None:
        i = self.home.selected_row()
        if i < 0 or i >= len(self.steps):
            return
        self.steps.insert(i + 1, copy.deepcopy(self.steps[i]))
        self.home.refresh_rows(self.steps, i + 1)

    def move_selected(self, direction: int) -> None:
        i = self.selected_row()
        t = i + direction
        if i < 0 or not (0 <= t < len(self.steps)):
            return
        self.steps[i], self.steps[t] = self.steps[t], self.steps[i]
        self.home.refresh_rows(self.steps, t)

    def move_row(self, src: int, dst: int) -> None:
        if self.player is not None:
            return
        if not (0 <= src < len(self.steps)) or not (0 <= dst < len(self.steps)):
            return
        step = self.steps.pop(src)
        self.steps.insert(dst, step)
        self.home.refresh_rows(self.steps, dst)

    def start_run(self) -> None:
        if self.player is not None:
            return
        self.home.close_editors()
        if not self.steps:
            InfoBar.warning(
                title="Click Studio",
                content="No steps to run. Add some first.",
                parent=self,
                duration=2500,
            )
            return
        self.player = Player(list(self.steps), self.settings.loop_inf, self.settings.loop_count, self)
        self.player.progress.connect(self.home.set_status)
        self.player.finished_run.connect(self._on_player_finished)
        self.player.start()
        self.home.set_running(True)
        self.home.set_status("Running...")
        self.switchTo(self.home)

    def toggle_pause(self) -> None:
        if self.player is None:
            return
        paused = self.player.toggle_pause()
        self.home.set_pause_label(paused)
        self.home.set_status("Paused" if paused else "Running...")

    def stop_playback(self) -> None:
        if self.player is not None:
            self.player.request_stop()

    def _on_player_finished(self, msg: str) -> None:
        if self.player is not None:
            self.player.wait()
            self.player = None
        self.home.set_pause_label(False)
        self.home.set_running(False)
        self.home.set_status(msg if msg != "Stopped" else f"Stopped - {len(self.steps)} step(s)")

    def save_settings(self, s: AppSettings) -> None:
        self.settings = s
        save_settings(s)
        self.hotkeys.register(s.cap_hk, s.play_hk)
        self.home.set_status(f"Settings saved - capture {s.cap_hk}, play {s.play_hk}, stop ESC")
        InfoBar.success(title="Click Studio", content="Settings saved.", parent=self.settings_page, duration=2000)

    def export_menu(self) -> None:
        if not self.steps:
            InfoBar.warning(title="Click Studio", content="Nothing to export.", parent=self, duration=2000)
            return
        menu = RoundMenu(parent=self)
        act_json = Action(FIF.DOCUMENT, "JSON file", self)
        act_json.triggered.connect(self.export_json)
        act_py = Action(FIF.CODE, "Python script", self)
        act_py.triggered.connect(self.export_py)
        menu.addAction(act_json)
        menu.addAction(act_py)
        menu.exec(QCursor.pos())

    def _save_steps_dialog(self, title: str, default, flt: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, title, default, flt)
        return path

    def export_json(self) -> None:
        default = str(CFG_FILE.with_name("steps.json"))
        path = self._save_steps_dialog("Export steps", default, "JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        payload = {"version": 1, "steps": [step_to_dict(s) for s in self.steps]}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            InfoBar.error(title="Click Studio", content="Cannot write file.", parent=self, duration=2500)
            return
        self.home.set_status(f"Exported {len(self.steps)} step(s) -> {path}")

    def export_py(self) -> None:
        default = str(CFG_FILE.with_name("sequence.py"))
        path = self._save_steps_dialog("Export steps", default, "Python (*.py)")
        if not path:
            return
        if not path.lower().endswith(".py"):
            path += ".py"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_sequence_script(self.steps))
        except OSError:
            InfoBar.error(title="Click Studio", content="Cannot write file.", parent=self, duration=2500)
            return
        self.home.set_status(f"Exported {len(self.steps)} step(s) -> {path}")

    def import_steps(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import steps", str(CFG_FILE.parent), "Sequence files (*.json *.py)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            InfoBar.error(title="Click Studio", content="Empty or unreadable file.", parent=self, duration=2500)
            return
        try:
            if path.lower().endswith(".py"):
                items = steps_payload_from_script(raw)
            else:
                items = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            InfoBar.error(title="Click Studio", content="No steps found in file.", parent=self, duration=2500)
            return
        items = items.get("steps") if isinstance(items, dict) else items
        if not isinstance(items, list):
            InfoBar.error(title="Click Studio", content="No steps found in file.", parent=self, duration=2500)
            return
        if self.steps:
            d = Dialog("Replace steps?", f"Replace current {len(self.steps)} step(s)?", self)
            if not d.exec():
                return
        parsed = []
        skipped = 0
        for obj in items:
            s = step_from_dict(obj) if isinstance(obj, dict) else None
            if s is None:
                skipped += 1
            else:
                parsed.append(s)
        self.steps = parsed
        self.home.refresh_rows(self.steps, 0 if parsed else -1)
        msg = f"Imported {len(parsed)} step(s)"
        if skipped:
            msg += f", skipped {skipped} invalid"
        InfoBar.success(title="Click Studio", content=msg, parent=self, duration=3000)
        self.home.set_status(msg)

    def show_help(self) -> None:
        HelpBox(self, help_text(self.settings.cap_hk, self.settings.play_hk)).exec()

    def closeEvent(self, event) -> None:
        self.home.close_editors()
        if self.player is not None:
            self.player.request_stop()
            self.player.wait(2000)
        self.hotkeys.unregister()
        super().closeEvent(event)


def _cursor_pos():
    import pyautogui

    p = pyautogui.position()
    return int(p.x), int(p.y)


def main() -> None:
    import faulthandler

    install_excepthook()
    try:
        _fh_log = open(ERROR_LOG.with_name("clickstudio_fault.log"), "w", encoding="utf-8")
        faulthandler.enable(_fh_log, all_threads=True)
    except OSError:
        pass
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(980, 640)
    w.show()
    sys.exit(app.exec())
