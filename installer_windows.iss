; Inno Setup Script for Neo Drug Windows Installer
; سكريبت توليد ملف التثبيت الاحترافي للويندوز (Setup.exe)
; يقوم بتثبيت البرنامج في Program Files وعمل اختصار في قائمة ابدأ وسطح المكتب

[Setup]
AppName=Neo Drug
AppVersion=1.0.0
AppPublisher=Mahmoud Yehia (محمود النجار)
AppPublisherURL=https://neo-drug.vercel.app
DefaultDirName={autopf}\NeoDrug
DefaultGroupName=Neo Drug
OutputDir=dist_installer
OutputBaseFilename=NeoDrug_Setup_Windows
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب (Create Desktop Shortcut)"; GroupDescription: "اختصارات إضافية:"

[Files]
; الملفات الناتجة من PyInstaller
Source: "dist\NeoDrug_Portable\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; اختصار في قائمة ابدأ (Start Menu)
Name: "{group}\Neo Drug — دليل الأدوية المصري"; Filename: "{app}\NeoDrug_Portable.exe"
Name: "{group}\إلغاء التثبيت (Uninstall)"; Filename: "{uninstallexe}"
; اختصار على سطح المكتب (Desktop Shortcut)
Name: "{autodesktop}\Neo Drug"; Filename: "{app}\NeoDrug_Portable.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NeoDrug_Portable.exe"; Description: "تشغيل التطبيق فوراً (Launch Neo Drug)"; Flags: nowait postinstall skipifsilent
