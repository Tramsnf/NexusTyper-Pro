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
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Pull APP_VERSION from the single-source-of-truth in the script itself.
def _read_app_version(default="0.0.0"):
    try:
        with open("NexusTyper Pro.py", "r", encoding="utf-8") as f:
            head = f.read(8000)
        m = re.search(r'APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', head)
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

# AppKit is bundled by pyobjc on macOS. We only add an extra binary on
# Darwin and only if the system framework is at the expected path.
binaries = []
if platform.system() == "Darwin":
    appkit = "/System/Library/Frameworks/AppKit.framework/AppKit"
    if os.path.exists(appkit):
        binaries.append((appkit, '.'))

a = Analysis(
    ['NexusTyper Pro.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'pyautogui', 'pynput', 'pyperclip',
        'PyQt5', 'PyQt5.sip', 'PyQt5.QtWidgets',
        'PyQt5.QtGui', 'PyQt5.QtCore', 'PyQt5.QtSvg',
    ] + collect_submodules('nexustyper'),
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
        'NSAppleEventsUsageDescription': 'This app needs to control your computer to automate typing.',
        'NSAccessibilityUsageDescription': 'This app needs to access Accessibility features to simulate keyboard input.',
        'LSUIElement': False,
        'NSHighResolutionCapable': True,
    },
)
