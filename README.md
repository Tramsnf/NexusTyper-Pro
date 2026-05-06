# NexusTyper Pro

A desktop typing automation app that types text into any window with human-like
pacing, configurable mistakes, and macros. Built with PyQt5; runs on macOS,
Windows, and Linux.

![NexusTyper Pro](ico.png)

## Features

- **Human-like typing** — variable WPM with a Min/Max range, occasional
  adjacency-based mistakes with backspace corrections, natural pauses on
  punctuation.
- **Multiple newline modes** — Line Paste (fastest), Standard Typing, Smart
  Newlines (joins single breaks for prose), List Mode (strips indent for code
  editors).
- **Personas** — quick presets for Deliberate Writer, Fast Messenger, Careful
  Coder, or full manual control.
- **Macros** — embed `{{PAUSE:1.5}}`, `{{PRESS:enter}}`, `{{CLICK:x,y}}`, and
  `{{COMMENT:...}}` directly in your text.
- **Auto-optimize** for the active app (chat, code editor, browser) and
  **Compliance mode** that auto-pauses inside a configurable blocklist.
- **Global hotkeys** for Start / Stop / Resume.
- **Dry-run preview** simulates typing without sending real keystrokes.
- **Diagnostics & logging** at `~/.nexustyper_pro/logs/app.log`.

## Requirements

- Python 3.10+
- macOS, Windows, or Linux
- See [`requirements.txt`](requirements.txt) for Python deps.

### Platform-specific permissions

- **macOS** — System Settings → Privacy & Security → Accessibility (and
  Input Monitoring on macOS 14+) must allow the Python interpreter or the
  packaged `.app`. The app will trigger the prompt on first run.
- **Windows / Linux** — typically no extra setup; on Wayland, install the
  `xdotool` helper for full key-injection support.

## Install & run from source

```bash
git clone https://github.com/<your-fork>/NexusTyper-Pro.git
cd NexusTyper-Pro
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python "NexusTyper Pro.py"
```

## Building a standalone app

A PyInstaller spec is included for macOS bundling:

```bash
pip install pyinstaller
pyinstaller "NexusTyper Pro.spec"
# The .app bundle lands in dist/NexusTyper Pro.app
```

For Windows / Linux executables, run PyInstaller against the script directly:

```bash
pyinstaller --windowed --name "NexusTyper Pro" \
    --add-data "ico2.png:." --icon icon.icns "NexusTyper Pro.py"
```

## Releases

Tagged commits (`v3.x`) trigger
[`.github/workflows/release.yml`](.github/workflows/release.yml), which builds
the macOS bundle and attaches it to a GitHub Release. To cut a release:

```bash
git tag v3.4
git push origin v3.4
```

## Project structure

```
NexusTyper Pro.py        # Single-file PyQt5 app (entry point)
NexusTyper Pro.spec      # PyInstaller bundle config
icon.icns / ico*.png     # App icons
icon.iconset/            # Source PNGs for rebuilding icon.icns
requirements.txt         # Python dependencies
.github/workflows/       # CI / release automation
```

## License

See [`LICENSE`](LICENSE).
