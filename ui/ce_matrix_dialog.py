# -*- coding: utf-8 -*-
"""Cua so 'Ma tran nhan qua' (Cause & Effect Matrix): chon nhieu tin hieu DICH (vd MFT,
ETS, RUNBACK), tim TAT CA nguyen nhan GOC dan toi tung tin hieu (uu tien nhan da lam
tai lieu san trong CAD_TAG_FID, khong co thi suy luan tu day qua core/ce_matrix.py),
gom thanh 1 bang: hang = nguyen nhan, cot = tin hieu dich, o = OR (mot minh du) hay
AND (can du ca nhom). Click 1 hang -> nhay toi sheet nguon. Co nut xuat Excel."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit,
                               QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                               QMessageBox, QHeaderView, QScrollArea,
                               QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core import ce_matrix as CE
from core import project_index as PI


class CEMatrixDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.setWindowTitle("Ma tran nhan qua (Cause & Effect Matrix)")
        self.resize(880, 560)
        self.targets = []     # [{'db','sheet','net','disp'}]
        self.columns = []
        self.rows = []

        lay = QVBoxLayout(self)

        # --- hang chon tin hieu dich ---
        top = QHBoxLayout()
        top.addWidget(QLabel("Tin hieu dich:"))
        self.chip_area = QHBoxLayout()
        self.chip_area.setSpacing(6)
        chip_wrap = QWidget()
        chip_wrap.setLayout(self.chip_area)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedHeight(40)
        scroll.setWidget(chip_wrap)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        top.addWidget(scroll, 1)
        lay.addLayout(top)

        add_row = QHBoxLayout()
        self.ed = QLineEdit(); self.ed.setPlaceholderText("Go ten tin hieu (vd MFT) roi Enter...")
        btn_add = QPushButton("+ Them")
        btn_rb = QPushButton("Dung lai chi muc")
        btn_rb.setToolTip("Dung lai chi muc tim kiem tu dau (dung khi tim khong ra tin hieu dung ra)")
        btn_build = QPushButton("Dung ma tran")
        btn_export = QPushButton("Xuat Excel...")
        add_row.addWidget(self.ed, 1)
        add_row.addWidget(btn_add)
        add_row.addWidget(btn_rb)
        add_row.addWidget(btn_build)
        add_row.addWidget(btn_export)
        lay.addLayout(add_row)

        self.info = QLabel("")
        self.info.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(self.info)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self._on_row_click)
        lay.addWidget(self.table, 1)

        legend = QLabel("● = nguyen nhan doc lap, mot minh du gay hieu ung (chi hien OR, cac "
                        "nguyen nhan phai ket hop voi cai khac (AND) da duoc an bot)   |   "
                        "Bam 1 hang de nhay toi sheet nguon")
        legend.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(legend)

        btn_add.clicked.connect(lambda: self._add_target(False))
        self.ed.returnPressed.connect(lambda: self._add_target(False))
        btn_rb.clicked.connect(self._rebuild_index)
        btn_build.clicked.connect(self._rebuild)
        btn_export.clicked.connect(self._export_excel)

    # ---------------------------------------------------------------- chips
    def _refresh_chips(self):
        while self.chip_area.count():
            it = self.chip_area.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, tg in enumerate(self.targets):
            w = QWidget()
            hl = QHBoxLayout(w); hl.setContentsMargins(6, 2, 6, 2); hl.setSpacing(4)
            w.setStyleSheet("background:#DBEAFE; border-radius:10px;")
            lb = QLabel(tg["disp"]); lb.setStyleSheet("color:#1D4ED8; font-size:12px;")
            x = QPushButton("✕"); x.setFixedSize(16, 16)
            x.setStyleSheet("border:none; color:#1D4ED8; font-size:10px;")
            x.clicked.connect(lambda _=False, idx=i: self._remove_target(idx))
            hl.addWidget(lb); hl.addWidget(x)
            self.chip_area.addWidget(w)
        self.chip_area.addStretch(1)

    def _remove_target(self, idx):
        if 0 <= idx < len(self.targets):
            self.targets.pop(idx)
            self._refresh_chips()
            self._rebuild()

    # ---------------------------------------------------------------- them tin hieu
    def _db_paths(self):
        return list(getattr(self.mw, "meta_by_path", {}).keys())

    def _rebuild_index(self):
        paths = self._db_paths()
        if not paths:
            self.info.setText("Chua import DB nao.")
            return
        try:
            PI.build(paths)
            self.info.setText("Da dung lai chi muc tu %d file DB. Thu them tin hieu lai." % len(paths))
        except Exception as e:
            self.info.setText("Loi khi dung lai chi muc: %s" % e)

    def _add_target(self, force_rebuild=False):
        name = self.ed.text().strip()
        if not name:
            return
        paths = self._db_paths()
        if not paths:
            self.info.setText("Chua import DB nao.")
            return
        try:
            if force_rebuild:
                PI.build(paths)
            else:
                PI.ensure(paths)
        except Exception:
            pass
        cands = CE.resolve_target_candidates(name, paths)
        if not cands:
            # phan biet: ten khong ton tai o dau, vs co ton tai nhung chi la THAM CHIEU
            # (khong sheet nao THUC SU sinh ra no) - de nguoi dung biet huong xu ly dung
            any_ref = bool(PI.find(name, limit=5))
            if any_ref:
                self.info.setText(
                    "Tim thay ten '%s' nhung KHONG co sheet nao thuc su SAN XUAT ra no trong "
                    "%d DB da import (chi la tham chieu/dau vao o noi khac). Co the tin hieu nay "
                    "duoc sinh ra o 1 DB/CPU chua import - thu Import them DB lien quan." % (name, len(paths)))
            else:
                self.info.setText(
                    "Khong tim thay ten '%s' trong %d DB da import. Kiem tra dung chinh ta, hoac bam "
                    "'Dung lai chi muc' neu ban vua import DB moi." % (name, len(paths)))
            return
        # Khong hoi chon 1 noi nua - gop nguyen nhan tu TAT CA noi (db/sheet) cung
        # san xuat ra ten tin hieu nay (vd 2 CPU du phong A/B cung dung ten).
        disp = name.upper()
        if any(t["disp"] == disp for t in self.targets):
            self.info.setText("'%s' da co trong ma tran." % disp)
            return
        self.targets.append({"disp": disp, "cands": cands})
        self.ed.clear()
        if len(cands) > 1:
            self.info.setText("Da them '%s' (gop nguyen nhan tu %d noi cung san xuat tin hieu nay). "
                              "Bam 'Dung ma tran' de tinh lai." % (disp, len(cands)))
        else:
            self.info.setText("Da them '%s'. Bam 'Dung ma tran' de tinh lai." % disp)
        self._refresh_chips()
        self._rebuild()

    # ---------------------------------------------------------------- dung ma tran
    def _rebuild(self):
        if not self.targets:
            self.table.setRowCount(0); self.table.setColumnCount(0)
            self.rows = []; self.columns = []
            return
        cpu_paths = getattr(self.mw, "cpu_paths", None) or {}
        try:
            self.columns, self.rows = CE.build_matrix(self.targets, cpu_paths=cpu_paths)
        except Exception as e:
            self.info.setText("Loi khi dung ma tran: %s" % e)
            return
        self._render_table()
        n_tag = sum(1 for r in self.rows if r.get("source") == "tag")
        self.info.setText("%d nguyen nhan (%d tu nhan CAD_TAG_FID co san, %d suy luan tu day)."
                          % (len(self.rows), n_tag, len(self.rows) - n_tag))

    def _render_table(self):
        cols = ["Nguyen nhan goc", "Nguon"] + self.columns
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            it = QTableWidgetItem(row["label"])
            it.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(r, 0, it)
            src = "Tai lieu (TAG)" if row.get("source") == "tag" else "Suy luan tu day"
            self.table.setItem(r, 1, QTableWidgetItem(src))
            for ci, col in enumerate(self.columns):
                m = row["marks"].get(col)
                cell = QTableWidgetItem("")
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if m:
                    if m["kind"] == "or":
                        cell.setText("●")
                        cell.setForeground(QColor("#1D4ED8"))
                    else:
                        cell.setText("▲%s" % m.get("group", ""))
                        cell.setForeground(QColor("#B45309"))
                        with_txt = ", ".join(m.get("with") or [])
                        cell.setToolTip("Can du ca nhom:\n%s" % with_txt if with_txt else "Nhom AND")
                    f = cell.font(); f.setBold(True); cell.setFont(f)
                self.table.setItem(r, ci + 2, cell)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for ci in range(1, len(cols)):
            self.table.horizontalHeader().setSectionResizeMode(ci, QHeaderView.ResizeMode.ResizeToContents)

    # ---------------------------------------------------------------- dieu huong
    def _on_row_click(self, r, _c):
        it = self.table.item(r, 0)
        if not it:
            return
        row = it.data(Qt.ItemDataRole.UserRole)
        if not row or not row.get("db") or row.get("sheet") is None:
            self.info.setText("Nguyen nhan nay chua ro sheet nguon (tin hieu ben ngoai / chua dinh vi duoc).")
            return
        self.mw._open_cross(row["db"], row["sheet"])
        self.raise_()

    # ---------------------------------------------------------------- xuat Excel
    def _export_excel(self):
        if not self.rows:
            QMessageBox.information(self, "Xuat Excel", "Chua co du lieu de xuat - them tin hieu dich truoc.")
            return
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Xuat ma tran nhan qua", "CE_Matrix.xlsx",
                                              "Excel (*.xlsx)")
        if not path:
            return
        try:
            from core import ce_export as CX
            CX.export_matrix(path, self.columns, self.rows)
        except Exception as e:
            QMessageBox.warning(self, "Xuat Excel", "Loi khi xuat: %s" % e)
            return
        self.info.setText("Da xuat: %s" % path)
