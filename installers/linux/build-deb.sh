#!/usr/bin/env bash
# Build a Debian package (.deb) for NexusTyper Pro from a PyInstaller bundle.
#
# Layout produced on the target system:
#   /opt/nexustyper-pro/                  — full PyInstaller dist folder
#   /usr/bin/nexustyper-pro               — symlink to the launcher
#   /usr/share/applications/…desktop      — menu integration
#   /usr/share/icons/hicolor/256x256/…    — icon for the launcher
#
# Required positional args:
#   $1  PyInstaller dist folder    (e.g. dist/NexusTyper-Pro)
#   $2  display version            (e.g. "3.4")
#   $3  icon source PNG            (e.g. icon.iconset/icon_256x256.png)
#   $4  output .deb path
set -euo pipefail

DIST_DIR="${1:?missing dist dir}"
VERSION="${2:?missing version}"
ICON_SRC="${3:?missing icon path}"
OUTPUT_DEB="${4:?missing output path}"

if [[ ! -d "$DIST_DIR" ]]; then
    echo "error: $DIST_DIR is not a directory" >&2
    exit 1
fi
if [[ ! -f "$ICON_SRC" ]]; then
    echo "error: $ICON_SRC not found" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

ROOT="$WORKDIR/debroot"
mkdir -p \
    "$ROOT/DEBIAN" \
    "$ROOT/opt/nexustyper-pro" \
    "$ROOT/usr/bin" \
    "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/icons/hicolor/256x256/apps"

# App payload
cp -R "$DIST_DIR"/. "$ROOT/opt/nexustyper-pro/"
chmod -R go-w "$ROOT/opt/nexustyper-pro"

# Launcher symlink
ln -s "/opt/nexustyper-pro/NexusTyper-Pro" "$ROOT/usr/bin/nexustyper-pro"

# Desktop entry + icon
cp "$SCRIPT_DIR/nexustyper-pro.desktop" "$ROOT/usr/share/applications/"
cp "$ICON_SRC" "$ROOT/usr/share/icons/hicolor/256x256/apps/nexustyper-pro.png"

# control file with version substitution
sed "s|@VERSION@|$VERSION|" "$SCRIPT_DIR/control.template" > "$ROOT/DEBIAN/control"

# dpkg-deb requires DEBIAN dir mode 0755
chmod 0755 "$ROOT/DEBIAN"

# --root-owner-group makes the produced .deb claim root:root for every file,
# which is what users expect when installing as root via dpkg/apt and avoids
# leaking the runner's UID/GID into the archive.
dpkg-deb --build --root-owner-group "$ROOT" "$OUTPUT_DEB"
echo "Built: $OUTPUT_DEB"
