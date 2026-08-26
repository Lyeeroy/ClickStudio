from PyQt6.QtWidgets import QTextEdit
from qfluentwidgets import MessageBoxBase


def help_text(cap_hk: str, play_hk: str) -> str:
    return (
        "CLICK STUDIO - UI automation sequencer\n\n"
        "ADD STEPS:\n"
        f"- Add Mouse opens a REC window: move the cursor, left-click anywhere to grab the position.\n"
        "- Manual entry expands precise fields inside the same window.\n"
        f"- Or press {cap_hk} anywhere for quick capture.\n"
        "- Each step has an optional delay-before.\n"
        "- Select a row then Edit/Delete/Up/Down (double-click edits).\n\n"
        "RUN:\n"
        f"- Run button or {play_hk} hotkey starts. Same hotkey pauses/resumes.\n"
        "- ESC stops instantly. Loops configured in Settings.\n\n"
        "KEY NAMES (Keyboard step):\n"
        "- Letters: a b c   Digits: 1 2 3\n"
        "- Special: {{ENTER}} {{TAB}} {{SPACE}} {{ESC}} {{F1}}-{{F12}} {{DEL}}\n"
        "- Combos: ^c = Ctrl+C, !f = Alt+F, +s = Shift+S, #{{TAB}} = Win+Tab\n\n"
        "FILES:\n"
        "- Export/Import saves steps as JSON (same format as the AutoIt version).\n"
        "- Settings live in clickstudio_settings.ini next to the app.\n"
        "- Errors are logged to clickstudio_error.log.\n\n"
        "NOTE: if clicks do nothing, the target app may run as admin - run this app as admin too."
    )


class HelpBox(MessageBoxBase):
    def __init__(self, parent, text: str):
        super().__init__(parent)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setPlainText(text)
        self.view.setMinimumSize(520, 400)
        self.viewLayout.addWidget(self.view)
        self.yesButton.setText("OK")
        self.cancelButton.hide()
        self.widget.setMinimumWidth(560)
