#!/bin/bash
# Build and run AiBeing as a proper .app bundle with icon
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJ_DIR/.build/debug"
APP_DIR="$BUILD_DIR/AiBeing.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES_DIR="$CONTENTS/Resources"

# Build
echo "🔨 Building..."
cd "$PROJ_DIR"
swift build 2>&1

# Kill existing instance
pkill -f "AiBeing.app/Contents/MacOS/AiBeing" 2>/dev/null || true
pkill -f ".build/debug/AiBeing" 2>/dev/null || true
sleep 0.5

# Create .app bundle structure
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

# Copy binary
cp "$BUILD_DIR/AiBeing" "$MACOS_DIR/AiBeing"

# Copy icon
if [ -f "$PROJ_DIR/Sources/Resources/AppIcon.icns" ]; then
    cp "$PROJ_DIR/Sources/Resources/AppIcon.icns" "$RESOURCES_DIR/AppIcon.icns"
fi

# Create Info.plist
cat > "$CONTENTS/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AiBeing</string>
    <key>CFBundleIdentifier</key>
    <string>com.aibeing.app</string>
    <key>CFBundleName</key>
    <string>AiBeing</string>
    <key>CFBundleDisplayName</key>
    <string>AiBeing</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Copy SPM resources bundle if exists
for bundle in "$BUILD_DIR"/*.bundle; do
    if [ -d "$bundle" ]; then
        cp -R "$bundle" "$RESOURCES_DIR/"
    fi
done

# Copy .app to project root for easy access
ROOT_DIR="$PROJ_DIR/../.."
rm -rf "$ROOT_DIR/AiBeing.app"
cp -R "$APP_DIR" "$ROOT_DIR/AiBeing.app"
echo "✅ AiBeing.app → $(cd "$ROOT_DIR" && pwd)/AiBeing.app"

echo "🚀 Launching AiBeing..."
open "$ROOT_DIR/AiBeing.app"
