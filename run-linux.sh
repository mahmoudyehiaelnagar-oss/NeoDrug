#!/usr/bin/env bash
# ==============================================================================
# Neo Drug — Linux Launcher (Native Standalone Application)
# تشغيل تطبيق ديسكتوب لينكس الأصلي المستقل (GTK3 Native Window)
# ==============================================================================

# --------------------------------------------------------------
# تعريف مسار السكريبت واختيار الـ backend المناسب
# --------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# إذا كان هناك جلسة Wayland → استخدم Wayland
if [ -n "$WAYLAND_DISPLAY" ]; then
    export GDK_BACKEND="wayland"
    echo "⚙️  اختيار Wayland (GDK_BACKEND=wayland)"
# وإلا إذا كان هناك X11 (متغيّر DISPLAY) → استخدم X11
elif [ -n "$DISPLAY" ]; then
    export GDK_BACKEND="x11"
    echo "⚙️  اختيار X11 (GDK_BACKEND=x11)"
else
    echo "⚠️  لا يوجد DISPLAY ولا WAYLAND_DISPLAY – قد لا تعمل الواجهة الرسومية."
fi

# المتغيّرات اللازمة لتفادي الشاشة السوداء على معالجات Intel Haswell
export DISPLAY=${DISPLAY:-:0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}

cd "$SCRIPT_DIR"

# ----------------------------------------------------------------------
# 1️⃣ إعدادات لتفادي الشاشة السوداء (يمكن إلغاء الGPU عبر NEODRUG_GPU_ACCEL=1)
# ----------------------------------------------------------------------
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1

# ----------------------------------------------------------------------
# 2️⃣ تجاوز قيود AppArmor / sandbox (مطلوب للـ WebKit)
# ----------------------------------------------------------------------
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1

# ----------------------------------------------------------------------
# 3️⃣ إعدادات البروكسي (نتأكد أن الطلب المحلي لا يُمرّر عبر proxy)
# ----------------------------------------------------------------------
export no_proxy="127.0.0.1,localhost,::1"
export NO_PROXY="127.0.0.1,localhost,::1"

chmod +x neo-drug-app.py 2>/dev/null

echo "=========================================="
echo "  💊 Neo Drug — تطبيق لينكس الأصلي المستقل"
echo "=========================================="
echo "جاري فتح نافذة التطبيق الأصلية المستقلة (GTK3)..."

# تشغيل التطبيق
python3 "$SCRIPT_DIR/neo-drug-app.py" "$@"
