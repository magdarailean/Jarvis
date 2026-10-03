# Jarvis

A Windows desktop assistant and tutor for Romanian-speaking users, primarily in Moldova.

**Current state: Milestone 1, migrated to Python/PySide6.** The Romanian welcome window, `Gata` status, blue J tray icon, hide/reopen, single-instance activation and explicit exit work. AI, voice, screen capture, annotations, shortcuts and conversations are not implemented yet. Idle operation records nothing and makes no network requests.

## Prerequisites

- Windows 10/11 x64; tested on Windows 11 build 26200.
- Python **3.12 or newer, 64-bit** with pip/venv. Python 3.12 is the verified baseline. Use the Python launcher (`py`) or substitute your installed Python executable in the setup command.
- Internet access for initial dependency installation only. Runtime requires no account, API key, model or backend.

No .NET SDK/runtime, Visual Studio, separate Qt installation, database or administrator privileges are required. The old C# solution has been removed.

## Install

In PowerShell at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

This installs Jarvis in editable mode and the pinned `PySide6-Essentials==6.11.2` package (with matching `shiboken6`). No activation script or PowerShell execution-policy change is needed. Open this folder in your Python IDE and select `.venv\Scripts\python.exe` as its interpreter.

**On the current development machine, `.venv` is already created and installed.** You can run the commands below immediately, even though `py` is not on PATH. This environment was created using the available Python 3.12.14 runtime; teammates should create their own environment with their installed Python. Do not commit or copy `.venv` between computers.

## Run

With a console for development:

```powershell
.\.venv\Scripts\python.exe -m jarvis
```

Without a console:

```powershell
.\.venv\Scripts\jarvis.exe
```

You may also double-click `.venv\Scripts\jarvis.exe` in File Explorer. It is a Python GUI launcher, not a standalone installer. Choose **Ieșire** before changing or reinstalling the app.

## Manual behavior check

1. Launch Jarvis. Check the title **Jarvis — Asistent și tutore**, **Gata**, and the Romanian notices.
2. Find the blue **J** beside the clock (possibly under the hidden-icons arrow). Its tooltip is **Jarvis — Gata · Microfon oprit**.
3. Click **Ascunde** or the window **X**. The window disappears but the application stays running.
4. Double-click J, or right-click it and choose **Deschide Jarvis**. The same window returns.
5. Hide the window and run Jarvis again from another PowerShell window or File Explorer. The original window returns; the second process exits. Repeat with the window minimized.
6. Resize down to the minimum size. Text wraps and scrolls; **Ascunde** and **Ieșire** remain visible. Use Tab to focus the buttons and Enter or Space to activate them.
7. Choose **Ieșire** from the window or tray. The window/icon and Python process exit. Relaunch and exit again to verify restart.

If the tray is unavailable or initialization fails, hiding is disabled, a Romanian explanation appears, and X exits. The app does not register itself to start with Windows. Single-instance scope is the current Windows user and login session, including compatibility with an already-running previous C# build.

## Build and test

Python source needs no application compilation. Validate syntax, dependencies and lifecycle:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src/jarvis tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run tests on an unlocked Windows desktop. They briefly open real Qt windows/tray icons and test widget mouse/keyboard events, native tray action callbacks, duplicate child processes, shutdown/restart, simulated tray failure, abrupt child termination, logging failure and log size limits. Close an existing Jarvis first to include the installed-launcher test; other tests use unique instance names. Only test-created child processes are terminated. The suite uses standard-library `unittest` and QtTest, with no separate test framework.

Tests write app-only window renders to ignored `.artifacts/`. They do not capture the desktop. Physical taskbar tray clicks, Windows logoff and Explorer restart still require manual checks.

Build a distributable Python wheel (not a standalone Windows installer):

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
```

The wheel is `dist\jarvis_desktop-0.1.0-py3-none-any.whl`. It contains Python source and declares Qt dependencies; Windows is still required because single-instance integration uses Windows APIs. The build backend downloads setuptools into an isolated build environment when needed.

## Configuration and diagnostics

No application-specific environment variables or configuration are required. Windows' standard `LOCALAPPDATA` determines the diagnostic path:

```powershell
Get-Content "$env:LOCALAPPDATA\Jarvis\logs\application.log" -Tail 20
```

The same log location as before records startup, tray creation, hide/reopen, duplicate notification and shutdown. It resets near 1 MiB and contains no screenshots, audio, prompts, responses or credentials. Logging failures do not block operation. In Python, processes are named `python.exe`/`pythonw.exe` or the launcher; do not terminate unrelated Python processes when checking shutdown.

## Project structure

```text
src/jarvis/
  app.py                         # Composition and desktop lifetime
  presentation/main_window.py    # Romanian Qt widgets and UI signals
  infrastructure/
    single_instance.py          # Windows mutex/event boundary
    tray.py                     # Tray menu/icon adapter
    app_log.py                  # Bounded, best-effort logging
tests/                          # Real Windows/Qt integration + logging tests
pyproject.toml                  # Package, pinned dependency and GUI entry point
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries and [STATUS.md](STATUS.md) for verification and the roadmap. `.venv`, generated outputs and test renders are ignored. Deletions of C# source/build files in this migration are intentional; Python is now the only implementation.

Development stops after each milestone for manual review/commit. No automatic Git commits.
