#!/usr/bin/env bash
# ==============================================================================
# Neo Drug — Linux Uninstaller Script
# سكريبت إلغاء تثبيت تطبيق Neo Drug
# ==============================================================================

echo "=========================================="
echo "  🗑️ إلغاء تثبيت تطبيق Neo Drug"
echo "=========================================="

# حذف الملفات العامة إن وجدت (تتطلب root)
if [ -d "/usr/share/neo-drug" ] || [ -f "/usr/bin/neo-drug" ]; then
  if [ "$EUID" -eq 0 ]; then
    echo "• إزالة الملفات العامة (/usr)..."
    rm -rf /usr/share/neo-drug
    rm -f /usr/bin/neo-drug
    rm -f /usr/share/applications/neo-drug.desktop
    rm -f /usr/share/icons/hicolor/*/apps/neo-drug.png
  else
    echo "• ملاحظة: توجد ملفات مثبتة على مستوى النظام، يمكنك تشغيل: sudo ./uninstall.sh لإزالتها."
  fi
fi

# حذف الملفات الخاصة بالمستخدم الحالي
echo "• إزالة ملفات المستخدم ($HOME/.local)..."
rm -rf "$HOME/.local/share/neo-drug"
rm -f "$HOME/.local/bin/neo-drug"
rm -f "$HOME/.local/share/applications/neo-drug.desktop"
rm -f "$HOME/.local/share/icons/hicolor/*/apps/neo-drug.png"

# تحديث قاعدة بيانات التطبيقات
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
  if [ "$EUID" -eq 0 ]; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
  fi
fi

echo "✅ تم إلغاء التثبيت بنجاح."
