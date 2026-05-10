<div align="center">

<img src="ico2.png" alt="NexusTyper Pro" width="180"/>

# NexusTyper Pro

**Type any text into any app, on any platform, with human-like pacing.**

A cross-platform desktop typing automation tool for the cases where copy-paste isn't an option — remote desktops, online IDEs that block paste, chat apps with no paste support, AI-generated text headed into a stubborn input field, and accessibility setups that need slow, deliberate keystrokes.

[![CI](https://github.com/Tramsnf/NexusTyper-Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/Tramsnf/NexusTyper-Pro/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Tramsnf/NexusTyper-Pro?label=latest)](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest)
[![License](https://img.shields.io/github/license/Tramsnf/NexusTyper-Pro)](LICENSE)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Built with PyQt5](https://img.shields.io/badge/built%20with-PyQt5-41cd52)

[**Download**](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest) ·
[**Install guide**](#install) ·
[**Features**](#features) ·
[**FAQ**](#faq)

</div>

---

## Why NexusTyper Pro exists

There's a surprising amount of text in modern computing that can't be pasted:

- **Online IDEs and coding sandboxes** (LeetCode, HackerRank, repl.it, CoderPad) sometimes intercept paste, mangle indentation, or trigger anti-paste warnings.
- **Remote desktop sessions** — Chrome Remote Desktop, AnyDesk, TeamViewer, Parsec, mstsc — don't propagate `Ctrl+V` from the host's clipboard to the remote app cleanly. (NexusTyper Pro v3.7.4+ ships a Windows scancode backend that fixes this.)
- **Chat apps and forms** that strip formatting, drop newlines, or cap input length on paste.
- **AI-generated text** — Claude, ChatGPT, Gemini, etc. — that you want to feed into something paste-hostile, with realistic pacing instead of an instant 4 KB drop.
- **Demo recording** — type out a code walkthrough at a steady, watchable speed without your hands on the keyboard.
- **Accessibility** — a slower, configurable typing rate for users who'd rather click "go" than type a long message themselves.

NexusTyper Pro is the keyboard you wish those apps had: programmable, paste-free, and configurable down to the millisecond.

## Install

Asset filenames are stable — the URLs below always resolve to the latest release.

| OS | Recommended (installer) | Portable |
|---|---|---|
| **macOS** | [`NexusTyper-Pro-macOS.dmg`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/NexusTyper-Pro-macOS.dmg) — open and drag to *Applications* | [`NexusTyper-Pro-macOS.zip`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/NexusTyper-Pro-macOS.zip) |
| **Windows** | [`NexusTyper-Pro-Windows-Setup.exe`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/NexusTyper-Pro-Windows-Setup.exe) — Inno Setup wizard | [`NexusTyper-Pro-Windows.zip`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/NexusTyper-Pro-Windows.zip) |
| **Linux** | [`nexustyper-pro_amd64.deb`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/nexustyper-pro_amd64.deb) — `sudo apt install ./nexustyper-pro_*.deb` | [`NexusTyper-Pro-Linux.tar.gz`](https://github.com/Tramsnf/NexusTyper-Pro/releases/latest/download/NexusTyper-Pro-Linux.tar.gz) |

The installers register the app with the OS (Launchpad / Start menu / app launcher) and skip the "unverified developer" prompt on subsequent launches.

### First-run permissions (macOS)

NexusTyper Pro needs **Accessibility** permission to inject keystrokes into other apps. The first launch prompts you; if you skip it the app shows a clear in-window banner:

> ⚠ macOS Accessibility permission not granted — typing will be blocked. Open Settings → Privacy & Security → Accessibility, enable NexusTyper Pro, then restart the app.

Grant it once and the app is ready. The Diagnostics dialog (Help → Diagnostics) shows the current permission state.

### First-run notes per platform

<details>
<summary><strong>macOS</strong></summary>

1. Double-click `NexusTyper-Pro-macOS.dmg`. macOS may prompt *"Apple could not verify…"* on the first install if the build is unsigned for your developer ID.
2. If blocked, open **System Settings → Privacy & Security**, scroll down, click **Open Anyway**, then re-mount the DMG.
3. Drag *NexusTyper Pro* onto the *Applications* alias inside the mounted volume.
4. Launch from Launchpad. Grant Accessibility when prompted.

If macOS calls a portable .zip "damaged", run `xattr -cr "NexusTyper Pro.app"` in the folder containing the .app to strip the download quarantine.
</details>

<details>
<summary><strong>Windows</strong></summary>

1. Double-click the Setup.exe. SmartScreen may show *"Windows protected your PC"* — click **More info → Run anyway**.
2. Choose per-user install if you don't want a UAC prompt.
3. Launch from the Start menu — no further warnings.

For the portable .zip with persistent **"We can't verify who created this file"** prompts, run `Get-ChildItem -Recurse | Unblock-File` in the extracted folder from PowerShell.
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
sudo apt install ./nexustyper-pro_*.deb
nexustyper-pro
```

The .deb installs to `/opt/nexustyper-pro/`, registers a launcher in your app menu, and pulls Qt/X11 runtime deps from your distro. Wayland sessions: synthetic input doesn't work under most Wayland compositors yet — switch to an X11 session if typing into other apps doesn't fire.
</details>

## Features

### Typing engine
- **Human-like pacing** — Min/Max WPM range, beta-distributed delays, optional fat-finger mistakes with backspace corrections, longer pauses after punctuation, occasional cognitive pauses at word boundaries.
- **Multiple newline modes** — Standard, Smart Newlines (joins soft-wrapped prose), List Mode (strips leading indent for code editors), Paste Mode (one paste per line for speed).
- **Personas** — quick presets for *Deliberate Writer*, *Fast Messenger*, *Careful Coder*, plus a fully custom mode.
- **Inline macros** — embed `{{PAUSE:1.5}}`, `{{PRESS:enter}}`, `{{CLICK:120,240}}`, `{{COMMENT:notes}}` in your text.

### Reach more apps
- **Remote Desktop typing** (macOS / Windows) — a scancode keyboard backend on Windows so keystrokes reach Chrome Remote Desktop, RDP (mstsc), AnyDesk, TeamViewer, Parsec, RustDesk, NoMachine, Splashtop, and ScreenConnect. Auto-detects remote-desktop windows; flip to *Always on* if needed (Settings → Remote Desktop typing).
- **IME-friendly mode** — paste-based output for CJK / Unicode input methods.
- **Unicode Hex Input** (macOS) — types arbitrary code-points via Option+Hex when the macOS input source is enabled.
- **Auto-optimize** — picks newline mode and editor settings based on the focused app (chat / code editor / browser).

### Stay in control
- **Tight focus lock** — pauses typing automatically when you switch apps *or* switch tabs in the same browser window. Resumes when you focus back.
- **Compliance mode** — auto-pauses inside a configurable blocklist of app titles.
- **Global hotkeys** — Start / Stop / Resume from anywhere, even when the app isn't focused.
- **Dry-run preview** — see exactly what would be typed without sending real keystrokes.
- **Comprehensive logging** — `~/.nexustyper_pro/logs/app.log` (rotated, 5 MB max). `sys.excepthook`, `threading.excepthook`, and Qt's own warnings all flow into the same file.

### Quality-of-life
- Light / dark themes with a polished masthead, persona pill, and clean sidebar.
- In-window update banner when a new release is available — no nagging modals on background checks.
- Smart-paste cleanup of invisible Unicode, smart quotes, em-dashes, and other AI-text artifacts before they reach your editor.
- Word / character / line counter that matches MS Word and Google Docs.
- Cross-platform: macOS, Windows, and Linux from one PyQt5 codebase.

## How typing works

Behind the scenes, NexusTyper Pro chooses the right output path for your text:

1. **Per-key typing** for short content: each character goes through the platform's keyboard injection API at a paced delay derived from your Min/Max WPM range, with optional fat-finger errors that backspace and correct themselves.
2. **Paste mode** for bulk content: writes to the OS clipboard and fires `Cmd+V` / `Ctrl+V` per line.
3. **Scancode mode** (Windows, RDP-aware): bypasses pyautogui's legacy `keybd_event` API and uses `SendInput` with `KEYEVENTF_SCANCODE` so events propagate through remote-desktop clients to the actual remote app.

The worker runs on its own QThread and can be paused, resumed, or stopped at any moment via global hotkeys or in-app buttons.

## Privacy & safety

- **No telemetry, no network calls** beyond the GitHub Releases poll for updates (once per day, polite User-Agent, no analytics).
- **Local-only logs** in `~/.nexustyper_pro/logs/`. Nothing is uploaded.
- **No clipboard scraping** — the app only writes to the clipboard during paste-mode typing and restores your previous clipboard contents afterwards.
- **Source-available** — read every line; build it yourself if you want.

## FAQ

<details>
<summary><strong>Why does my text show "typing in progress" but nothing appears in the target app?</strong></summary>

On **macOS**, this is almost always missing Accessibility permission for the installed app bundle. Open the Diagnostics dialog (Help → Diagnostics) and check the *macOS Accessibility trusted* line. If it's `False`, grant the permission in System Settings → Privacy & Security → Accessibility and **fully restart the app** (macOS caches the trust state per process).

On **Windows with Chrome Remote Desktop** or another remote-desktop client, make sure Settings → *Remote Desktop typing* is set to **Auto** or **Always on**.
</details>

<details>
<summary><strong>Does typing pause when I switch tabs / apps?</strong></summary>

Yes. The focus lock captures both the focused app's identity *and* (for browsers) the focused tab's title prefix. Switching apps or switching browser tabs trips the lock; the worker pauses and the status bar shows *"Lost focus on '…' (now: …) — paused"*. Refocus the original target and typing resumes after a 4-second grace period.
</details>

<details>
<summary><strong>What about online proctoring / academic-honesty enforcement?</strong></summary>

NexusTyper Pro is not designed to defeat any kind of monitoring or anti-cheat system, and we don't accept patches in that direction. If your use case is "type the answer key during an exam without getting caught", this is the wrong tool. Legitimate uses (RDP typing, demos, accessibility, AI-text→paste-hostile-app workflows) are what the project is for.
</details>

<details>
<summary><strong>Can I auto-update like Chrome?</strong></summary>

Today the app shows an in-window banner when a new release is available; click **Update** to download the new installer and run it. True silent auto-update (Sparkle on macOS, WinSparkle on Windows, with delta updates so you don't redownload the whole bundle) is on the roadmap but not shipped yet.
</details>

<details>
<summary><strong>Where is my config / log?</strong></summary>

- **Logs** — `~/.nexustyper_pro/logs/app.log` (open from Help → Diagnostics → *Open Logs Folder*)
- **Settings** — Qt's `QSettings` store; on macOS that's `~/Library/Preferences/com.tramsnf.NexusTyper Pro.plist`, on Windows the registry under `HKCU\Software\TramsNF\NexusTyper Pro`, on Linux `~/.config/TramsNF/NexusTyper Pro.conf`.
</details>

<details>
<summary><strong>How do I uninstall?</strong></summary>

- **macOS** — drag the app from Applications to the Trash; optionally remove `~/.nexustyper_pro/`.
- **Windows** — Settings → Apps → uninstall *NexusTyper Pro*.
- **Linux** — `sudo apt remove nexustyper-pro`.
</details>

## Build from source

```bash
git clone https://github.com/Tramsnf/NexusTyper-Pro
cd NexusTyper-Pro
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python "NexusTyper Pro.py"
```

To produce installers locally:

```bash
pip install pyinstaller
pyinstaller "NexusTyper Pro.spec"
# macOS:
./installers/macos/build-dmg.sh "dist/NexusTyper Pro.app" 0.0.0-dev "dist/NexusTyper-Pro-macOS.dmg"
```

CI (`.github/workflows/release.yml`) builds and publishes signed macOS .dmg, Windows Setup.exe, and Linux .deb on every `v*` tag push.

### Release signing & notarization

The release workflow signs and notarizes when the corresponding repo **secrets** are set, and silently falls back to unsigned builds when they're absent. To enable signing, add:

| Secret | Purpose |
|---|---|
| `APPLE_APPLICATION_CERT_BASE64` / `APPLE_CERT_PASSWORD` | Developer ID signing for the .app and .dmg |
| `APPLE_DEVELOPER_ID_APPLICATION` | Identity name for the codesign step |
| `NOTARIZE_APPLE_ID` / `NOTARIZE_APPLE_PASSWORD` / `NOTARIZE_TEAM_ID` | Apple notarization credentials |
| `WINDOWS_PFX_BASE64` / `WINDOWS_PFX_PASSWORD` | Windows code-signing certificate |

The in-app updater hits the GitHub Releases API once a day (the `UPDATE_FEED_URL` constant), surfaces the in-window banner, then streams the chosen installer (`.dmg` / `Setup.exe` / `.deb`) to your Downloads folder. Downloads support **HTTP Range resume** and **content-length cache hits**, so canceling and retrying picks up where it stopped instead of redownloading.

## Project layout

```
NexusTyper Pro.py            # Entry script — AutoTyperApp QMainWindow + glue
nexustyper/
├── constants.py             # APP_VERSION, hotkey defaults, branding
├── platform/                # OS-specific keyboard / accessibility / focus
│   ├── _macos.py            # AppKit + AX-based focus + accessibility probe
│   ├── _windows.py          # HWND-based focus identity
│   └── _linux.py            # X11 fallback via pyautogui
├── typing/                  # Typing engine
│   ├── worker.py            # TypingWorker (QObject) — the main thread
│   ├── keyboard.py          # Windows scancode backend + KeyboardShim
│   ├── sanitize.py          # Smart-paste cleanup (invisibles, quotes, …)
│   ├── macros.py            # {{PAUSE}} / {{PRESS}} / {{CLICK}}
│   ├── mistakes.py          # Keyboard-adjacency typo injection
│   ├── personas.py          # Deliberate Writer / Fast Messenger / Coder
│   ├── browser.py           # Active-window-aware optimizer
│   └── dry_run.py           # DryRunWorker (preview pane)
├── services/                # Background QObject workers
│   ├── update_checker.py    # GitHub Releases API polling
│   ├── installer_downloader.py  # Asset download + Range resume + cache
│   ├── logging_setup.py     # Rotating logger + global excepthooks
│   ├── hotkey_listener.py   # Global hotkey daemon
│   ├── hotkeys.py           # Qt → pynput hotkey translation
│   └── file_ingestion.py    # .docx / .pdf / .md text extraction
└── ui/                      # PyQt5 dialogs, widgets, theming
    ├── theming.py
    ├── dialogs/             # About / Settings / Diagnostics / Help / Dry-run
    └── widgets/             # Splitter, paste-cleaning text edit, code editor
installers/
├── macos/build-dmg.sh       # Notarized .dmg builder
├── windows/NexusTyper-Pro.iss   # Inno Setup script
└── linux/build-deb.sh       # .deb packager
.github/workflows/           # CI + multi-platform release automation
```

## Contributing

Issues and PRs welcome. The CI on every PR runs syntax + import checks against headless Qt; please make sure they pass before requesting review. Bug reports with `~/.nexustyper_pro/logs/app.log` attached are 10× easier to action.

For platform-specific bugs, mention which OS, which target app, and whether you reproduced via the installer or `python "NexusTyper Pro.py"`.

## License

[MIT](LICENSE) — do what you want, just don't blame us.

---

<div align="center">
<sub>Made for the spaces between paste and type.</sub>
</div>
