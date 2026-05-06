"""Single source of truth for app-level constants.

Imported by both `NexusTyper Pro.py` and the `nexustyper.*` subpackages so
versioning, branding, and update-feed URLs only have to change in one place.
"""

import platform

APP_NAME = "NexusTyper Pro"
APP_VERSION = "3.7.2"
APP_AUTHOR = "TramsNF"
APP_COPYRIGHT_YEAR = "2025"
APP_SIGNATURE = "Automate. Create. Elevate."
CONTACT_EMAIL = "xx"
CONTACT_WEBSITE = "https://tramsnf.com"

# GitHub release feed for the in-app update checker. Forks should change
# this to point at their own repo or set it to "" to disable the checker.
UPDATE_FEED_URL = "https://api.github.com/repos/Tramsnf/NexusTyper-Pro/releases/latest"
UPDATE_DOWNLOAD_PAGE = "https://github.com/Tramsnf/NexusTyper-Pro/releases/latest"

DEFAULT_MIN_WPM, DEFAULT_MAX_WPM = 80, 120
MIN_WPM_LIMIT, MAX_WPM_LIMIT = 10, 800
DEFAULT_LAPS, DEFAULT_DELAY = 1, 3
MISTAKE_CHANCE = 0.02

MACOS_ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)

if platform.system() == "Darwin":
    DEFAULT_START_HOTKEY = "Cmd+Alt+S"
    DEFAULT_STOP_HOTKEY = "Cmd+Alt+X"
    DEFAULT_RESUME_HOTKEY = "Cmd+Alt+R"
else:
    DEFAULT_START_HOTKEY = "Ctrl+Alt+S"
    DEFAULT_STOP_HOTKEY = "Ctrl+Alt+X"
    DEFAULT_RESUME_HOTKEY = "Ctrl+Alt+R"
