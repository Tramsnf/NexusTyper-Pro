#!/usr/bin/env bash
# Build a flat macOS installer .pkg for NexusTyper Pro.
#
# Drops the .app into /Applications via the system installer. The system
# installer extracts files as root without inheriting the user's quarantine
# xattr, so the installed .app launches without the Gatekeeper "Apple could
# not verify…" dialog — even when the .pkg itself is unsigned. (The .pkg
# still needs the System Settings → Privacy & Security → Open Anyway dance
# on Sequoia for the *first* run; that's the unsigned-installer floor.)
#
# Signing is gated on env vars set by the workflow:
#   APPLE_DEVELOPER_ID_INSTALLER  — full identity name, e.g. "Developer ID
#                                   Installer: Jane Doe (TEAMID)". When set,
#                                   the productbuild step signs with it.
#   NOTARIZE_APPLE_ID             — Apple ID for notarytool. When set together
#   NOTARIZE_APPLE_PASSWORD         with the others, the script submits the
#   NOTARIZE_TEAM_ID                signed .pkg for notarization and staples
#                                   the ticket on success.
#
# Required positional args:
#   $1  path to NexusTyper Pro.app
#   $2  display version (e.g. "3.4")
#   $3  output .pkg path
set -euo pipefail

APP_BUNDLE="${1:?missing .app path}"
VERSION="${2:?missing version}"
OUTPUT_PKG="${3:?missing output path}"

if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "error: $APP_BUNDLE is not a directory" >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# pkgbuild wants a "root" directory that mirrors the install layout. Place
# the .app under <root>/Applications so --install-location / drops it in
# /Applications on the target machine.
PAYLOAD="$WORKDIR/payload"
mkdir -p "$PAYLOAD/Applications"
cp -R "$APP_BUNDLE" "$PAYLOAD/Applications/"

COMPONENT_PKG="$WORKDIR/component.pkg"
pkgbuild \
    --root "$PAYLOAD" \
    --identifier "com.nexustyper.pro" \
    --version "$VERSION" \
    --install-location "/" \
    "$COMPONENT_PKG"

PRODUCTBUILD_ARGS=(
    --package "$COMPONENT_PKG"
    --version "$VERSION"
)

if [[ -n "${APPLE_DEVELOPER_ID_INSTALLER:-}" ]]; then
    echo "Signing .pkg with: $APPLE_DEVELOPER_ID_INSTALLER"
    PRODUCTBUILD_ARGS+=(--sign "$APPLE_DEVELOPER_ID_INSTALLER")
else
    echo "APPLE_DEVELOPER_ID_INSTALLER not set — building unsigned .pkg"
fi

productbuild "${PRODUCTBUILD_ARGS[@]}" "$OUTPUT_PKG"

if [[ -n "${NOTARIZE_APPLE_ID:-}" \
   && -n "${NOTARIZE_APPLE_PASSWORD:-}" \
   && -n "${NOTARIZE_TEAM_ID:-}" \
   && -n "${APPLE_DEVELOPER_ID_INSTALLER:-}" ]]; then
    echo "Submitting $OUTPUT_PKG to notarytool…"
    xcrun notarytool submit "$OUTPUT_PKG" \
        --apple-id "$NOTARIZE_APPLE_ID" \
        --password "$NOTARIZE_APPLE_PASSWORD" \
        --team-id  "$NOTARIZE_TEAM_ID" \
        --wait
    echo "Stapling notarization ticket…"
    xcrun stapler staple "$OUTPUT_PKG"
else
    echo "Notarization secrets not set — skipping notarization"
fi

echo "Built: $OUTPUT_PKG"
