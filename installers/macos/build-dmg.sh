#!/usr/bin/env bash
# Build a notarizable .dmg for NexusTyper Pro.
#
# Drag-to-install layout: the DMG's mount point contains the .app and a
# symlink to /Applications, so the user can drag the bundle straight in
# without opening a separate Finder window. Standard macOS distribution
# pattern; no licensing screen, no installer flow — just the drag.
#
# Signing is gated on env vars set by the workflow:
#   APPLE_DEVELOPER_ID_APPLICATION  — full identity name, e.g.
#                                     "Developer ID Application: Jane Doe (TEAMID)".
#                                     When set, the DMG itself is signed
#                                     with codesign (notarytool requires
#                                     a signed DMG).
#   NOTARIZE_APPLE_ID / NOTARIZE_APPLE_PASSWORD / NOTARIZE_TEAM_ID
#                                   — when all three are set together with
#                                     a signing identity, the DMG is
#                                     notarized and the ticket is stapled
#                                     so it installs offline without
#                                     Gatekeeper having to call home.
#
# Required positional args:
#   $1  path to NexusTyper Pro.app (already signed and notarized)
#   $2  display version (e.g. "3.7.5") — recorded in the volume name only
#   $3  output .dmg path
set -euo pipefail

APP_BUNDLE="${1:?missing .app path}"
VERSION="${2:?missing version}"
OUTPUT_DMG="${3:?missing output path}"

if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "error: $APP_BUNDLE is not a directory" >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# hdiutil wants a "source folder" whose contents become the DMG's root
# when mounted. We drop the .app and an /Applications symlink in there.
STAGING="$WORKDIR/stage"
mkdir -p "$STAGING"
cp -R "$APP_BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

VOL_NAME="NexusTyper Pro"

# UDZO = zlib-compressed read-only. Smallest output for distribution;
# user-installable verbatim.
hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    -fs HFS+ \
    "$OUTPUT_DMG"

# Sign the DMG with the Developer ID Application cert (same identity that
# signed the .app — notarytool rejects unsigned DMGs).
if [[ -n "${APPLE_DEVELOPER_ID_APPLICATION:-}" ]]; then
    echo "Signing .dmg with: $APPLE_DEVELOPER_ID_APPLICATION"
    codesign --force --sign "$APPLE_DEVELOPER_ID_APPLICATION" --timestamp "$OUTPUT_DMG"
else
    echo "APPLE_DEVELOPER_ID_APPLICATION not set — DMG will be unsigned"
fi

# Notarize the DMG and staple the ticket so Gatekeeper accepts the
# install offline. Without the staple, first-launch on a machine without
# internet pops the "cannot verify the developer" dialog.
if [[ -n "${NOTARIZE_APPLE_ID:-}" \
   && -n "${NOTARIZE_APPLE_PASSWORD:-}" \
   && -n "${NOTARIZE_TEAM_ID:-}" \
   && -n "${APPLE_DEVELOPER_ID_APPLICATION:-}" ]]; then
    echo "Submitting $OUTPUT_DMG to notarytool…"
    xcrun notarytool submit "$OUTPUT_DMG" \
        --apple-id "$NOTARIZE_APPLE_ID" \
        --password "$NOTARIZE_APPLE_PASSWORD" \
        --team-id  "$NOTARIZE_TEAM_ID" \
        --wait
    echo "Stapling notarization ticket…"
    xcrun stapler staple "$OUTPUT_DMG"
else
    echo "Notarization secrets not set — skipping notarization"
fi

echo "Built $OUTPUT_DMG"
