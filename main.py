# -*- coding: utf-8 -*-
"""
T-Designer Lite - diem khoi chay.
Chay:  python main.py
Yeu cau: Python 3.8+ va PySide6  (pip install PySide6)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Bo mau hien dai (light + accent indigo) ---
APP_QSS = """
* { font-family: 'Segoe UI', Arial; font-size: 13px; }
QMainWindow, QWidget { background: #EEF1F6; color: #23303F; }

QToolBar { background: #FFFFFF; border: none; border-bottom: 1px solid #D7DEE8;
           padding: 5px; spacing: 3px; }
QToolBar QToolButton { background: transparent; color: #2B3A55;
           padding: 6px 12px; border-radius: 7px; font-weight: 600; }
QToolBar QToolButton:hover { background: #E8EEFB; color: #2B54B8; }
QToolBar QToolButton:pressed, QToolBar QToolButton:checked { background: #3B6FE0; color: #FFFFFF; }
QToolBar::separator { background: #D7DEE8; width: 1px; margin: 5px 6px; }

QDockWidget { color: #23303F; }
QDockWidget::title { background: #E4EAF3; padding: 7px 12px; font-weight: 700;
           color: #2B3A55; border-bottom: 1px solid #D7DEE8; }

QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit {
           background: #FFFFFF; border: 1px solid #D7DEE8; border-radius: 8px; }
QTreeWidget::item, QListWidget::item { padding: 4px 3px; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #F2F6FE; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #E1EAFB; color: #2B54B8; }
QHeaderView::section { background: #E4EAF3; border: none; padding: 4px; }

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
           background: #FFFFFF; border: 1px solid #CBD5E3; border-radius: 7px;
           padding: 5px 9px; selection-background-color: #3B6FE0; selection-color: #FFFFFF; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #3B6FE0; }
QComboBox::drop-down { border: none; width: 20px; }

QPushButton { background: #3B6FE0; color: #FFFFFF; border: none; border-radius: 7px;
           padding: 7px 16px; font-weight: 600; }
QPushButton:hover { background: #2B54B8; }
QPushButton:pressed { background: #21449C; }
QPushButton:disabled { background: #C3CCDB; color: #EEF1F6; }

QGroupBox { border: 1px solid #D7DEE8; border-radius: 10px; margin-top: 12px; background: #FFFFFF; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px;
           color: #2B54B8; font-weight: 700; }
QCheckBox { spacing: 7px; }

QMenu { background: #FFFFFF; border: 1px solid #D7DEE8; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 5px; }
QMenu::item:selected { background: #E1EAFB; color: #2B54B8; }
QMenu::item:disabled { color: #A9B4C4; }

QStatusBar { background: #E4EAF3; color: #4A5A70; border-top: 1px solid #D7DEE8; }
QGraphicsView { background: #FCFDFF; border: none; }
QDialog { background: #EEF1F6; }
QLabel { background: transparent; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: #C3CCDB; border-radius: 5px; min-height: 26px; }
QScrollBar::handle:vertical:hover { background: #9AA8BE; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: #C3CCDB; border-radius: 5px; min-width: 26px; }
QScrollBar::handle:horizontal:hover { background: #9AA8BE; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: #2B3A55; color: #FFFFFF; border: none; padding: 5px 9px; border-radius: 5px; }
"""


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


if __name__ == "__main__":
    main()
