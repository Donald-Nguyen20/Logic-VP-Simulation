# -*- coding: utf-8 -*-
"""
T-Designer Lite - diem khoi chay.
Chay:  python main.py
Yeu cau: Python 3.8+ va PySide6  (pip install PySide6)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Bo mau giao dien chinh: sang, hien dai. Moi nhom nut toolbar 1 mau rieng ---
#   panel  (FB Library, DB Files)      -> cam hoi (mo/dong bang)
#   import (Import DB/folder/PDF)      -> xanh ngoc (du lieu di vao)
#   nav    (< Back)                    -> xam trung tinh (dieu huong)
#   view   (Zoom +/-, Fit, 100%)       -> tim (thao tac xem)
#   sim    (Simulate on sheet, toggle) -> xanh la khi BAT (dang mo phong)
#   mac dinh                           -> indigo (mau thuong hieu chinh)
APP_QSS = """
* { font-family: 'Segoe UI', Arial; font-size: 13px; }
QMainWindow, QWidget { background: #F3F5FB; color: #1E2433; }

QToolBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E6EAF3;
           padding: 6px; spacing: 4px; }
QToolBar QToolButton { background: transparent; color: #3346B5;
           padding: 7px 14px; border-radius: 8px; font-weight: 600;
           border: 1px solid transparent; }
QToolBar QToolButton:hover { background: #E8ECFF; color: #2438A8; border-color: #C7D2FE; }
QToolBar QToolButton:pressed { background: #D6DEFF; }
QToolBar QToolButton:checked { background: #4F6BFF; color: #FFFFFF; }
QToolBar QToolButton:checked:hover { background: #3D57E8; }
QToolBar::separator { background: #E6EAF3; width: 1px; margin: 6px 6px; }

/* nhom: mo/dong panel -> cam */
QToolBar QToolButton[grp="panel"] { color: #C2650A; }
QToolBar QToolButton[grp="panel"]:hover { background: #FFF1E0; color: #9A4E06; border-color: #FBD9AD; }
QToolBar QToolButton[grp="panel"]:pressed { background: #FFE3BF; }
QToolBar QToolButton[grp="panel"]:checked { background: #F59E0B; color: #FFFFFF; }
QToolBar QToolButton[grp="panel"]:checked:hover { background: #DB8B04; }

/* nhom: import du lieu -> xanh ngoc */
QToolBar QToolButton[grp="import"] { color: #0A8A9C; }
QToolBar QToolButton[grp="import"]:hover { background: #E0F7FA; color: #076B7A; border-color: #A6E6EE; }
QToolBar QToolButton[grp="import"]:pressed { background: #C8EEF3; }

/* nhom: dieu huong -> xam trung tinh */
QToolBar QToolButton[grp="nav"] { color: #56617A; }
QToolBar QToolButton[grp="nav"]:hover { background: #EEF1F7; color: #333E52; border-color: #D7DEE8; }
QToolBar QToolButton[grp="nav"]:pressed { background: #E1E6EF; }

/* nhom: zoom/xem -> tim */
QToolBar QToolButton[grp="view"] { color: #7C3AED; }
QToolBar QToolButton[grp="view"]:hover { background: #F1E9FE; color: #6423D0; border-color: #DAC4FB; }
QToolBar QToolButton[grp="view"]:pressed { background: #E3D2FD; }

/* nhom: mo phong -> xanh la khi bat */
QToolBar QToolButton[grp="sim"]:hover { background: #E3FAF0; color: #0C8F63; border-color: #B7EFDC; }
QToolBar QToolButton[grp="sim"]:checked { background: #10B981; color: #FFFFFF; }
QToolBar QToolButton[grp="sim"]:checked:hover { background: #0EA271; }

QDockWidget { color: #1E2433; }
QDockWidget::title { background: #E9EEFA; padding: 7px 12px; font-weight: 700;
           color: #2B3A55; border-bottom: 1px solid #DDE4F1; }

QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit {
           background: #FFFFFF; border: 1px solid #DDE4F1; border-radius: 8px; }
QTreeWidget::item, QListWidget::item { padding: 4px 3px; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #F1F5FF; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #DDE6FF; color: #2438A8; }
QHeaderView::section { background: #E9EEFA; border: none; padding: 4px; }

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
           background: #FFFFFF; border: 1px solid #CDD6E8; border-radius: 7px;
           padding: 5px 9px; selection-background-color: #4F6BFF; selection-color: #FFFFFF; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #4F6BFF; }
QComboBox::drop-down { border: none; width: 20px; }

QPushButton { background: #4F6BFF; color: #FFFFFF; border: none; border-radius: 8px;
           padding: 8px 18px; font-weight: 600; }
QPushButton:hover { background: #3D57E8; }
QPushButton:pressed { background: #2C42C4; }
QPushButton:disabled { background: #D7DCEC; color: #9AA4BE; }

QGroupBox { border: 1px solid #DDE4F1; border-radius: 10px; margin-top: 12px; background: #FFFFFF; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px;
           color: #2438A8; font-weight: 700; }
QCheckBox { spacing: 7px; }

QMenu { background: #FFFFFF; border: 1px solid #DDE4F1; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 5px; }
QMenu::item:selected { background: #DDE6FF; color: #2438A8; }
QMenu::item:disabled { color: #A9B4C4; }

QStatusBar { background: #E9EEFA; color: #4A5A70; border-top: 1px solid #DDE4F1; }
QGraphicsView { background: #FBFCFF; border: none; }
QDialog { background: #F3F5FB; }
QLabel { background: transparent; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #CBD3E6; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #9AA8BE; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: #CBD3E6; border-radius: 5px; min-width: 26px; }
QScrollBar::handle:horizontal:hover { background: #9AA8BE; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: #2B3A55; color: #FFFFFF; border: none; padding: 5px 9px; border-radius: 5px; }
"""

# Luat nay phai ghep rieng vi no can duong dan file anh, ma APP_QSS thi day dau
# ngoac nhon cua CSS nen khong dung .format() duoc.
QSS_MUI_TEN = """
QComboBox::down-arrow { image: url(%s); width: 11px; height: 11px; }
QComboBox::down-arrow:disabled { image: none; }
"""


def _ve_mui_ten():
    """Ve mui ten xuong cho o chon, tra ve duong dan file (rong neu that bai).

    Vi sao phai tu ve: luat 'QComboBox::drop-down' o tren dat 'border: none'.
    He dung vao drop-down bang stylesheet la Qt thoi ve mui ten mac dinh, nen ca
    9 o chon trong app deu tro thanh o trong tron - nhin nhu o go chu, khong ai
    biet la bam ra duoc danh sach. QSS chi nhan mui ten qua url() nen khong ve
    bang CSS thuan duoc (da thu meo tam giac bang vien trong suot: Qt ra hinh
    chu nhat dac).

    Ve luc chay chu khong de san mot file anh trong repo, vi T-Designer-Lite.spec
    chi dong goi thu muc 'core' - anh de trong 'ui' se mat khi dong goi.
    """
    try:
        import tempfile
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
        p = os.path.join(tempfile.gettempdir(), "tdesigner_mui_ten.png")
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        ve = QPainter(pm)
        ve.setRenderHint(QPainter.Antialiasing, True)
        but = QPen(QColor("#64748B"))
        but.setWidth(3)
        but.setCapStyle(Qt.RoundCap)
        but.setJoinStyle(Qt.RoundJoin)
        ve.setPen(but)
        ve.drawPolyline([QPoint(6, 9), QPoint(12, 16), QPoint(18, 9)])
        ve.end()
        if not pm.save(p):
            return ""
        return p.replace(chr(92), "/")     # QSS chi hieu dau gach cheo xuoi
    except Exception:
        return ""                          # khong ve duoc thi thoi, nhu cu


def main():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("Thieu PySide6. Cai bang lenh:  pip install PySide6")
        sys.exit(1)
    from ui.app import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _mt = _ve_mui_ten()
    app.setStyleSheet(APP_QSS + (QSS_MUI_TEN % _mt if _mt else ""))
    # Icon: chay tu source hoac tu ban dong goi (PyInstaller)
    try:
        from PySide6.QtGui import QIcon
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico = os.path.join(base, "icon.ico")
        if os.path.exists(ico):
            app.setWindowIcon(QIcon(ico))
    except Exception:
        pass
    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
