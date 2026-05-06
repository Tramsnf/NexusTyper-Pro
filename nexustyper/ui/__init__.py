"""NexusTyper Pro — UI layer (dialogs, widgets, theming).

This package contains pure-view components extracted from the monolithic
``NexusTyper Pro.py`` script. Nothing here knows about the ``AutoTyperApp``
controller; cross-class wiring (signal/slot hookups between dialogs and the
main app) lives in the script. Each module is independently importable.

Public surface:
    nexustyper.ui.theming                — LIGHT_STYLESHEET, DARK_STYLESHEET,
                                           ensure_qss_assets()
    nexustyper.ui.widgets.splitter       — ChevronSplitterHandle, ToggleSplitter
                                           (alias: ChevronSplitter)
    nexustyper.ui.dialogs.about          — AboutDialog
    nexustyper.ui.dialogs.help           — HelpDialog
    nexustyper.ui.dialogs.settings       — SettingsDialog (hotkey/global-hotkey
                                           toggle preferences)
    nexustyper.ui.dialogs.hotkey_settings — re-exports SettingsDialog as
                                           HotkeySettingsDialog for callers
                                           that prefer the more specific name
    nexustyper.ui.dialogs.diagnostics    — DiagnosticsDialog
"""
