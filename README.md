# Click Studio

A Windows desktop app for recording and replaying mouse clicks, keyboard input, commands and window actions - built for automating repetitive stuff in games and apps.

![Click Studio screenshot](https://github.com/Lyeeroy/ClickStudio/blob/main/image.png?raw=true)

## TL;DR

Add a few steps (click here, press that, wait, run a command, focus a window), hit **Run**, and Click Studio replays them for you. Export your sequence as JSON or as a standalone `.py` script that runs without the app.

## Features

- **Mouse steps** - click (left/right/middle), double/triple click, hold time, screen coordinates; auto-add mode records every click you make outside the app window
- **Keyboard steps** - send keys or combos like `Ctrl+Alt+Del` or `Win+R`, repeat them N times with an interval; includes a key recorder (press REC, hold the combo, release - done)
- **Sleep steps** - pause between steps
- **Command steps** - run any shell command and wait for it to finish
- **Window steps** - focus, minimize, maximize, restore or close any window by (partial, case-insensitive) title, e.g. `Minecraft` matches `Minecraft (1.1.4)`
- **Sequence editor** - reorder steps with drag & drop or Up/Down, edit or delete any step
- **Playback** - run once or loop (configurable), pause/resume, ESC to stop
- **Export / Import** - JSON files, or self-contained Python scripts that replay the sequence with nothing but `pyautogui` installed
- **Console** - log panel at the bottom showing what the app is doing

## Hotkeys

| Action | Default | Changeable in Settings |
|---|---|---|
| Capture position | `F9` | yes (F2 / F4 / F8 / F9) |
| Play / pause | `F10` | yes (F10 / F11 / F12 / pause) |
| Stop playback | `ESC` | no |

## Installation

> Windows only. Python 3.10+ must be installed.

**Run from source:**

```bat
pip install -r requirements.txt
python ClickStudio.py
```

**Run the prebuilt EXE:**

Just start `ClickStudio.exe` - no Python or installation needed.

## Building the EXE yourself

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name ClickStudio ClickStudio.py
```

The result lands in `dist/ClickStudio.exe`.

## Notes

- Settings are saved to `clickstudio_settings.ini` next to the app; errors go to `clickstudio_error.log`.
- PyAutoGUI's failsafe is active: slam the mouse into a screen corner to abort playback.
