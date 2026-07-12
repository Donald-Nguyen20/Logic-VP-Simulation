# -*- coding: utf-8 -*-
"""
T-Designer Lite — diem khoi chay.
Chay:  python main.py
Yeu cau: Python 3.8+ va PySide6  (pip install PySide6)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("Thieu PySide6. Cai bang lenh:  pip install PySide6")
        sys.exit(1)
    from ui.app import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
