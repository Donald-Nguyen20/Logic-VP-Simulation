# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('core', 'core'), ('icon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'numpy', 'matplotlib', 'pandas', 'scipy', 'PIL', 'fitz', 'pdfplumber', 'pdfminer', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuick3D', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel', 'PySide6.QtWebSockets', 'PySide6.QtNetwork', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSql', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPrintSupport', 'PySide6.QtTest', 'PySide6.QtDesigner', 'PySide6.QtUiTools', 'PySide6.Qt3DCore', 'PySide6.QtXml', 'PySide6.QtConcurrent', 'PySide6.QtPositioning'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='T-Designer-Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='T-Designer-Lite',
)
