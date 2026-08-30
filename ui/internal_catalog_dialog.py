# -*- coding: utf-8 -*-
"""Danh muc LOGIC NOI - mo tu thanh cong cu, khong phai di tim dung mot khoi tren sheet.

Truoc day chi vao duoc bang chuot phai len 1 khoi, nghia la muon xem mo hinh cua ma nao
thi phai biet truoc ma do nam o trang nao ma mo len. Nguoc doi: nguoi ta bat dau tu cau
hoi "ma nao chua co mo hinh" chu khong tu mot khoi cu the.

Hai tab, vi day la HAI TRUC KHAC NHAU - gop chung se roi:
  Khoi chuc nang: mot mo hinh dung chung cho MOI thuc the cua ma do. Ve 1 lan an ca du an.
  F(x)          : moi khoi mot bang gay khuc RIENG. 4.290 khoi, deu chung ma 4035.

Cot trang thai cua tab 1 chinh la BANG VIEC CAN LAM: do tren 21 DB cua du an co 132 ma /
28.206 khoi chua co mo hinh mo phong, trong do 31 ma / 9.742 khoi da co san hinh so do noi
bo trong manual - tuc la ve theo hinh co san la chay duoc ngay.
"""
from __future__ import annotations
import collections
import json
import os
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")

# Terminal (dau noi day), khong phai khoi tinh toan - de lan vao danh sach thi no chiem
# hon nua tong so khoi (23.331/44.087 rieng 01 UCS.db) va lam moi ty le tro nen vo nghia.
_MA_TERMINAL = "E0B1"


def _doc_json(ten):
    try:
        with open(os.path.join(_CORE, ten), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Thieu file du lieu chi lam mat mot COT trang thai, khong duoc lam chet danh muc.
        return {}


def _sem_codes():
    """Ma khoi ma bo mo phong sheet tinh duoc (gop analog_sem + logic_sem)."""
    ra = set()
    for f in ("analog_sem.json", "logic_sem.json"):
        for k in _doc_json(f):
            ra.add(str(k).upper())
    return ra


def _ten_theo_ma():
    """macrocode -> ten ngan de hien trong bang.

    Uu tien macro_manual.json (ten chuan cua hang, vd 'MOV3-SH'), thieu thi lay abbr
    trong macro_pins.json - file nay danh khoa theo KY HIEU nen phai lat nguoc lai."""
    ra = {}
    for k, v in (_doc_json("macro_manual.json").get("by_code") or {}).items():
        nm = (v or {}).get("name") or (v or {}).get("desc") or ""
        if nm:
            ra[str(k).upper()] = nm.strip()
    for v in _doc_json("macro_pins.json").values():
        code = str((v or {}).get("macrocode") or "").upper()
        if code and code not in ra:
            nm = (v or {}).get("abbr") or (v or {}).get("name") or ""
            if nm:
                ra[code] = str(nm).strip()
    return ra


def _dem_khoi(db_paths):
    """macrocode -> so khoi, cong don qua tat ca DB. Do that: 21 DB het 0,29 s nen tinh
    thang luc mo, khong can cache (cache la them mot thu co the sai lech voi DB)."""
    cnt = collections.Counter()
    loi = 0
    for p in db_paths:
        try:
            con = sqlite3.connect("file:%s?mode=ro" % str(p).replace("\\", "/"), uri=True)
            for code, n in con.execute(
                    "SELECT MACROCODE, COUNT(*) FROM CAD_BLOCK GROUP BY MACROCODE"):
                if code:
                    cnt[str(code).strip().upper()] += n
            con.close()
        except Exception:
            loi += 1          # DB rong / khong dung so do -> bo qua, dem tiep cac DB khac
    return cnt, loi


def _db_trong_index():
    """Duong dan DB ghi trong chi muc du an. Dung khi danh sach DB dang mo bi rong -
    chi muc van con nguyen nen danh muc khong viec gi phai trong theo."""
    try:
        from core import project_index as PI
        p = PI.index_path()
        if not os.path.exists(p):
            return []
        con = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
        ra = [r[0] for r in con.execute("SELECT DISTINCT db FROM muc") if r[0]]
        con.close()
        return [d for d in ra if os.path.exists(d)]
    except Exception:
        return []


def _so(v):
    """O bang sap xep theo SO chu khong theo chuoi ('9' phai nho hon '10')."""
    it = QTableWidgetItem()
    it.setData(Qt.ItemDataRole.DisplayRole, int(v))
    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return it


def _o(txt, giua=False):
    it = QTableWidgetItem(str(txt))
    if giua:
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return it


class InternalCatalogDialog(QDialog):
    """Danh muc khoi chuc nang + F(x) cua ca du an."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.setWindowTitle("Internal logic - danh muc khoi chuc nang va F(x)")
        self.resize(1100, 700)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self._tab_khoi()
        self._tab_fx()
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        self._nap_khoi()

    # ---------------- tab 1: khoi chuc nang ----------------
    def _tab_khoi(self):
        w = QWidget()
        v = QVBoxLayout(w)
        bar = QHBoxLayout()
        self.ed_k = QLineEdit()
        self.ed_k.setPlaceholderText("Loc theo ma hoac ten khoi...")
        self.ed_k.textChanged.connect(self._loc_khoi)
        bar.addWidget(self.ed_k, 1)
        self.cb_chua = QCheckBox("Chi hien ma CHUA co mo hinh")
        self.cb_chua.toggled.connect(self._loc_khoi)
        bar.addWidget(self.cb_chua)
        self.cb_hinh = QCheckBox("Chi hien ma co hinh manual")
        self.cb_hinh.toggled.connect(self._loc_khoi)
        bar.addWidget(self.cb_hinh)
        v.addLayout(bar)

        self.tb_k = QTableWidget(0, 6)
        self.tb_k.setHorizontalHeaderLabels(
            ["Ma", "Ten khoi", "So khoi", "Hinh manual", "Mo phong", "Ban ve"])
        self.tb_k.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tb_k.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tb_k.setSortingEnabled(True)
        self.tb_k.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tb_k.itemDoubleClicked.connect(lambda *_: self._ve())
        v.addWidget(self.tb_k, 1)

        h = QHBoxLayout()
        b1 = QPushButton("Ve / sua logic noi")
        b1.clicked.connect(self._ve)
        h.addWidget(b1)
        b2 = QPushButton("Xem hinh so do noi bo (manual)")
        b2.clicked.connect(self._xem_hinh)
        h.addWidget(b2)
        h.addStretch(1)
        b3 = QPushButton("Quet lai")
        b3.clicked.connect(self._nap_khoi)
        h.addWidget(b3)
        v.addLayout(h)
        self.tabs.addTab(w, "Khoi chuc nang")

    def _db_dang_dung(self):
        """DB de quet: uu tien danh sach dang mo trong app, rong thi lui ve chi muc."""
        ds = list(getattr(self.main, "db_nodes", {}) or {})
        return (ds, "dang mo") if ds else (_db_trong_index(), "chi muc")

    def _nap_khoi(self):
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dbs, nguon = self._db_dang_dung()
            cnt, loi = _dem_khoi(dbs)
            cnt.pop(_MA_TERMINAL, None)
            ten = _ten_theo_ma()
            sem = _sem_codes()
            hinh = {str(k).upper() for k in _doc_json("macro_internal.json")}
            ve = set()
            d_ve = os.path.join(_CORE, "internal_design")
            if os.path.isdir(d_ve):
                ve = {f[:-5].upper() for f in os.listdir(d_ve) if f.lower().endswith(".json")}

            self.tb_k.setSortingEnabled(False)
            self.tb_k.setRowCount(0)
            for code, n in cnt.most_common():
                r = self.tb_k.rowCount()
                self.tb_k.insertRow(r)
                self.tb_k.setItem(r, 0, _o(code))
                self.tb_k.setItem(r, 1, _o(ten.get(code, "")))
                self.tb_k.setItem(r, 2, _so(n))
                self.tb_k.setItem(r, 3, _o("co" if code in hinh else "", True))
                self.tb_k.setItem(r, 4, _o("co" if code in sem else "CHUA", True))
                self.tb_k.setItem(r, 5, _o("da ve" if code in ve else "", True))
            self.tb_k.setSortingEnabled(True)
            self.tb_k.sortItems(2, Qt.SortOrder.DescendingOrder)

            chua = [(c, n) for c, n in cnt.items() if c not in sem]
            tong = sum(cnt.values()) or 1
            self.lbl.setText(
                "%d ma / %d khoi chuc nang tu %d DB (%s)%s.  Chua co mo hinh: %d ma / "
                "%d khoi (%.1f%%), trong do %d ma da co hinh manual de ve theo."
                % (len(cnt), sum(cnt.values()), len(dbs), nguon,
                   ("; %d DB khong doc duoc" % loi) if loi else "",
                   len(chua), sum(n for _, n in chua),
                   100.0 * sum(n for _, n in chua) / tong,
                   len([1 for c, _ in chua if c in hinh])))
            self._loc_khoi()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _loc_khoi(self):
        q = self.ed_k.text().strip().upper()
        chi_chua = self.cb_chua.isChecked()
        chi_hinh = self.cb_hinh.isChecked()
        for r in range(self.tb_k.rowCount()):
            ma = self.tb_k.item(r, 0).text().upper()
            ten = self.tb_k.item(r, 1).text().upper()
            an = bool(q) and q not in ma and q not in ten
            if chi_chua and self.tb_k.item(r, 4).text() != "CHUA":
                an = True
            if chi_hinh and not self.tb_k.item(r, 3).text():
                an = True
            self.tb_k.setRowHidden(r, bool(an))

    def _ma_chon(self):
        r = self.tb_k.currentRow()
        if r < 0:
            self.lbl.setText("Chon mot dong trong bang truoc.")
            return "", ""
        return self.tb_k.item(r, 0).text(), self.tb_k.item(r, 1).text()

    def _ve(self):
        code, ten = self._ma_chon()
        if not code:
            return
        from ui.internal_design_dialog import InternalDesignDialog
        # Che do THU VIEN: khong co bid/sheet_id nen khong gan voi khoi cu the nao tren
        # trang -> nut "Tinh gia tri (tu DB)" tu tat, muon thu thi nhay doi node vao.
        # Van dua db_path vao vi no chi dung de LOC BANG KY HIEU theo thu muc DB (xem
        # _used_symbols): khong loc thi bang do ra ca 1.019 ky hieu, kho tim.
        ds, _ = self._db_dang_dung()
        InternalDesignDialog(code, ten, self.main, db_path=(ds[0] if ds else None)).exec()
        self._nap_khoi()          # ve xong -> cot "Ban ve" phai doi ngay

    def _xem_hinh(self):
        code, ten = self._ma_chon()
        if not code:
            return
        if hasattr(self.main, "show_internal_logic"):
            self.main.show_internal_logic(code, ten)

    # ---------------- tab 2: F(x) ----------------
    def _tab_fx(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.ed_f = QLineEdit()
        self.ed_f.setPlaceholderText("Loc theo ten F(x), CPU, trang...")
        self.ed_f.textChanged.connect(self._loc_fx)
        v.addWidget(self.ed_f)
        self.tb_f = QTableWidget(0, 5)
        self.tb_f.setHorizontalHeaderLabels(["Ten F(x)", "CPU", "Trang", "Tag", "DB"])
        self.tb_f.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tb_f.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tb_f.setSortingEnabled(True)
        self.tb_f.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tb_f.itemDoubleClicked.connect(lambda *_: self._mo_fx())
        v.addWidget(self.tb_f, 1)
        h = QHBoxLayout()
        b = QPushButton("Mo trang chua F(x) nay")
        b.clicked.connect(self._mo_fx)
        h.addWidget(b)
        h.addStretch(1)
        self.lbl_f = QLabel("")
        h.addWidget(self.lbl_f)
        v.addLayout(h)
        self.tabs.addTab(w, "F(x)")
        self._nap_fx()

    def _nap_fx(self):
        """Doc thang tu chi muc du an - 4.290 khoi F(x) da duoc danh chi muc kem TEN mo ta
        san o do, khong phai mo lai 21 DB de dung lai tu dau."""
        try:
            from core import project_index as PI
            p = PI.index_path()
            if not os.path.exists(p):
                self.lbl_f.setText("Chua co chi muc du an - bam Ctrl+F mot lan de dung.")
                return
            con = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
            rows = list(con.execute(
                "SELECT text, cpuname, sheetlbl, extra, db, sheet FROM muc WHERE kind='fx'"))
            con.close()
        except Exception as e:
            self.lbl_f.setText("Khong doc duoc chi muc: %s" % e)
            return
        self.tb_f.setSortingEnabled(False)
        self.tb_f.setRowCount(0)
        for txt, cpu, lbl, tag, db, sheet in rows:
            r = self.tb_f.rowCount()
            self.tb_f.insertRow(r)
            it = _o(txt or "")
            it.setData(Qt.ItemDataRole.UserRole, (db, sheet))
            self.tb_f.setItem(r, 0, it)
            self.tb_f.setItem(r, 1, _o(cpu or ""))
            self.tb_f.setItem(r, 2, _o(lbl or ""))
            self.tb_f.setItem(r, 3, _o(tag or ""))
            self.tb_f.setItem(r, 4, _o(os.path.basename(str(db or ""))))
        self.tb_f.setSortingEnabled(True)
        self.lbl_f.setText("%d khoi F(x)" % len(rows))

    def _loc_fx(self):
        q = self.ed_f.text().strip().upper()
        hien = 0
        for r in range(self.tb_f.rowCount()):
            hop = True
            if q:
                hop = any(q in (self.tb_f.item(r, c).text() or "").upper()
                          for c in range(self.tb_f.columnCount()))
            self.tb_f.setRowHidden(r, not hop)
            hien += bool(hop)
        self.lbl_f.setText("%d / %d khoi F(x)" % (hien, self.tb_f.rowCount()))

    def _mo_fx(self):
        r = self.tb_f.currentRow()
        if r < 0:
            self.lbl_f.setText("Chon mot dong trong bang truoc.")
            return
        data = self.tb_f.item(r, 0).data(Qt.ItemDataRole.UserRole)
        if not data or not hasattr(self.main, "_open_cross"):
            return
        db, sheet = data
        if not os.path.exists(str(db)):
            self.lbl_f.setText("Khong con file: %s" % db)
            return
        self.main._open_cross(db, int(sheet))
        self.raise_()
