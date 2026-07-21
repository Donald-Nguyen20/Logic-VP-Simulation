@echo off
REM ============================================================
REM  Dong goi T-Designer Lite (onedir, nhe) - MOI TRUONG SACH
REM  Tao venv rieng chi co PySide6 -> exe nho, khong lan thu vien la.
REM  Chay:  build.bat
REM ============================================================
cd /d "%~dp0"

REM --- 1) Moi truong sach chi co PySide6 (tao 1 lan, lan sau tai su dung) ---
if not exist build-env (
    python -m venv build-env
)
call build-env\Scripts\activate
python -m pip install --upgrade pip
pip install PySide6 pyinstaller claude-agent-sdk

REM --- 2) Dong goi onedir + icon + du lieu core + goi AI (claude-agent-sdk) ---
pyinstaller main.py --name T-Designer-Lite --onedir --windowed --noconfirm --clean ^
  --icon icon.ico ^
  --add-data "core;core" ^
  --add-data "icon.ico;." ^
  --collect-all claude_agent_sdk ^
  --exclude-module tkinter --exclude-module numpy --exclude-module matplotlib ^
  --exclude-module pandas --exclude-module scipy --exclude-module PIL ^
  --exclude-module fitz --exclude-module pdfplumber --exclude-module pdfminer ^
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtQuick3D ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.QtWebChannel --exclude-module PySide6.QtWebSockets ^
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.QtMultimediaWidgets --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtDataVisualization --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtPdfWidgets --exclude-module PySide6.QtSql ^
  --exclude-module PySide6.QtSvg --exclude-module PySide6.QtSvgWidgets ^
  --exclude-module PySide6.QtOpenGL --exclude-module PySide6.QtOpenGLWidgets ^
  --exclude-module PySide6.QtPrintSupport --exclude-module PySide6.QtTest ^
  --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtUiTools ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtXml ^
  --exclude-module PySide6.QtConcurrent --exclude-module PySide6.QtPositioning

echo.
echo ============================================================
echo  Xong! Chay file:  dist\T-Designer-Lite\T-Designer-Lite.exe
echo ============================================================
pause
