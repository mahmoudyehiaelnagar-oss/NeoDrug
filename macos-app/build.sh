#!/bin/bash
# Build NeoDrug.app (macOS) and a distributable NeoDrug.dmg.
# Usage: ./build.sh [output-dir]   (default: ../dist)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${1:-$ROOT/dist}"
APP_NAME="NeoDrug"
BUNDLE_ID="com.neodrug.app"
VERSION="3.0.0"

echo "▸ Compiling Swift shell…"
mkdir -p "$OUT"
APP="$OUT/$APP_NAME.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

swiftc -O "$HERE/main.swift" -o "$APP/Contents/MacOS/$APP_NAME" \
  -framework Cocoa -framework WebKit

echo "▸ Building icon…"
SRC_ICON="$ROOT/backend/public/icon-512.png"
if [ -f "$SRC_ICON" ]; then
  ICONSET="$OUT/AppIcon.iconset"
  rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$SRC_ICON" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    d=$((s*2))
    sips -z $d $d "$SRC_ICON" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
  rm -rf "$ICONSET"
fi

echo "▸ Writing Info.plist…"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>Neo Drug</string>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.medical</string>
  <key>NSSupportsAutomaticGraphicsSwitching</key><true/>
</dict>
</plist>
PLIST

echo "▸ Signing (ad-hoc)…"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "▸ Building DMG…"
DMG="$OUT/$APP_NAME-$VERSION-macOS.dmg"
rm -f "$DMG"
STAGE="$OUT/dmg-stage"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Neo Drug" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "✅ App:  $APP"
echo "✅ DMG:  $DMG"
