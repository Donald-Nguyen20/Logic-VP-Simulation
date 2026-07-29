# -*- coding: utf-8 -*-
"""Cua so THAM SO CAI DAT cua 1 khoi tren ban ve (thay cho 'Simulate block' cu).

Hien dung gia tri that dang cai trong khoi (bang CAD_BLOCK_PARAM cua file .db du an),
kem ten tham so (MSR, MFR, TRC, ULD, LLD...), kieu, mac dinh va gioi han theo loai khoi.
Nguoi dung SUA duoc; gia tri sua se duoc dung khi chay MO PHONG SHEET (nguong so sanh,
bang F(x), khoi tram...). Sua o day KHONG ghi vao file .db du an.
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.block_params import block_param_rows, block_pin_rows
import core.sheet_sim as SS


class BlockParamDialog(QDialog):
    """Bang tham so cai dat cua khoi - sua duoc, dung cho mo phong sheet.
    Kem bang CHAN VAO/RA hien tin hieu ngoai va GIA TRI dang nhan tu ben ngoai."""

    def __init__(self, db_path, bid, code, name="", parent=None, on_applied=None,
                 sim_values=None, sheet_id=None, dig_env=None, ana_env=None):
        super().__init__(parent)
        self.db_path = db_path
        self.bid = bid
        self.code = (code or "").upper()
        self.sheet_id = sheet_id
        self._sim_values = sim_values
        # dau vao nguoi dung da dat o mo phong sheet - can giu de tinh lai cho dung
        self._dig_env = dict(dig_env) if dig_env else {}
        self._ana_env = dict(ana_env) if ana_env else {}
        self._on_applied = on_applied
        self.setWindowTitle("Tham so cai dat: %s (%s)" % (name or "", self.code))
        self.resize(760, 560)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Gia tri dang cai trong khoi (doc tu file .db du an). Sua o cot 'Gia tri' roi "
            "bam 'Ap dung' - gia tri moi se duoc dung khi chay mo phong sheet.\n"
            "Luu y: khong ghi de vao file .db goc."))

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(
            ["So", "Ten", "Gia tri", "Kieu", "Mac dinh", "Gioi han"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                 | QAbstractItemView.EditTrigger.SelectedClicked
                                 | QAbstractItemView.EditTrigger.EditKeyPressed)
        lay.addWidget(self.tbl, 1)

        # --- bang CHAN VAO/RA + gia tri nhan tu ben ngoai ---
        lay.addWidget(QLabel(
            "Chan vao/ra cua khoi va GIA TRI dang nhan tu ben ngoai (theo mo phong sheet):"))
        self.tpin = QTableWidget(0, 5)
        self.tpin.setHorizontalHeaderLabels(
            ["Chan", "Ten chan", "Vao/Ra", "Tin hieu ngoai", "Gia tri"])
        self.tpin.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tpin.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tpin.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.tpin, 1)

        bar = QHBoxLayout()
        b_reset = QPushButton("Tra ve gia tri goc"); b_reset.clicked.connect(self._reset)
        bar.addWidget(b_reset)
        b_refresh = QPushButton("Cap nhat gia tri vao")
        b_refresh.clicked.connect(self._load_pins)
        bar.addWidget(b_refresh)
        bar.addStretch(1)
        b_apply = QPushButton("Ap dung (dung cho mo phong)")
        b_apply.clicked.connect(self._apply)
        bar.addWidget(b_apply)
        b_close = QPushButton("Dong"); b_close.clicked.connect(self.accept)
        bar.addWidget(b_close)
        lay.addLayout(bar)

        self._load()
        self._load_pins()

    # ---------- bang chan vao/ra ----------
    def _values(self):
        """{net: gia tri} THUC TE tren sheet: uu tien dung dung bo gia tri dang hien
        ngoai sheet; neu can tinh lai thi tinh voi DUNG dau vao nguoi dung da dat
        (neu khong se ra rong vi cac tin hieu vao chua xac dinh)."""
        if self._sim_values:
            return self._sim_values
        if self.db_path and self.sheet_id is not None:
            try:
                val, _it = SS.simulate(self.db_path, self.sheet_id,
                                       self._dig_env, self._ana_env)
                return val
            except Exception:
                return {}
        return {}

    def _load_pins(self):
        rows = block_pin_rows(self.db_path, self.bid, self.code)
        vals = self._values()
        self.tpin.setRowCount(len(rows))
        for i, r in enumerate(rows):
            v = vals.get(r["net"]) if r["net"] else None
            sig = r["net"] or ""
            if r["label"]:
                sig = ("%s  %s" % (sig, r["label"])).strip()
            cells = [str(r["no"]), r["name"], "vao" if r["side"] == "in" else "ra",
                     sig or "(chua noi)",
                     "" if v is None else ("%.6g" % v if isinstance(v, (int, float))
                                           and not isinstance(v, bool) else str(v))]
            for j, t in enumerate(cells):
                it = QTableWidgetItem(t)
                if j == 4 and t:
                    f = QFont(); f.setBold(True); it.setFont(f)
                    it.setForeground(QColor("#B45309"))
                if r["side"] == "out":
                    it.setBackground(QColor("#FEF3C7"))
                elif j == 4 and t:
                    it.setBackground(QColor("#EAF6FF"))
                self.tpin.setItem(i, j, it)

    # ---------- nap bang ----------
    def _load(self, use_original=False):
        rows = block_param_rows(self.db_path, self.bid, self.code)
        over = {} if use_original else SS.param_overrides().get(self.bid, {})
        self.tbl.setRowCount(len(rows))
        self._rows = rows
        for i, r in enumerate(rows):
            val = over.get(str(r["no"]), r["value"])
            it_no = QTableWidgetItem(str(r["no"]))
            it_nm = QTableWidgetItem(r["name"])
            it_v = QTableWidgetItem("" if val is None else str(val))
            it_k = QTableWidgetItem("chu" if r["kind"] == "1" else "so")
            it_d = QTableWidgetItem(str(r["default"]))
            lim = ""
            if r["min"] or r["max"]:
                lim = "%s .. %s" % (r["min"] or "-", r["max"] or "-")
            it_l = QTableWidgetItem(lim)
            for it in (it_no, it_nm, it_k, it_d, it_l):     # chi cot 'Gia tri' sua duoc
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if r["name"]:
                f = QFont(); f.setBold(True); it_nm.setFont(f)
            if str(val) != str(r["value"]):
                it_v.setBackground(QColor("#FEF3C7"))
            self.tbl.setItem(i, 0, it_no); self.tbl.setItem(i, 1, it_nm)
            self.tbl.setItem(i, 2, it_v); self.tbl.setItem(i, 3, it_k)
            self.tbl.setItem(i, 4, it_d); self.tbl.setItem(i, 5, it_l)

    # ---------- ap dung / tra ve goc ----------
    def _apply(self):
        changed = {}
        for i, r in enumerate(self._rows):
            new = self.tbl.item(i, 2).text().strip()
            if r["kind"] == "0" and new:              # kiem tra tham so KIEU SO
                try:
                    v = float(new)
                except ValueError:
                    QMessageBox.warning(self, "Gia tri khong hop le",
                        "Tham so P%s (%s) phai la so: %r" % (r["no"], r["name"] or "-", new))
                    return
                for key, cmp_ in (("min", lambda a, b: a < b), ("max", lambda a, b: a > b)):
                    lim = r.get(key)
                    try:
                        if lim not in ("", None) and cmp_(v, float(lim)):
                            QMessageBox.warning(self, "Ngoai gioi han",
                                "Tham so P%s (%s) = %s vuot gioi han %s = %s."
                                % (r["no"], r["name"] or "-", new, key, lim))
                            return
                    except ValueError:
                        pass
            if new != str(r["value"]):
                changed[str(r["no"])] = new
        SS.set_param_override(self.bid, changed)
        self._load()
        self._sim_values = None      # tinh lai theo tham so moi
        self._load_pins()
        if self._on_applied:
            self._on_applied()
        QMessageBox.information(self, "Da ap dung",
            "Da ap dung %d tham so sua doi cho khoi. Chay lai mo phong sheet de thay ket qua."
            % len(changed) if changed else
            "Khong co tham so nao khac gia tri goc (da bo moi ghi de).")

    def _reset(self):
        SS.set_param_override(self.bid, None)
        self._load(use_original=True)
        if self._on_applied:
            self._on_applied()
