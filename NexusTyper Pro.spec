# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Add all data files (icons) to be bundled
datas = [
    ('icon.icns', '.'),
    ('ico2.png', '.')
]

# Add potential binary dependencies for pyautogui and pynput
binaries = [
    ('/System/Library/Frameworks/AppKit.framework/AppKit', '.')
]

a = Analysis(['NexusTyper Pro.py'],
             pathex=['.'],
             binaries=binaries,
             datas=datas,
             hiddenimports=['pyautogui', 'pynput', 'pyperclip', 'AppKit', 'sip', 'PyQt5.sip', 'PyQt5.Qt', 'PyQt5.QtWidgets', 'PyQt5.QtGui', 'PyQt5.QtCore'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='NexusTyper Pro',
          debug=True,  # Enable debug mode for more output
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)  # Ensure console output for debugging

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='NexusTyper Pro')

app = BUNDLE(coll,
             name='NexusTyper Pro.app',
             icon='icon.icns',
             bundle_identifier='com.tramsnf.nexustyperpro',
             info_plist={
                 'LSMinimumSystemVersion': '10.13',
                 'NSHumanReadableCopyright': 'Copyright © 2025 TramsNF',
                 'CFBundleShortVersionString': '3.2',
                 'CFBundleVersion': '3.2',
                 'CFBundleExecutable': 'NexusTyper Pro',
                 'CFBundleName': 'NexusTyper Pro',
                 'NSAppleEventsUsageDescription': 'This app needs to control your computer to automate typing.',
                 'NSAccessibilityUsageDescription': 'This app needs to access Accessibility features to simulate keyboard input.',
                 'LSUIElement': False 
             })