# -*- coding: utf-8 -*-
"""Hai bang chon nam BEN TRONG ban ve logic noi (ui/internal_design_dialog.py).

Truoc day day la mot hop thoai danh muc rieng: bam nut thi ra mot cai bang, chon dong
roi moi mo duoc ban ve. Thua mot nhip - nguoi ta bam "Internal logic" la de VE, chu
khong phai de doc bang. Nay hai bang nay thanh hai the canh bang ky hieu, ngay trong
ban ve: dang ve thi voi tay lay them khoi hoac F(x), khong phai dong mo cua so.

Hai the, vi day la HAI TRUC KHAC NHAU - gop chung se roi:
  Khoi chuc nang: mot mo hinh dung chung cho MOI thuc the cua ma do. Ve 1 lan an ca du an.
  F(x)          : moi khoi mot bang gay khuc RIENG. 4.290 khoi, deu chung ma 4035, nen
                  ten ma khong noi len gi - phai keo dung bang cua dung khoi do ve.

Cot trang thai cua the "Khoi chuc nang" chinh la BANG VIEC CAN LAM: do tren 21 DB cua
du an co 132 ma / 28.206 khoi chua co mo hinh mo phong, trong do 31 ma / 9.742 khoi da
co san hinh so do noi bo trong manual - tuc la ve theo hinh co san la chay duoc ngay.
"""
from __future__ import annotations
import collections
import json
import os
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
        # Thieu file du lieu chi lam mat mot COT trang thai, khong duoc lam chet bang.
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


def db_trong_index():
    """Duong dan DB ghi trong chi muc du an. Dung khi danh sach DB dang mo bi rong -
    chi muc van con nguyen nen bang chon khong viec gi phai trong theo."""
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


def db_dang_dung(main):
    """DB de quet: uu tien danh sach dang mo trong app, rong thi lui ve chi muc."""
    ds = list(getattr(main, "db_nodes", {}) or {})
    return (ds, "dang mo") if ds else (db_trong_index(), "chi muc")


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


class KhoiPanel(QWidget):
    """Bang toan bo ma khoi chuc nang cua cac DB, kem trang thai mo hinh mo phong."""

    chon = Signal(str, str)          # (macrocode, ten khoi) - nhay doi hoac bam nut

    def __init__(self, main=None, parent=None):
        super().__init__(parent)
        self.main = main
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("Loc theo ma hoac ten khoi...")
        self.ed.textChanged.connect(self._loc)
        v.addWidget(self.ed)
        self.cb_chua = QCheckBox("Chi ma CHUA co mo hinh")
        self.cb_chua.toggled.connect(self._loc)
        v.addWidget(self.cb_chua)
        self.cb_hinh = QCheckBox("Chi ma co hinh manual")
        self.cb_hinh.toggled.connect(self._loc)
        v.addWidget(self.cb_hinh)

        self.tb = QTableWidget(0, 6)
        self.tb.setHorizontalHeaderLabels(
            ["Ma", "Ten khoi", "So khoi", "Hinh", "Mo phong", "Ban ve"])
        self.tb.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tb.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tb.setSortingEnabled(True)
        self.tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tb.itemDoubleClicked.connect(lambda *_: self._phat())
        v.addWidget(self.tb, 1)

        h = QHBoxLayout()
        b1 = QPushButton("Mo ban ve cua ma nay")
        b1.clicked.connect(self._phat)
        h.addWidget(b1)
        b2 = QPushButton("Hinh manual")
        b2.setToolTip("Xem so do noi bo in trong manual cua hang de ve theo")
        b2.clicked.connect(self._xem_hinh)
        h.addWidget(b2)
        v.addLayout(h)

        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        v.addWidget(self.lbl)
        self.nap()

    def nap(self):
        """Quet lai toan bo DB. Goi lai sau khi luu ban ve de cot 'Ban ve' doi ngay."""
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dbs, nguon = db_dang_dung(self.main)
            cnt, loi = _dem_khoi(dbs)
            cnt.pop(_MA_TERMINAL, None)
            ten = _ten_theo_ma()
            sem = _sem_codes()
            hinh = {str(k).upper() for k in _doc_json("macro_internal.json")}
            ve = set()
            d_ve = os.path.join(_CORE, "internal_design")
            if os.path.isdir(d_ve):
                ve = {f[:-5].upper() for f in os.listdir(d_ve) if f.lower().endswith(".json")}

            self.tb.setSortingEnabled(False)
            self.tb.setRowCount(0)
            for code, n in cnt.most_common():
                r = self.tb.rowCount()
                self.tb.insertRow(r)
                self.tb.setItem(r, 0, _o(code))
                self.tb.setItem(r, 1, _o(ten.get(code, "")))
                self.tb.setItem(r, 2, _so(n))
                self.tb.setItem(r, 3, _o("co" if code in hinh else "", True))
                self.tb.setItem(r, 4, _o("co" if code in sem else "CHUA", True))
                self.tb.setItem(r, 5, _o("da ve" if code in ve else "", True))
            self.tb.setSortingEnabled(True)
            self.tb.sortItems(2, Qt.SortOrder.DescendingOrder)

            chua = [(c, n) for c, n in cnt.items() if c not in sem]
            tong = sum(cnt.values()) or 1
            self.lbl.setText(
                "%d ma / %d khoi tu %d DB (%s)%s.\nChua co mo hinh: %d ma / %d khoi "
                "(%.1f%%), trong do %d ma da co hinh manual de ve theo."
                % (len(cnt), sum(cnt.values()), len(dbs), nguon,
                   ("; %d DB khong doc duoc" % loi) if loi else "",
                   len(chua), sum(n for _, n in chua),
                   100.0 * sum(n for _, n in chua) / tong,
                   len([1 for c, _ in chua if c in hinh])))
            self._loc()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _loc(self):
        q = self.ed.text().strip().upper()
        chi_chua = self.cb_chua.isChecked()
        chi_hinh = self.cb_hinh.isChecked()
        for r in range(self.tb.rowCount()):
            ma = self.tb.item(r, 0).text().upper()
            ten = self.tb.item(r, 1).text().upper()
            an = bool(q) and q not in ma and q not in ten
            if chi_chua and self.tb.item(r, 4).text() != "CHUA":
                an = True
            if chi_hinh and not self.tb.item(r, 3).text():
                an = True
            self.tb.setRowHidden(r, bool(an))

    def _ma_chon(self):
        r = self.tb.currentRow()
        if r < 0:
            self.lbl.setText("Chon mot dong trong bang truoc.")
            return "", ""
        return self.tb.item(r, 0).text(), self.tb.item(r, 1).text()

    def _phat(self):
        code, ten = self._ma_chon()
        if code:
            self.chon.emit(code, ten)

    def _xem_hinh(self):
        code, ten = self._ma_chon()
        if code and hasattr(self.main, "show_internal_logic"):
            self.main.show_internal_logic(code, ten)


class FxPanel(QWidget):
    """Bang 4.290 khoi F(x) cua ca du an, doc thang tu chi muc."""

    chon = Signal(object)            # dict(db, sheet, tag, ten) - nhay doi hoac bam nut

    def __init__(self, main=None, parent=None):
        super().__init__(parent)
        self.main = main
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("Loc theo ten F(x), CPU, trang...")
        self.ed.textChanged.connect(self._loc)
        v.addWidget(self.ed)
        self.tb = QTableWidget(0, 5)
        self.tb.setHorizontalHeaderLabels(["Ten F(x)", "CPU", "Trang", "Tag", "DB"])
        self.tb.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tb.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tb.setSortingEnabled(True)
        self.tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tb.itemDoubleClicked.connect(lambda *_: self._phat())
        v.addWidget(self.tb, 1)
        h = QHBoxLayout()
        b = QPushButton("Tha vao ban ve")
        b.setToolTip("Them khoi F(x) nay vao so do, KEM bang gay khuc that cua no")
        b.clicked.connect(self._phat)
        h.addWidget(b)
        b2 = QPushButton("Mo trang")
        b2.clicked.connect(self._mo_trang)
        h.addWidget(b2)
        v.addLayout(h)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        v.addWidget(self.lbl)
        self.nap()

    def nap(self):
        """Doc thang tu chi muc du an - 4.290 khoi F(x) da duoc danh chi muc kem TEN mo ta
        san o do, khong phai mo lai 21 DB de dung lai tu dau."""
        try:
            from core import project_index as PI
            p = PI.index_path()
            if not os.path.exists(p):
                self.lbl.setText("Chua co chi muc du an - bam Ctrl+F mot lan de dung.")
                return
            con = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
            rows = list(con.execute(
                "SELECT text, cpuname, sheetlbl, extra, db, sheet FROM muc WHERE kind='fx'"))
            con.close()
        except Exception as e:
            self.lbl.setText("Khong doc duoc chi muc: %s" % e)
            return
        self.tb.setSortingEnabled(False)
        self.tb.setRowCount(0)
        for txt, cpu, lbl, tag, db, sheet in rows:
            r = self.tb.rowCount()
            self.tb.insertRow(r)
            it = _o(txt or "")
            it.setData(Qt.ItemDataRole.UserRole, (db, sheet, tag or ""))
            self.tb.setItem(r, 0, it)
            self.tb.setItem(r, 1, _o(cpu or ""))
            self.tb.setItem(r, 2, _o(lbl or ""))
            self.tb.setItem(r, 3, _o(tag or ""))
            self.tb.setItem(r, 4, _o(os.path.basename(str(db or ""))))
        self.tb.setSortingEnabled(True)
        self.lbl.setText("%d khoi F(x)" % len(rows))

    def _loc(self):
        q = self.ed.text().strip().upper()
        hien = 0
        for r in range(self.tb.rowCount()):
            hop = True
            if q:
                hop = any(q in (self.tb.item(r, c).text() or "").upper()
                          for c in range(self.tb.columnCount()))
            self.tb.setRowHidden(r, not hop)
            hien += bool(hop)
        self.lbl.setText("%d / %d khoi F(x)" % (hien, self.tb.rowCount()))

    def _dong_chon(self):
        r = self.tb.currentRow()
        if r < 0:
            self.lbl.setText("Chon mot dong trong bang truoc.")
            return None
        db, sheet, tag = self.tb.item(r, 0).data(Qt.ItemDataRole.UserRole)
        if not os.path.exists(str(db)):
            self.lbl.setText("Khong con file: %s" % db)
            return None
        return {"db": str(db), "sheet": int(sheet), "tag": tag,
                "ten": self.tb.item(r, 0).text()}

    def _phat(self):
        d = self._dong_chon()
        if d:
            self.chon.emit(d)

    def _mo_trang(self):
        d = self._dong_chon()
        if d and hasattr(self.main, "_open_cross"):
            self.main._open_cross(d["db"], d["sheet"])


def diem_fx(db, sheet, tag):
    """Bang gay khuc THAT cua mot khoi F(x) -> (pts, ten, ghi chu loi).

    Chi muc chi luu (db, trang, tag) chu khong luu BLOCK_ID, nen phai mo dung trang do
    va doi chieu tag. Trang thuong chi co vai khoi F(x) nen viec nay re; doi lai khong
    phai dung lai ca chi muc 16 MB chi de them mot cot."""
    try:
        from core import sheet_sim as SS
        dau = None
        for ap in SS._analog_producers(db, sheet).values():
            if ap.get("op") != "FUNC":
                continue
            fi = SS.func_info(db, sheet, ap["bid"])
            if dau is None:
                dau = fi
            if (fi.get("tag") or "").strip() == (tag or "").strip():
                return fi.get("pts") or [], fi.get("name") or "", ""
        if dau is not None:
            # Tag lech (chi muc cu hon DB chang han) - van lay duoc khoi F(x) dau trang,
            # nhung phai NOI RA, vi duong cong sai thi ket qua mo phong sai theo.
            return (dau.get("pts") or [], dau.get("name") or "",
                    "Khong thay tag '%s' tren trang, lay khoi F(x) dau tien." % tag)
        return [], "", "Trang %s khong con khoi F(x) nao." % sheet
    except Exception as e:
        return [], "", "Khong doc duoc bang F(x): %s" % e
