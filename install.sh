#!/usr/bin/env bash
# ==============================================================================
# Neo Drug — Linux Installer Script
# سكريبت تثبيت تطبيق Neo Drug على نظام لينكس
# ==============================================================================

set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# التحقق هل المستخدم لديه صلاحيات root
if [ "$EUID" -eq 0 ]; then
  PREFIX="/usr"
  APP_DIR="/usr/share/neo-drug"
  BIN_DIR="/usr/bin"
  DESKTOP_DIR="/usr/share/applications"
  ICON_192_DIR="/usr/share/icons/hicolor/192x192/apps"
  ICON_512_DIR="/usr/share/icons/hicolor/512x512/apps"
  ICON_SCALABLE_DIR="/usr/share/icons/hicolor/scalable/apps"
  GLOBAL_INSTALL=1
else
  PREFIX="$HOME/.local"
  APP_DIR="$HOME/.local/share/neo-drug"
  BIN_DIR="$HOME/.local/bin"
  DESKTOP_DIR="$HOME/.local/share/applications"
  ICON_192_DIR="$HOME/.local/share/icons/hicolor/192x192/apps"
  ICON_512_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
  ICON_SCALABLE_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
  GLOBAL_INSTALL=0
fi

echo "=========================================="
echo "  💊 تثبيت تطبيق Neo Drug على لينكس"
echo "=========================================="
if [ "$GLOBAL_INSTALL" -eq 1 ]; then
  echo "• وضع التثبيت: تثبيت عام للنظام بالكامل (/usr)"
else
  echo "• وضع التثبيت: تثبيت خاص بالمستخدم الحالي ($HOME/.local)"
fi

echo "• إنشاء المجلدات المطلوبة..."
mkdir -p "$APP_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_192_DIR"
mkdir -p "$ICON_512_DIR"

echo "• نسخ ملفات التطبيق وقاعدة البيانات..."
cp -r "$SOURCE_DIR"/*.html "$APP_DIR/" 2>/dev/null || true
cp -r "$SOURCE_DIR"/*.js "$APP_DIR/" 2>/dev/null || true
cp -r "$SOURCE_DIR"/*.css "$APP_DIR/" 2>/dev/null || true
cp -r "$SOURCE_DIR"/*.json "$APP_DIR/" 2>/dev/null || true
cp -r "$SOURCE_DIR"/*.png "$APP_DIR/" 2>/dev/null || true
cp "$SOURCE_DIR/neo-drug-app.py" "$APP_DIR/"
chmod +x "$APP_DIR/neo-drug-app.py"

echo "• نسخ الأيقونات..."
cp "$SOURCE_DIR/icon-192.png" "$ICON_192_DIR/neo-drug.png"
cp "$SOURCE_DIR/icon-512.png" "$ICON_512_DIR/neo-drug.png"

echo "• إنشاء أمر التشغيل (neo-drug)..."
cat << 'EOF' > "$BIN_DIR/neo-drug"
#!/usr/bin/env bash
TARGET_DIR=""
if [ -d "/usr/share/neo-drug" ]; then
  TARGET_DIR="/usr/share/neo-drug"
elif [ -d "$HOME/.local/share/neo-drug" ]; then
  TARGET_DIR="$HOME/.local/share/neo-drug"
fi

if [ -n "$TARGET_DIR" ]; then
  export LIBGL_ALWAYS_SOFTWARE=1
  export GALLIUM_DRIVER=llvmpipe
  export WEBKIT_DISABLE_COMPOSITING_MODE=1
  export WEBKIT_DISABLE_DMABUF_RENDERER=1
  export GDK_BACKEND=x11
  export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
  export no_proxy="127.0.0.1,localhost,::1"
  export NO_PROXY="127.0.0.1,localhost,::1"
  exec python3 "$TARGET_DIR/neo-drug-app.py" "$@"
else
  echo "Neo Drug directory not found."
  exit 1
fi
EOF
chmod +x "$BIN_DIR/neo-drug"

echo "• تسجيل اختصار سطح المكتب وقائمة التطبيقات..."
cp "$SOURCE_DIR/neo-drug.desktop" "$DESKTOP_DIR/"
chmod 644 "$DESKTOP_DIR/neo-drug.desktop"

# تحديث قواعد بيانات الديسكتوب والأيقونات إن وجدت
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$(dirname "$(dirname "$ICON_192_DIR")")" 2>/dev/null || true
fi

echo "=========================================="
echo "✅ تم تثبيت Neo Drug بنجاح!"
echo "• يمكنك الآن تشغيل التطبيق بالضغط على أيقونته من قائمة التطبيقات (Applications Menu)"
echo "• أو عبر كتابة الأمر في الطرفية (Terminal): neo-drug"
echo "=========================================="
