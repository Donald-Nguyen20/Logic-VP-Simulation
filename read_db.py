# -*- coding: utf-8 -*-
"""
read_db.py - Cong cu doc & xem cau truc file .db (SQLite) DOC LAP, khong dung chung
bat ky module nao cua T_Designer_Lite (chi de kiem tra/kham pha cau truc DB).

Chuc nang:
  - Mo NHIEU file .db cung luc (chon nhieu file trong hop thoai).
  - Cay ben trai: tung file DB -> danh sach bang (kem so dong).
  - Bam vao 1 bang: xem schema (ten cot, kieu du lieu) + du lieu preview (toi da
    2000 dong dau, co the doi trong SPINBOX so dong preview).
  - Xuat Excel:
      + Xuat RIENG bang dang xem ra 1 file .xlsx.
      + Xuat TAT CA bang cua TAT CA file DB dang mo ra 1 file .xlsx (moi bang = 1
        sheet, ten sheet dat theo "<ten_db>_<ten_bang>").

Chay:  python read_db.py
Yeu cau thu vien: PySide6, openpyxl
"""
from __future__ import annotations
import sys
import os
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QFileDialog, QMessageBox, QStatusBar, QSpinBox, QMenu,
    QAbstractItemView, QHeaderView, QLineEdit, QDialog, QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction


def _decode(b):
    """text_factory an toan: khong bao gio crash du bytes co loi encoding."""
    if isinstance(b, bytes):
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("utf-8", errors="replace")
    return b


def _safe_sheet_name(name, used=None):
    """Ten sheet Excel: bo ky tu cam, gioi han 31 ky tu, khong trung nhau."""
    bad = set('[]:*?/\\')
    name = "".join(ch for ch in str(name) if ch not in bad).strip() or "Sheet"
    name = name[:31]
    if used is not None:
        base, i = name, 1
        while name in used:
            suf = "_%d" % i
            name = (base[: 31 - len(suf)] + suf) if len(base) + len(suf) > 31 else base + suf
            i += 1
        used.add(name)
    return name


class DBReaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("read_db - Xem cau truc file .db")
        self.dbs = {}          # {path: sqlite3.Connection}
        self.cur_path = None
        self.cur_table = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- thanh nut tren cung ----
        bar = QHBoxLayout()
        b_open = QPushButton("Mo file .db...")
        b_open.clicked.connect(self.open_dbs)
        b_close_all = QPushButton("Dong tat ca")
        b_close_all.clicked.connect(self.close_all)
        b_export_cur = QPushButton("Xuat bang dang xem -> Excel...")
        b_export_cur.clicked.connect(self.export_current)
        b_export_all = QPushButton("Xuat TAT CA bang -> Excel...")
        b_export_all.clicked.connect(self.export_all)
        bar.addWidget(b_open)
        bar.addWidget(b_close_all)
        bar.addStretch(1)
        bar.addWidget(QLabel("So dong preview:"))
        self.sp_limit = QSpinBox()
        self.sp_limit.setRange(10, 200000)
        self.sp_limit.setValue(2000)
        self.sp_limit.setSingleStep(500)
        self.sp_limit.valueChanged.connect(self._reload_current)
        bar.addWidget(self.sp_limit)
        bar.addWidget(b_export_cur)
        bar.addWidget(b_export_all)
        root.addLayout(bar)

        # ---- thanh tim kiem ----
        sbar = QHBoxLayout()
        sbar.addWidget(QLabel("Loc trong bang dang xem:"))
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("Go de loc ngay cac dong dang hien (khong phan biet hoa/thuong)...")
        self.ed_filter.textChanged.connect(self._apply_filter)
        sbar.addWidget(self.ed_filter, 1)
        b_search_all = QPushButton("Tim trong TAT CA bang...")
        b_search_all.clicked.connect(self.search_all_dialog)
        sbar.addWidget(b_search_all)
        root.addLayout(sbar)

        # ---- splitter: cay trai + bang phai ----
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File DB / Bang"])
        self.tree.itemClicked.connect(self._on_tree_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        split.addWidget(self.tree)

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        self.lbl_schema = QLabel("(chua chon bang nao)")
        self.lbl_schema.setWordWrap(True)
        self.lbl_schema.setStyleSheet("padding:4px; color:#334155;")
        rlay.addWidget(self.lbl_schema)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        rlay.addWidget(self.table, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([320, 900])

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._build_menu()

    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        a1 = QAction("Mo file .db...", self); a1.triggered.connect(self.open_dbs)
        a2 = QAction("Dong tat ca", self); a2.triggered.connect(self.close_all)
        a3 = QAction("Thoat", self); a3.triggered.connect(self.close)
        m.addAction(a1); m.addAction(a2); m.addSeparator(); m.addAction(a3)
        me = self.menuBar().addMenu("&Export")
        a4 = QAction("Xuat bang dang xem -> Excel...", self); a4.triggered.connect(self.export_current)
        a5 = QAction("Xuat TAT CA bang -> Excel...", self); a5.triggered.connect(self.export_all)
        me.addAction(a4); me.addAction(a5)

    # ------------------------------------------------------------------ mo DB
    def open_dbs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chon 1 hoac nhieu file .db", "", "SQLite DB (*.db);;Tat ca file (*)")
        for p in paths:
            self._load_db(p)

    def _load_db(self, path):
        if path in self.dbs:
            self.status.showMessage("Da mo san: " + path, 4000)
            return
        try:
            con = sqlite3.connect(path)
            con.text_factory = _decode
            cur = con.cursor()
            tables = [r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        except Exception as e:
            QMessageBox.warning(self, "Loi mo file", "%s\n%s" % (path, e))
            return
        self.dbs[path] = con
        item = QTreeWidgetItem([os.path.basename(path)])
        item.setToolTip(0, path)
        item.setData(0, Qt.UserRole, {"kind": "db", "path": path})
        for t in tables:
            try:
                n = cur.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            except Exception:
                n = "?"
            child = QTreeWidgetItem(["%s  (%s dong)" % (t, n)])
            child.setData(0, Qt.UserRole, {"kind": "table", "path": path, "table": t})
            item.addChild(child)
        self.tree.addTopLevelItem(item)
        item.setExpanded(True)
        self.status.showMessage("Da mo: %s (%d bang)" % (path, len(tables)), 4000)

    def close_all(self):
        for con in self.dbs.values():
            try:
                con.close()
            except Exception:
                pass
        self.dbs.clear()
        self.tree.clear()
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.lbl_schema.setText("(chua chon bang nao)")
        self.cur_path = self.cur_table = None

    def _tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("kind") != "db":
            return
        menu = QMenu(self)
        act = menu.addAction("Dong file nay")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == act:
            path = data["path"]
            try:
                self.dbs.pop(path).close()
            except Exception:
                pass
            idx = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(idx)
            if self.cur_path == path:
                self.cur_path = self.cur_table = None

    # ------------------------------------------------------------- xem bang
    def _on_tree_click(self, item, _col):
        data = item.data(0, Qt.UserRole)
        if not data or data.get("kind") != "table":
            return
        self._show_table(data["path"], data["table"])

    def _reload_current(self):
        if self.cur_path and self.cur_table:
            self._show_table(self.cur_path, self.cur_table)

    def _apply_filter(self, text):
        """Loc nhanh tren du lieu DA HIEN trong bang (khong truy van lai DB)."""
        text = (text or "").strip().lower()
        n_rows = self.table.rowCount()
        n_cols = self.table.columnCount()
        shown = 0
        for r in range(n_rows):
            match = not text
            if not match:
                for c in range(n_cols):
                    item = self.table.item(r, c)
                    if item and text in item.text().lower():
                        match = True
                        break
            self.table.setRowHidden(r, not match)
            shown += 1 if match else 0
        if text:
            self.status.showMessage("Loc '%s': %d / %d dong khop" % (text, shown, n_rows))

    def _show_table(self, path, table):
        con = self.dbs.get(path)
        if con is None:
            return
        cur = con.cursor()
        try:
            cols = cur.execute('PRAGMA table_info("%s")' % table).fetchall()
        except Exception as e:
            QMessageBox.warning(self, "Loi doc schema", str(e))
            return
        # cols: (cid, name, type, notnull, dflt_value, pk)
        schema_parts = []
        for c in cols:
            piece = c[1] + (" %s" % c[2] if c[2] else "")
            if c[5]:
                piece += " [PK]"
            schema_parts.append(piece)
        total = cur.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        self.lbl_schema.setText(
            "Bang: %s  |  %d cot, %d dong\nSchema: %s" %
            (table, len(cols), total, ", ".join(schema_parts)))

        colnames = [c[1] for c in cols]
        limit = self.sp_limit.value()
        rows = cur.execute('SELECT * FROM "%s" LIMIT ?' % table, (limit,)).fetchall()

        self.table.clear()
        self.table.setColumnCount(len(colnames))
        self.table.setHorizontalHeaderLabels(colnames)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()

        self.cur_path, self.cur_table = path, table
        self.status.showMessage(
            "%s :: %s -> hien %d / %d dong" % (os.path.basename(path), table, len(rows), total))

    # ------------------------------------------------------- tim trong tat ca bang
    def _scan_all(self, term, per_table_limit=50, total_limit=1000):
        """Tim 'term' (LIKE, khong phan biet hoa/thuong) tren MOI cot cua MOI bang
        cua TAT CA DB dang mo. Tra ve [(db_path, table, colname, rowid_or_None, row_text)]."""
        results = []
        like = "%" + term + "%"
        for path, con in self.dbs.items():
            cur = con.cursor()
            try:
                tables = [r[0] for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            except Exception:
                continue
            for t in tables:
                if len(results) >= total_limit:
                    return results
                try:
                    cols = [c[1] for c in cur.execute('PRAGMA table_info("%s")' % t).fetchall()]
                    if not cols:
                        continue
                    where = " OR ".join('CAST("%s" AS TEXT) LIKE ?' % c for c in cols)
                    q = 'SELECT %s FROM "%s" WHERE %s LIMIT ?' % (
                        ", ".join('"%s"' % c for c in cols), t, where)
                    params = [like] * len(cols) + [per_table_limit]
                    rows = cur.execute(q, params).fetchall()
                except Exception:
                    continue
                for row in rows:
                    matched_cols = [cols[i] for i, v in enumerate(row)
                                    if v is not None and term.lower() in str(v).lower()]
                    row_text = " | ".join("%s=%s" % (c, v) for c, v in zip(cols, row))
                    results.append((path, t, ", ".join(matched_cols) or "?", row_text))
                    if len(results) >= total_limit:
                        return results
        return results

    def search_all_dialog(self):
        if not self.dbs:
            QMessageBox.information(self, "Tim kiem", "Chua mo file .db nao.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Tim trong tat ca bang")
        dlg.resize(900, 560)
        lay = QVBoxLayout(dlg)

        row0 = QHBoxLayout()
        row0.addWidget(QLabel("Tu khoa:"))
        ed = QLineEdit()
        ed.setPlaceholderText("Go tu khoa roi bam Tim hoac Enter...")
        row0.addWidget(ed, 1)
        b_go = QPushButton("Tim")
        row0.addWidget(b_go)
        lay.addLayout(row0)

        lbl = QLabel("")
        lay.addWidget(lbl)

        res_table = QTableWidget()
        res_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        res_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        res_table.setColumnCount(4)
        res_table.setHorizontalHeaderLabels(["File DB", "Bang", "Cot khop", "Noi dung dong"])
        res_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        lay.addWidget(res_table, 1)

        hint = QLabel("Bam dup vao 1 dong ket qua de mo bang do trong man hinh chinh.")
        hint.setStyleSheet("color:#64748b;")
        lay.addWidget(hint)

        b_close = QPushButton("Dong")
        row1 = QHBoxLayout()
        row1.addStretch(1)
        row1.addWidget(b_close)
        lay.addLayout(row1)

        state = {"rows": []}

        def do_search():
            term = ed.text().strip()
            if not term:
                return
            res_table.setRowCount(0)
            results = self._scan_all(term, per_table_limit=50, total_limit=1000)
            state["rows"] = results
            res_table.setRowCount(len(results))
            for r, (path, table, cols, row_text) in enumerate(results):
                res_table.setItem(r, 0, QTableWidgetItem(os.path.basename(path)))
                res_table.setItem(r, 1, QTableWidgetItem(table))
                res_table.setItem(r, 2, QTableWidgetItem(cols))
                res_table.setItem(r, 3, QTableWidgetItem(row_text))
            res_table.resizeColumnsToContents()
            lbl.setText("Tim thay %d dong khop (moi bang toi da 50, tong toi da 1000)." % len(results))

        def open_hit(r, _c=0):
            rows = state["rows"]
            if not (0 <= r < len(rows)):
                return
            path, table, _cols, _txt = rows[r]
            self._show_table(path, table)
            self.ed_filter.setText(ed.text().strip())
            dlg.accept()

        b_go.clicked.connect(do_search)
        ed.returnPressed.connect(do_search)
        res_table.cellDoubleClicked.connect(open_hit)
        b_close.clicked.connect(dlg.reject)

        dlg.exec()

    # ------------------------------------------------------------- xuat Excel
    def export_current(self):
        if not self.cur_table:
            QMessageBox.information(self, "Xuat Excel", "Chua chon bang nao de xuat.")
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Luu Excel", self.cur_table + ".xlsx", "Excel (*.xlsx)")
        if not out:
            return
        try:
            self._export_tables_to_xlsx(out, [(self.cur_path, self.cur_table)])
            QMessageBox.information(self, "Xuat Excel", "Da xuat xong:\n" + out)
        except Exception as e:
            QMessageBox.warning(self, "Loi xuat Excel", str(e))

    def export_all(self):
        if not self.dbs:
            QMessageBox.information(self, "Xuat Excel", "Chua mo file .db nao.")
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Luu Excel (tat ca bang)", "all_tables.xlsx", "Excel (*.xlsx)")
        if not out:
            return
        pairs = []
        for path, con in self.dbs.items():
            cur = con.cursor()
            tables = [r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            for t in tables:
                pairs.append((path, t))
        try:
            self._export_tables_to_xlsx(out, pairs)
            QMessageBox.information(self, "Xuat Excel", "Da xuat xong %d bang:\n%s" % (len(pairs), out))
        except Exception as e:
            QMessageBox.warning(self, "Loi xuat Excel", str(e))

    def _export_tables_to_xlsx(self, out_path, pairs):
        """pairs = [(db_path, table_name), ...] -> 1 file .xlsx, moi bang 1 sheet."""
        import openpyxl
        wb = openpyxl.Workbook(write_only=True)
        used_names = set()
        for path, table in pairs:
            con = self.dbs[path]
            cur = con.cursor()
            dbname = os.path.splitext(os.path.basename(path))[0]
            sheet_name = _safe_sheet_name("%s_%s" % (dbname, table), used_names)
            ws = wb.create_sheet(title=sheet_name)
            cols = [c[1] for c in cur.execute('PRAGMA table_info("%s")' % table).fetchall()]
            ws.append(cols)
            for row in cur.execute('SELECT * FROM "%s"' % table):
                ws.append(["" if v is None else v for v in row])
        wb.save(out_path)


def main():
    app = QApplication(sys.argv)
    win = DBReaderWindow()
    win.resize(1300, 750)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
