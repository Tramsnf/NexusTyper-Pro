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

## Distribution & releases

End users grab the latest installable from the **Releases** page on GitHub:
<https://github.com/Tramsnf/NexusTyper-Pro/releases/latest>. Each release ships
three artifacts:

| Platform | File | How to run |
|---|---|---|
| macOS    | `NexusTyper-Pro-vX.Y-macOS.zip`   | See [macOS first-run notes](#macos-first-run-notes) below. |
| Windows  | `NexusTyper-Pro-vX.Y-Windows.zip` | Unzip → run `NexusTyper Pro.exe`. SmartScreen may warn the first time; click **More info** → **Run anyway**. |
| Linux    | `NexusTyper-Pro-vX.Y-Linux.tar.gz`| `tar -xzf NexusTyper-Pro-*-Linux.tar.gz && ./NexusTyper-Pro/NexusTyper-Pro` |

#### macOS first-run notes

The bundle is **ad-hoc signed but not notarized** — it has a valid signature
(so it launches on Apple Silicon), but Apple has no record of the developer,
so Gatekeeper will warn on first open. Pick the option that works for you:

1. **Easiest** — right-click (or Control-click) `NexusTyper Pro.app` →
   **Open** → confirm the warning dialog. macOS remembers the override and
   subsequent launches don't prompt.
2. **If macOS says "damaged" or won't open after #1** — open Terminal in the
   folder containing the .app and run:
   ```bash
   xattr -cr "NexusTyper Pro.app"
   ```
   That strips the `com.apple.quarantine` attribute Safari/Chrome attached
   when you downloaded the zip.
3. **System Settings path** — try to launch normally, get blocked, then go
   to **System Settings → Privacy & Security**, scroll to the message
   about NexusTyper Pro, and click **Open Anyway**.

After first launch, macOS will prompt you to grant **Accessibility** and
**Input Monitoring** in *System Settings → Privacy & Security*. Both are
required for the app to send keystrokes to other windows.

### How updates reach users

The app pings GitHub's Releases API at startup (and on demand from
**Help → Check for Updates…**). When a newer `tag_name` than `APP_VERSION`
appears, a non-blocking dialog shows the new version's notes with an
*Open download page* button. Background checks fire at most once a day; the
manual menu action bypasses the throttle. Configure or disable the checker
by changing `UPDATE_FEED_URL` near the top of
[`NexusTyper Pro.py`](NexusTyper%20Pro.py) (set to `""` to disable).

### Cutting a release

Bump `APP_VERSION` in `NexusTyper Pro.py`, commit, then push a matching
`v*` tag. The workflow builds macOS/Windows/Linux artifacts in parallel and
attaches them to a GitHub Release with auto-generated notes:

```bash
# Edit APP_VERSION = "3.4" in the source first, commit, then:
git tag v3.4
git push origin v3.4
```

You can also test the build pipeline without cutting a release — push the
**Run workflow** button on the **Release** action page (the workflow listens
for `workflow_dispatch`). Manual runs just publish artifacts on the run
page; no GitHub Release is created.

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
