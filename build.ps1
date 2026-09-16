# =============================================================================
#  Dong goi Logic Simulation - ban PowerShell, thay cho build.bat
#  Chay:  .\build.ps1              (ten mac dinh "Logic Simulation 1.1")
#         .\build.ps1 -Ten "..."   (doi ten ban dong goi)
#         .\build.ps1 -Sach        (dung venv rieng, giong het build.bat cu)
#
#  Vi sao co ban .ps1 nay: lenh trong build.bat noi dong bang dau ^ - do la cu
#  phap cua cmd.exe. Dan thang no vao PowerShell la vo mot loat loi
#  "Missing expression after unary operator '--'". PowerShell noi dong bang dau
#  backtick, con o day thi khoi can noi dong: gom tham so vao mang la xong.
# =============================================================================
param(
    [string]$Ten  = 'Logic Simulation 1.1',
    [switch]$Sach                                  # -Sach: dung venv build-env rieng
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# --- 1) Thu vien bat buoc -----------------------------------------------------
#  requests KHONG phai tuy chon: core/llm_client.py va core/llm_nvidia.py import
#  no ngay o muc module, ma ui/ai_dialog.py lai import llm_client. Thieu requests
#  thi app van mo len binh thuong roi moi chet dung luc nguoi dung bam AI - ban
#  dong goi 30/08 dung la nhu vay (trong dist khong he co requests, urllib3).
$py = 'python'
if ($Sach) {
    if (-not (Test-Path 'build-env')) { python -m venv build-env }
    $py = Join-Path $PSScriptRoot 'build-env\Scripts\python.exe'
}
& $py -m pip install --upgrade pip
& $py -m pip install --upgrade PySide6 pyinstaller claude-agent-sdk requests
if ($LASTEXITCODE -ne 0) {
    Write-Host '[LOI] Cai thu vien that bai - dung o day.' -ForegroundColor Red
    Write-Host '      Chay tiep chi ra mot ban thieu thu vien ma van bao "Xong!".'
    exit 1
}

# --- 2) Dong goi --------------------------------------------------------------
#  --noupx: PyInstaller mac dinh nen bang UPX neu tren may co upx. UPX nen DLL
#  cua Qt la nguyen nhan kinh dien cua kieu loi "chay duoc o may minh, sang may
#  nguoi dung thi antivirus chan hoac crash luc mo". Khong nen doi lay vai MB.
$tham = @(
    'main.py'
    '--name',        $Ten
    '--onedir'
    '--windowed'
    '--noconfirm'
    '--clean'
    '--noupx'
    '--icon',        'icon.ico'
    '--add-data',    'core;core'
    '--add-data',    'icon.ico;.'
    '--collect-all', 'claude_agent_sdk'
)
#  Bo bot nhung goi khong dung den. Chu y PySide6.QtNetwork: app goi mang bang
#  requests (python thuan) chu khong qua Qt, nen bo di khong anh huong gi.
$bo = @(
    'tkinter', 'numpy', 'matplotlib', 'pandas', 'scipy', 'PIL'
    'fitz', 'pdfplumber', 'pdfminer'
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuick3D'
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel'
    'PySide6.QtWebSockets', 'PySide6.QtNetwork', 'PySide6.QtMultimedia'
    'PySide6.QtMultimediaWidgets', 'PySide6.QtCharts', 'PySide6.QtDataVisualization'
    'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSql'
    'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets'
    'PySide6.QtPrintSupport', 'PySide6.QtTest', 'PySide6.QtDesigner', 'PySide6.QtUiTools'
    'PySide6.Qt3DCore', 'PySide6.QtXml', 'PySide6.QtConcurrent', 'PySide6.QtPositioning'
)
foreach ($m in $bo) { $tham += '--exclude-module'; $tham += $m }

& $py -m PyInstaller @tham
if ($LASTEXITCODE -ne 0) {
    Write-Host '[LOI] PyInstaller bao loi - xem thong bao o tren.' -ForegroundColor Red
    exit 1
}

# --- 3) Chep dinh nghia macro cua hang (DEF) di kem --------------------------
#  Vi sao can: core/def_sim.py mo phong KHOI TRAM bang cach chay THANG than lenh
#  goc trong TAG_MCR.DEF, con core/block_params.py doc kieu/mac dinh/gioi han
#  tham so tu macro_param.csv. Hai nguon nay nam NGOAI repo (C:\T_Designer\DEF)
#  nen ban dong goi khong tu co chung. Do tren 21 file .db cua du an: mat DEF thi
#  12.667/12.871 khoi tram BIEN MAT khoi mo phong dong - cua chan o sheet_dyn.py
#  dong 475, ma mo hinh du phong macro_analog.json chi phu duoc 204 khoi - va
#  param_meta() tut tu 586 ma khoi xuong 0.
#
#  Chep RA CANH file exe chu khong nhet vao _internal: find_def_files() trong
#  core/macro_def.py lui 3 cap tu core/ ra roi tim "<thu muc app>\DEF\SR21E".
#  Ban dong goi onedir dat core/ o <app>\_internal\core nen lui 3 cap ra dung
#  <app> - cho nay san co, khong phai sua code. Them nua sau nay hang cap nhat
#  DEF thi chi viec de len, khong can dong goi lai.
#
#  Khong dung --add-data: PyInstaller 6.18 HUY BUILD neu duong dan nguon khong
#  ton tai ("ERROR: Unable to find ... when adding binary and data files"), tuc
#  may nao khong cai T-Designer se het build duoc. Chep sau khi build thi thieu
#  DEF chi con la mot canh bao.
#
#  Chep ca 6 thu muc TYPE_*: doi chieu thay than lenh trung ten thi GIONG HET
#  nhau, chung chi khac o cho moi thu muc chua bao nhieu macro. Rieng 82FD
#  (1.898 khoi trong du an) va 82FE (222 khoi) CHI co trong TYPE_B_CPUX01.
#  Danh sach duoi day phai khop _DEF_DIRS trong core/macro_def.py.
$DEF_DIRS = @('TYPE_A_CPUW01', 'TYPE_A_CPUW02', 'TYPE_A_CPUW11',
              'TYPE_A_CPUW12', 'TYPE_A_CPUX02', 'TYPE_B_CPUX01')
$D      = Join-Path 'dist' $Ten
$defSrc = Join-Path (Split-Path $PSScriptRoot -Parent) 'DEF\SR21E'
$defDst = Join-Path $D 'DEF\SR21E'
$coDef  = $false
if (Test-Path (Join-Path $defSrc 'macro_param.csv')) {
    New-Item -ItemType Directory -Force -Path $defDst | Out-Null
    Copy-Item (Join-Path $defSrc 'macro_param.csv') $defDst -Force
    foreach ($d in $DEF_DIRS) {
        $s = Join-Path $defSrc $d
        if (-not (Test-Path (Join-Path $s 'TAG_MCR.DEF'))) { continue }
        $t = Join-Path $defDst $d
        New-Item -ItemType Directory -Force -Path $t | Out-Null
        foreach ($f in @('TAG_MCR.DEF', 'TODEN.DEF')) {
            $q = Join-Path $s $f
            if (Test-Path $q) { Copy-Item $q $t -Force }
        }
    }
    $coDef = $true
    Write-Host "[OK] Da chep dinh nghia macro cua hang vao $defDst" -ForegroundColor Green
}

# --- 4) Soi lai ban vua dong goi ---------------------------------------------
#  Thieu bat cu thu nao duoi day, PyInstaller VAN bao thanh cong: app cu mo len
#  binh thuong roi chet dung luc nguoi dung bam vao tinh nang. Kiem o day re hon
#  nhieu so voi phat hien tren may nguoi dung.
$TOC = Join-Path 'build' (Join-Path $Ten 'PYZ-00.toc')
$loi = @()

if (-not (Test-Path (Join-Path $D "$Ten.exe")))            { $loi += 'file exe' }
if (-not (Test-Path "$D\_internal\icon.ico"))              { $loi += 'icon.ico - main.py doc file nay luc chay de dat icon cua so' }
if (-not (Test-Path "$D\_internal\core\internal_design"))  { $loi += 'core\internal_design - ban ve logic noi bo se trong' }
if (-not (Test-Path "$D\_internal\core\internal_figs"))    { $loi += 'core\internal_figs - hinh khoi trong tra cuu se trong' }

#  Goi PYTHON THUAN (requests, urllib3) KHONG hien ra thanh thu muc trong
#  _internal: PyInstaller nen chung vao kho PYZ nam BEN TRONG file exe. Chi goi
#  nao co file du lieu (certifi: cacert.pem) hay .pyd (charset_normalizer) moi
#  duoc bung ra thu muc. Do lai tren ban 30/08: _internal khong he co thu muc
#  'requests' nhung PYZ-00.toc liet du 17 module requests.* va 36 module
#  urllib3.* - ban dong goi DUNG, chi cai kiem "co thu muc khong" la sai va bao
#  dong gia. Vay phai soi DANH MUC PYZ. File .toc do chinh buoc build vua roi
#  sinh ra (co --clean nen khong the la ban cu con sot).
$coRequests = (Test-Path "$D\_internal\requests") -or `
              ((Test-Path $TOC) -and
               (Select-String -Path $TOC -SimpleMatch "'requests.sessions'" -Quiet))
if (-not $coRequests) { $loi += 'goi requests - AI Groq/Gemini/NVIDIA se chet khi bam' }

if ($coDef) {
    if (-not (Test-Path "$defDst\TYPE_A_CPUW01\TAG_MCR.DEF")) { $loi += 'DEF\SR21E\TYPE_A_CPUW01\TAG_MCR.DEF - khoi tram MV/SV se khong mo phong duoc' }
    if (-not (Test-Path "$defDst\macro_param.csv"))           { $loi += 'DEF\SR21E\macro_param.csv - mat kieu/mac dinh/gioi han tham so' }
} else {
    Write-Host '[CANH BAO] Khong thay DEF\SR21E cua T-Designer canh thu muc du an.'  -ForegroundColor Yellow
    Write-Host '           Ban dong goi nay se KHONG mo phong duoc khoi tram MV/SV' -ForegroundColor Yellow
    Write-Host '           va mat kieu/mac dinh/gioi han tham so. Cac phan con lai'  -ForegroundColor Yellow
    Write-Host '           (logic, analog, F(x), timer) van chay binh thuong.'       -ForegroundColor Yellow
}

if (-not (Test-Path "$D\_internal\claude_agent_sdk\_bundled\claude.exe")) {
    Write-Host '[CANH BAO] Thieu claude.exe di kem: AI Claude se doi may nguoi dung' -ForegroundColor Yellow
    Write-Host '           tu cai Node. Cac nha AI khac khong anh huong.'  -ForegroundColor Yellow
}

Write-Host ''
Write-Host '============================================================'
if ($loi) {
    foreach ($x in $loi) { Write-Host "[THIEU] $x" -ForegroundColor Red }
    Write-Host ' CHUA XONG - con thieu nhu liet ke o tren. Dung dem ban nay di cai.' -ForegroundColor Red
    Write-Host '============================================================'
    exit 1
}
Write-Host " Xong! Chay file:  $D\$Ten.exe" -ForegroundColor Green
Write-Host '============================================================'
