# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for NexusTyper Pro.

Production-shaped: no debug bootloader, no Terminal window, version
pulled live from the source so we don't drift between the About dialog
and the .app's Info.plist. Linux/Windows builds in CI use plain
PyInstaller flags; this spec is the macOS canonical.
"""

import os
import platform
import re
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Pull APP_VERSION from the single source of truth (nexustyper.constants).
# Reading the constant directly with a regex avoids importing the package
# at spec-eval time (which would drag in PyQt5 / pyautogui on the build
# host). A CI env-var override lets the release workflow inject the tag
# version so the bundle's Info.plist matches the GitHub release tag even
# if a maintainer forgets to bump constants.py.
def _read_app_version(default="0.0.0"):
    env_override = os.environ.get("NEXUSTYPER_VERSION_OVERRIDE", "").strip()
    if env_override:
        return env_override
    try:
        with open("nexustyper/constants.py", "r", encoding="utf-8") as f:
            src = f.read()
        m = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', src, re.M)
        return m.group(1) if m else default
    except Exception:
        return default

APP_VERSION = _read_app_version()

datas = [
    ('icon.icns', '.'),
    ('ico.png', '.'),
    ('ico2.png', '.'),
]
datas += collect_data_files('certifi')

# pyobjc framework bridges. The macOS platform layer's AX permission
# probe (Quartz.AXIsProcessTrusted), the Unicode-Hex typing path
# (AppKit), and the focused-window-title read (ApplicationServices)
# all import these at call time. Without explicit bundling PyInstaller
# misses some of the bridge submodules, the imports raise inside the
# packaged .app, the AX probe falls through to its "fail open" branch,
# and the worker happily starts typing while the OS silently drops
# every keystroke.
binaries = []
hidden_objc = []
if platform.system() == "Darwin":
    appkit_dylib = "/System/Library/Frameworks/AppKit.framework/AppKit"
    if os.path.exists(appkit_dylib):
        binaries.append((appkit_dylib, '.'))
    for _mod in ("AppKit", "Quartz", "ApplicationServices", "objc"):
        try:
            _datas, _binaries, _hidden = collect_all(_mod)
            datas += _datas
            binaries += _binaries
            hidden_objc += _hidden
        except Exception:
            # collect_all raises if the module isn't installed on the
            # build host. That's fine for non-macOS hosts; the import-
            # closure on macOS will pick the right ones up there.
            pass

a = Analysis(
    ['NexusTyper Pro.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'pyautogui', 'pynput', 'pyperclip',
        'PyQt5', 'PyQt5.sip', 'PyQt5.QtWidgets',
        'PyQt5.QtGui', 'PyQt5.QtCore', 'PyQt5.QtSvg',
    ] + collect_submodules('nexustyper') + hidden_objc,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NexusTyper Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app — no Terminal window for end users.
    icon='icon.icns' if os.path.exists('icon.icns') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NexusTyper Pro',
)

app = BUNDLE(
    coll,
    name='NexusTyper Pro.app',
    icon='icon.icns',
    bundle_identifier='com.tramsnf.nexustyperpro',
    info_plist={
        'LSMinimumSystemVersion': '10.13',
        'NSHumanReadableCopyright': f'Copyright © 2025 TramsNF',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'CFBundleExecutable': 'NexusTyper Pro',
        'CFBundleName': 'NexusTyper Pro',
        'NSAppleEventsUsageDescription': 'NexusTyper Pro needs to send Apple events to drive other apps for automated typing.',
        'NSAccessibilityUsageDescription': 'NexusTyper Pro needs Accessibility access to simulate keyboard input into other apps.',
        # Required by macOS Sequoia (15.x) before IOHIDRequestAccess will
        # register the app in System Settings → Privacy & Security →
        # Input Monitoring. Without this key, the app never appears in
        # the list and the user has no toggle to grant.
        'NSInputMonitoringUsageDescription': 'NexusTyper Pro needs to listen for keyboard events to support global hotkeys (Start / Stop / Resume).',
        'LSUIElement': False,
        'NSHighResolutionCapable': True,
    },
)
