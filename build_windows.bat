@echo off
chcp 65001 > nul
echo ========================================================
echo   💊 بناء تطبيق ومثبت Neo Drug لويندوز (Windows Build)
echo ========================================================

echo 1. تثبيت الحزم المطلوبة...
python -m pip install pywebview uvicorn fastapi sqlalchemy

echo 2. بناء التطبيق المستقل عبر PyInstaller...
python -m PyInstaller -y --noconsole --name="NeoDrug_Portable" --icon="backend/public/icon-512.png" --add-data "backend/public;backend/public" standalone_app.py

echo.
echo ========================================================
echo ✓ تم بناء ملف البرنامج بنجاح داخل مجلد: dist\NeoDrug_Portable
echo.
echo لتوليد مثبت Windows Setup.exe التلقائي:
echo افتح ملف installer_windows.iss ببرنامج Inno Setup المجاني واضغط Compile.
echo ========================================================
pause
