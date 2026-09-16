@echo off
REM ============================================================
REM  Dong goi T-Designer Lite (onedir, nhe) - MOI TRUONG SACH
REM  Tao venv rieng chi co dung thu vien can -> exe nho, khong lan thu vien la.
REM  Chay:  build.bat
REM
REM  Lenh pyinstaller ben duoi TU SINH LAI T-Designer-Lite.spec moi lan chay (vi
REM  target la main.py va co --noconfirm). Dung sua tay file .spec - sua xong
REM  chay build.bat mot cai la mat sach. Can them gi thi them vao lenh o day.
REM ============================================================
cd /d "%~dp0"

REM --- 1) Moi truong sach (tao 1 lan, lan sau tai su dung) ---
REM  requests la BAT BUOC chu khong phai tuy chon: core/llm_client.py import no o
REM  muc module, ma ui/ai_dialog.py va ui/llm_settings_dialog.py lai import
REM  llm_client. Thieu requests thi app van mo len binh thuong roi moi chet luc
REM  nguoi dung bam AI - ban dong goi truoc day dung la nhu vay (trong dist khong
REM  he co requests, urllib3 hay certifi).
if not exist build-env (
    python -m venv build-env
)
call build-env\Scripts\activate
python -m pip install --upgrade pip
pip install PySide6 pyinstaller claude-agent-sdk requests
if errorlevel 1 (
    echo.
    echo [LOI] Cai thu vien that bai - dung o day.
    echo       Chay tiep chi ra mot ban thieu thu vien ma van bao "Xong!".
    pause
    exit /b 1
)

REM --- 2) Dong goi onedir + icon + du lieu core + goi AI (claude-agent-sdk) ---
REM  --noupx: PyInstaller mac dinh nen bang UPX neu tren may co upx. UPX nen DLL
REM  cua Qt la nguyen nhan kinh dien cua kieu loi "chay duoc o may minh, sang may
REM  nguoi dung thi antivirus chan hoac crash luc mo". Khong nen doi lay vai MB.
pyinstaller main.py --name T-Designer-Lite --onedir --windowed --noconfirm --clean ^
  --noupx ^
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
if errorlevel 1 (
    echo.
    echo [LOI] PyInstaller bao loi - xem thong bao o tren.
    pause
    exit /b 1
)

REM --- 3) Chep dinh nghia macro cua hang (DEF) di kem ---
REM  Vi sao can: core/def_sim.py mo phong KHOI TRAM bang cach chay THANG than
REM  lenh goc trong TAG_MCR.DEF, con core/block_params.py doc kieu/mac dinh/gioi
REM  han tham so tu macro_param.csv. Hai nguon nay nam NGOAI repo
REM  (C:\T_Designer\DEF) nen ban dong goi khong tu co chung. Do tren 21 file .db
REM  cua du an: mat DEF thi 12.667/12.871 khoi tram BIEN MAT khoi mo phong dong
REM  - cua chan o sheet_dyn.py dong 475, ma mo hinh du phong macro_analog.json
REM  chi phu duoc 204 khoi - va param_meta() tut tu 586 ma khoi xuong 0.
REM
REM  Chep RA CANH file exe chu khong nhet vao _internal: find_def_files() trong
REM  core/macro_def.py lui 3 cap tu core/ ra roi tim "<thu muc app>\DEF\SR21E".
REM  Ban onedir dat core/ o <app>\_internal\core nen lui 3 cap ra dung <app> -
REM  cho nay san co, khong phai sua code.
REM
REM  Khong dung --add-data: PyInstaller 6.18 HUY BUILD neu duong dan nguon khong
REM  ton tai ("ERROR: Unable to find ... when adding binary and data files"),
REM  tuc may nao khong cai T-Designer se het build duoc.
REM
REM  Chep ca 6 thu muc TYPE_*: than lenh trung ten thi GIONG HET nhau, chung chi
REM  khac o cho moi thu muc chua bao nhieu macro. Rieng 82FD (1.898 khoi trong
REM  du an) va 82FE (222 khoi) CHI co trong TYPE_B_CPUX01. Danh sach duoi day
REM  phai khop _DEF_DIRS trong core/macro_def.py.
set D=dist\T-Designer-Lite
set "DEFSRC=%~dp0..\DEF\SR21E"
set "DEFDST=%D%\DEF\SR21E"
set CODEF=0
if exist "%DEFSRC%\macro_param.csv" (
    if not exist "%DEFDST%" mkdir "%DEFDST%"
    copy /Y "%DEFSRC%\macro_param.csv" "%DEFDST%\" >nul
    for %%T in (TYPE_A_CPUW01 TYPE_A_CPUW02 TYPE_A_CPUW11 TYPE_A_CPUW12 TYPE_A_CPUX02 TYPE_B_CPUX01) do (
        if exist "%DEFSRC%\%%T\TAG_MCR.DEF" (
            if not exist "%DEFDST%\%%T" mkdir "%DEFDST%\%%T"
            copy /Y "%DEFSRC%\%%T\TAG_MCR.DEF" "%DEFDST%\%%T\" >nul
            copy /Y "%DEFSRC%\%%T\TODEN.DEF"   "%DEFDST%\%%T\" >nul
        )
    )
    set CODEF=1
    echo [OK] Da chep dinh nghia macro cua hang vao %DEFDST%
)

REM --- 4) Soi lai ban vua dong goi ---
REM  Thieu bat cu thu nao duoi day, pyinstaller van bao thanh cong: app cu mo len
REM  binh thuong roi chet dung luc nguoi dung bam vao tinh nang. Kiem o day re hon
REM  nhieu so voi phat hien tren may nguoi dung.
set LOI=0
if not exist "%D%\T-Designer-Lite.exe" (
    echo [THIEU] file exe
    set LOI=1
)
REM  Goi PYTHON THUAN (requests, urllib3) KHONG hien ra thanh thu muc trong
REM  _internal: PyInstaller nen chung vao kho PYZ nam BEN TRONG file exe. Chi goi
REM  nao co file du lieu (certifi: cacert.pem) hay .pyd (charset_normalizer) moi
REM  duoc bung ra thu muc. Do lai tren ban 30/08: _internal khong he co thu muc
REM  'requests' nhung PYZ-00.toc liet du 17 module requests.* va 36 module
REM  urllib3.* - ban dong goi DUNG, chi cai kiem "if not exist" la sai va bao
REM  dong gia. Vay phai soi DANH MUC PYZ. File .toc do chinh buoc build vua roi
REM  sinh ra (co --clean nen khong the la ban cu con sot).
set TOC=build\T-Designer-Lite\PYZ-00.toc
set COREQ=0
if exist "%D%\_internal\requests" set COREQ=1
findstr /C:"'requests.sessions'" "%TOC%" >nul 2>&1
if not errorlevel 1 set COREQ=1
if "%COREQ%"=="0" (
    echo [THIEU] goi requests - AI Groq/Gemini/NVIDIA se chet khi bam
    set LOI=1
)
if not exist "%D%\_internal\icon.ico" (
    echo [THIEU] icon.ico - main.py doc file nay luc chay de dat icon cua so
    set LOI=1
)
if not exist "%D%\_internal\core\internal_design" (
    echo [THIEU] core\internal_design - ban ve logic noi bo se trong
    set LOI=1
)
if not exist "%D%\_internal\core\internal_figs" (
    echo [THIEU] core\internal_figs - hinh khoi trong tra cuu se trong
    set LOI=1
)
if "%CODEF%"=="0" (
    echo [CANH BAO] Khong thay DEF\SR21E cua T-Designer canh thu muc du an.
    echo            Ban dong goi nay se KHONG mo phong duoc khoi tram MV/SV va
    echo            mat kieu/mac dinh/gioi han tham so. Cac phan con lai
    echo            ^(logic, analog, F^(x^), timer^) van chay binh thuong.
)
if "%CODEF%"=="1" (
    if not exist "%DEFDST%\TYPE_A_CPUW01\TAG_MCR.DEF" (
        echo [THIEU] DEF\SR21E\TYPE_A_CPUW01\TAG_MCR.DEF - khoi tram se khong mo phong duoc
        set LOI=1
    )
)
if not exist "%D%\_internal\claude_agent_sdk\_bundled\claude.exe" (
    echo [CANH BAO] Thieu claude.exe di kem: AI Claude se doi may nguoi dung
    echo            tu cai Node. Cac nha AI khac khong anh huong.
)

echo.
echo ============================================================
if "%LOI%"=="1" (
    echo  CHUA XONG - con thieu nhu liet ke o tren. Dung dem ban nay di cai.
) else (
    echo  Xong! Chay file:  dist\T-Designer-Lite\T-Designer-Lite.exe
)
echo ============================================================
pause
