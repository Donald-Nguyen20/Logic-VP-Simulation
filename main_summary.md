# Tom tat chi tiet file `main.py`

## Muc dich

`main.py` la diem khoi chay chinh cua ung dung **T-Designer Lite**.
File nay chiu trach nhiem:

- Dam bao thu muc goc cua du an nam trong `sys.path` de import module noi bo.
- Dinh nghia stylesheet QSS toan ung dung.
- Khoi tao `QApplication` cua PySide6.
- Nap cua so chinh `MainWindow` tu module `ui.app`.
- Hien thi cua so chinh o che do phong toan man hinh.
- Bat dau event loop cua Qt.

Lenh chay du kien:

```bash
python main.py
```

Yeu cau moi truong:

- Python 3.8 tro len.
- Thu vien `PySide6`.

Neu chua co PySide6:

```bash
pip install PySide6
```

## Cau truc tong quan

File gom cac phan chinh:

1. Khai bao encoding va docstring gioi thieu.
2. Import cac module he thong: `sys`, `os`.
3. Them thu muc hien tai vao `sys.path`.
4. Khai bao bien `APP_QSS` chua CSS/QSS cho giao dien Qt.
5. Dinh nghia ham `main()`.
6. Goi `main()` khi file duoc chay truc tiep.

## Chi tiet tung thanh phan

### 1. Khai bao encoding va mo ta file

```python
# -*- coding: utf-8 -*-
"""
T-Designer Lite - diem khoi chay.
Chay:  python main.py
Yeu cau: Python 3.8+ va PySide6  (pip install PySide6)
"""
```

Phan nay cho biet file su dung UTF-8 va day la diem khoi chay cua ung dung.
Docstring cung ghi ro cach chay va dependency can thiet.

### 2. Import module he thong

```python
import sys
import os
```

- `sys`: dung de doc tham so dong lenh, thoat chuong trinh, va cau hinh event loop Qt.
- `os`: dung de xac dinh duong dan tuyet doi cua file hien tai.

### 3. Them thu muc goc vao `sys.path`

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

Dung de dam bao Python co the import cac module noi bo cua du an, vi du:

```python
from ui.app import MainWindow
```

Y nghia:

- `__file__`: duong dan file `main.py`.
- `os.path.abspath(__file__)`: chuyen thanh duong dan tuyet doi.
- `os.path.dirname(...)`: lay thu muc chua `main.py`.
- `sys.path.insert(0, ...)`: dua thu muc do len dau danh sach tim module.

Viec chen vao vi tri `0` giup module trong du an duoc uu tien hon module cung ten o noi khac.

## Bien `APP_QSS`

```python
APP_QSS = """ ... """
```

`APP_QSS` la chuoi stylesheet QSS cua Qt, duoc ap dung cho toan bo ung dung bang:

```python
app.setStyleSheet(APP_QSS)
```

QSS co cu phap gan giong CSS, nhung ap dung cho widget cua Qt.

### Phong cach giao dien

Theme tong the:

- Nen sang.
- Mau chu chinh: xanh den/xam dam.
- Mau nhan: xanh indigo.
- Cac control co vien tron nhe.
- Toolbar, dock, menu, input, button, scrollbar deu duoc style rieng.

Bang mau chinh:

- Nen app: `#EEF1F6`
- Nen widget/card/input: `#FFFFFF`
- Mau chu chinh: `#23303F`
- Mau phu: `#2B3A55`
- Accent xanh: `#3B6FE0`
- Accent xanh dam khi hover/pressed: `#2B54B8`, `#21449C`
- Vien nhe: `#D7DEE8`, `#CBD5E3`

### Cac widget duoc style

`APP_QSS` thiet lap giao dien cho:

- Tat ca widget: font `Segoe UI`, fallback `Arial`, co chu `13px`.
- `QMainWindow`, `QWidget`: mau nen va mau chu mac dinh.
- `QToolBar`, `QToolButton`: toolbar trang, nut trong suot, hover/pressed/checked.
- `QDockWidget`: tieu de dock co nen xam xanh va font dam.
- `QTreeWidget`, `QListWidget`, `QPlainTextEdit`, `QTextEdit`: nen trang, vien bo tron.
- Item trong tree/list: hover va selected.
- `QHeaderView::section`: style header cua bang/tree.
- `QLineEdit`, `QComboBox`, `QDoubleSpinBox`, `QSpinBox`: input trang, vien tron, focus border xanh.
- `QPushButton`: nut xanh, hover/pressed/disabled.
- `QGroupBox`: khung trang co vien, title mau xanh.
- `QCheckBox`: spacing giua checkbox va label.
- `QMenu`: menu trang, item hover, item disabled.
- `QStatusBar`: thanh trang thai mau xam xanh.
- `QGraphicsView`: nen gan trang, khong vien.
- `QDialog`: nen giong app.
- `QLabel`: nen trong suot.
- `QScrollBar`: scrollbar doc/ngang thanh manh, bo tron.
- `QToolTip`: tooltip nen xanh dam, chu trang.

## Ham `main()`

```python
def main():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("Thieu PySide6. Cai bang lenh:  pip install PySide6")
        sys.exit(1)
    from ui.app import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())
```

Day la ham khoi dong ung dung.

### Buoc 1: Kiem tra PySide6

```python
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("Thieu PySide6. Cai bang lenh:  pip install PySide6")
    sys.exit(1)
```

Neu PySide6 khong duoc cai dat:

- In thong bao loi ra terminal.
- Thoat chuong trinh voi ma loi `1`.

Dependency `QApplication` duoc import trong ham thay vi tren dau file de co the bat loi thieu PySide6 va hien thong bao than thien hon.

### Buoc 2: Import cua so chinh

```python
from ui.app import MainWindow
```

`MainWindow` la lop cua so chinh cua ung dung.
No nam trong module:

```text
ui/app.py
```

File `main.py` khong tu dinh nghia giao dien chinh, ma chi khoi tao va hien thi `MainWindow`.

### Buoc 3: Tao doi tuong QApplication

```python
app = QApplication(sys.argv)
```

`QApplication` quan ly:

- Event loop cua Qt.
- Tham so dong lenh.
- Style toan cuc.
- Tai nguyen giao dien cua ung dung.

Moi ung dung PySide6 GUI thuong can mot doi tuong `QApplication`.

### Buoc 4: Dat style Qt

```python
app.setStyle("Fusion")
```

Dung style `Fusion`, mot style Qt co giao dien dong nhat giua cac he dieu hanh.
Sau do QSS rieng se duoc ap them len tren style nay.

### Buoc 5: Ap dung QSS

```python
app.setStyleSheet(APP_QSS)
```

Ap dung theme trong `APP_QSS` cho toan bo ung dung.
Moi widget con duoc tao sau do se ke thua hoac bi anh huong boi stylesheet nay neu selector phu hop.

### Buoc 6: Tao va hien thi cua so chinh

```python
win = MainWindow()
win.showMaximized()
```

- Tao instance cua `MainWindow`.
- Hien thi cua so o che do maximize.

Ung dung khong goi `show()` thong thuong, ma dung `showMaximized()` de mo rong cua so ngay khi khoi dong.

### Buoc 7: Chay event loop

```python
sys.exit(app.exec())
```

`app.exec()` bat dau event loop cua Qt.
Tu thoi diem nay, ung dung se lang nghe va xu ly cac su kien nhu:

- Click chuot.
- Go ban phim.
- Ve lai giao dien.
- Dong/mo dialog.
- Tin hieu va slot cua Qt.

Gia tri tra ve cua `app.exec()` duoc truyen vao `sys.exit()` de chuong trinh thoat voi dung exit code.

## Dieu kien chay truc tiep

```python
if __name__ == "__main__":
    main()
```

Doan nay dam bao `main()` chi duoc goi khi chay truc tiep file:

```bash
python main.py
```

Neu file nay duoc import tu file khac, `main()` se khong tu dong chay.

## Luong khoi dong ung dung

Thu tu xu ly khi chay `python main.py`:

1. Python doc file `main.py`.
2. Import `sys` va `os`.
3. Them thu muc du an vao `sys.path`.
4. Nap bien `APP_QSS`.
5. Gap khoi `if __name__ == "__main__"` va goi `main()`.
6. Thu import `QApplication` tu PySide6.
7. Neu thieu PySide6, in thong bao va thoat.
8. Import `MainWindow` tu `ui.app`.
9. Tao `QApplication`.
10. Dat style Qt la `Fusion`.
11. Ap dung stylesheet `APP_QSS`.
12. Tao cua so chinh `MainWindow`.
13. Hien thi cua so chinh o che do maximize.
14. Chay event loop bang `app.exec()`.
15. Khi ung dung dong, tra exit code ve he dieu hanh.

## Phu thuoc quan trong

File nay phu thuoc vao:

- `PySide6.QtWidgets.QApplication`
- `ui.app.MainWindow`

Neu muon hieu logic giao dien chinh, can doc tiep:

```text
ui/app.py
```

## Vai tro cua file trong kien truc du an

`main.py` nen duoc xem la bootstrap file, khong phai noi chua business logic.

Trach nhiem hop ly cua file nay:

- Cau hinh moi truong chay ban dau.
- Cau hinh style/theme toan app.
- Khoi tao app va main window.
- Xu ly loi dependency co ban.

Nhung thu khong nen dua vao file nay:

- Logic nghiep vu.
- Xu ly file/du lieu phuc tap.
- Widget chi tiet.
- Signal/slot phuc tap cua giao dien.
- Logic thao tac nguoi dung.

Nhung phan do nen nam trong cac module rieng, dac biet la `ui.app` va cac module UI/logic khac.

## Ghi chu cho AI khi sua code

- Neu can doi theme toan ung dung, sua bien `APP_QSS`.
- Neu can thay doi cua so dau tien duoc hien thi, sua import `MainWindow` hoac cach khoi tao `win`.
- Neu can them cau hinh app truoc khi hien thi giao dien, them vao sau khi tao `QApplication` va truoc `win.showMaximized()`.
- Neu can ho tro che do cua so khac, thay `win.showMaximized()` bang `win.show()`, `win.showFullScreen()`, hoac logic tuy chon.
- Khong nen dat logic lon vao `main.py`; nen giu file nay nhe va ro vai tro khoi dong.
- Can can than khi sua `sys.path.insert(...)` vi no anh huong cach Python tim module trong toan ung dung.

## Tom tat ngan gon cho AI

`main.py` la entry point cua ung dung PySide6 T-Designer Lite. File nay them thu muc du an vao `sys.path`, dinh nghia QSS theme sang voi accent xanh indigo, kiem tra PySide6, import `MainWindow` tu `ui.app`, tao `QApplication`, ap style `Fusion` va `APP_QSS`, tao cua so chinh, hien thi maximize, roi chay event loop Qt. File nay nen duoc giu nhu bootstrap layer, khong nen chua logic nghiep vu.
