#!/usr/bin/env bash
# ==============================================================================
# Neo Drug — Debian (.deb) Package Builder
# بناء حزمة تثبيت لينكس الرسمية بصيغة .deb لنظام Zorin OS / Ubuntu / Debian
# ==============================================================================

set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_NAME="neo-drug"
VERSION="1.0.0"
ARCH="all"
BUILD_DIR="$SOURCE_DIR/build/deb-package"
OUTPUT_DEB="$SOURCE_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

echo "=========================================="
echo "  📦 بناء حزمة لينكس: ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo "=========================================="

# تنظيف مسار البناء القديم
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/neo-drug"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/192x192/apps"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps"

# 1. ملف التحكم control
cat << EOF > "$BUILD_DIR/DEBIAN/control"
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: science
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Maintainer: Mahmoud <mahmoud@neodrug.local>
Description: Egyptian Drug Guide & Medical AI (دليل الأدوية المصري)
 Neo Drug is a modern, comprehensive Egyptian drug guide application featuring
 over 9,700 registered medications, generic equivalents, drug interaction checker,
 and clinical AI assistant with an interactive visual creative design.
EOF

# 2. ملف postinst (يتم تشغيله بعد التثبيت لتحديث أيقونات النظام واختصارات سطح المكتب)
cat << 'EOF' > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/sh
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi

exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

# 3. ملف prerm (يتم تشغيله قبل الإزالة)
cat << 'EOF' > "$BUILD_DIR/DEBIAN/prerm"
#!/bin/sh
set -e
exit 0
EOF
chmod 755 "$BUILD_DIR/DEBIAN/prerm"

# 4. نسخ ملفات التطبيق وقاعدة البيانات والواجهة الإبداعية
echo "• نسخ ملفات التطبيق..."
cp -r "$SOURCE_DIR"/*.html "$BUILD_DIR/usr/share/neo-drug/"
cp -r "$SOURCE_DIR"/*.js "$BUILD_DIR/usr/share/neo-drug/"
cp -r "$SOURCE_DIR"/*.css "$BUILD_DIR/usr/share/neo-drug/"
cp -r "$SOURCE_DIR"/*.json "$BUILD_DIR/usr/share/neo-drug/"
cp -r "$SOURCE_DIR"/*.png "$BUILD_DIR/usr/share/neo-drug/"
cp "$SOURCE_DIR/neo-drug-app.py" "$BUILD_DIR/usr/share/neo-drug/"
chmod +x "$BUILD_DIR/usr/share/neo-drug/neo-drug-app.py"

# 5. تثبيت الأيقونات
echo "• تثبيت الأيقونات..."
cp "$SOURCE_DIR/icon-192.png" "$BUILD_DIR/usr/share/icons/hicolor/192x192/apps/neo-drug.png"
cp "$SOURCE_DIR/icon-512.png" "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps/neo-drug.png"

# 6. تثبيت ملف الديسكتوب
echo "• تثبيت اختصار الديسكتوب..."
cp "$SOURCE_DIR/neo-drug.desktop" "$BUILD_DIR/usr/share/applications/"
chmod 644 "$BUILD_DIR/usr/share/applications/neo-drug.desktop"

# 7. إنشاء الملف التنفيذي في /usr/bin/neo-drug
cat << 'EOF' > "$BUILD_DIR/usr/bin/neo-drug"
#!/usr/bin/env bash
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export GDK_BACKEND=x11
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
export no_proxy="127.0.0.1,localhost,::1"
export NO_PROXY="127.0.0.1,localhost,::1"
exec python3 /usr/share/neo-drug/neo-drug-app.py "$@"
EOF
chmod 755 "$BUILD_DIR/usr/bin/neo-drug"

# 8. ضبط الصلاحيات القياسية لحزم دبيان
find "$BUILD_DIR" -type d -exec chmod 755 {} +

# 9. تجميع الحزمة عبر dpkg-deb
echo "• تجميع ملف .deb..."
dpkg-deb --build --root-owner-group "$BUILD_DIR" "$OUTPUT_DEB"

# تنظيف المجلد المؤقت
rm -rf "$BUILD_DIR"

echo "=========================================="
echo "✅ تم بناء حزمة لينكس بنجاح!"
echo "📁 الملف الناتج: $OUTPUT_DEB"
echo "الحجم: $(ls -lh "$OUTPUT_DEB" | awk '{print $5}')"
echo "للتثبيت المباشر على النظام يمكنك تشغيل:"
echo "   sudo apt install ./$(basename "$OUTPUT_DEB")"
echo "   أو الضغط مرتين (Double Click) على الملف لتثبيته بمتجر البرامج"
echo "=========================================="
