# -*- coding: utf-8 -*-
"""Cai dat bang gay khuc cho mot khoi F(x) tren ban ve mo phong.

Vi sao can rieng cho nay: ca 4.290 khoi F(x) cua du an deu chung macrocode 4035, nen
KY HIEU khong noi len duoc duong cong nao ca - bang gay khuc la cua rieng tung khoi.
Tha tu the "F(x)" thi bang duoc keo tu DB ve, con them tu bang ky hieu thi khoi con
trong, ma mot khoi F(x) trong luon tra None -> ca nhanh phia sau cung None. Nhin ra
nhu so do sai chu khong nhu thieu du lieu, nen phai cho cai bang ngay tai cho.

Bang o day duoc SAP THEO X truoc khi dung, dung nhu core/sheet_sim.func_points sap
bang doc tu DB - noi suy tuyen tinh gia dinh x tang dan, khong sap thi mot diem lac
cho keo lech ca doan.

Co tinh KHONG co duong cong dung san kieu y=x hay can bac hai: bang bia ra van cho ra
so, va so do chay tron tru, nen khong con dau hieu nao de biet la dang mo phong nham
duong cong. Bang phai la bang THAT - chep tu mot khoi F(x) cua du an, hoac go/dan tu
tai lieu.
"""
import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


def chuan_hoa(pts):
    """Loc + sap bang gay khuc, tra ve (pts, ghi_chu). pts rong nghia la khong dung duoc."""
    sach = []
    for p in pts or []:
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
            continue
        sach.append((x, y))
    if len(sach) < 2:
        return [], "Bang phai co it nhat 2 diem."
    sach.sort()
    # Hai diem trung X thi doan giua co do doc vo han. sheet_sim tra y0 cho truong hop
    # nay (x1 == x0), tuc diem sau bi bo qua - giu lai chi lam nguoi dung tuong da cai
    # duoc mot buoc nhay dung tai do.
    trung = [a for (a, _), (b, _) in zip(sach, sach[1:]) if a == b]
    if trung:
        gon, thay = [], set()
        for x, y in sach:
            if x in thay:
                continue
            thay.add(x)
            gon.append((x, y))
        if len(gon) < 2:
            return [], "Bang phai co it nhat 2 diem co X khac nhau."
        return gon, ("Da bo diem trung X (%s), giu diem dau tien - dung nhu cach "
                     "sheet_sim noi suy." % ", ".join("%g" % t for t in trung[:5]))
    return sach, ""


class Xem(QWidget):
    """Ve nhanh duong cong de nhin ra ngay bang co bi go nham dau khong."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pts = []
        self.setMinimumHeight(150)

    def dat(self, pts):
        self.pts = list(pts or [])
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(38, 10, -10, -22)
        p.fillRect(self.rect(), QColor("#0F172A"))
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawRect(r)
        p.setFont(QFont("Segoe UI", 7))
        if len(self.pts) < 2:
            p.setPen(QColor("#94A3B8"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Chua co bang gay khuc")
            return
        xs = [a for a, _ in self.pts]
        ys = [b for _, b in self.pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        dx = (x1 - x0) or 1.0
        dy = (y1 - y0) or 1.0

        def toa(x, y):
            return QPointF(r.left() + (x - x0) / dx * r.width(),
                           r.bottom() - (y - y0) / dy * r.height())

        p.setPen(QPen(QColor("#1E293B"), 1))
        for i in range(1, 4):
            yy = int(r.top() + r.height() * i / 4.0)
            p.drawLine(r.left(), yy, r.right(), yy)
        p.setPen(QPen(QColor("#38BDF8"), 2))
        p.drawPolyline(QPolygonF([toa(a, b) for a, b in self.pts]))
        p.setPen(QPen(QColor("#FDE68A"), 1))
        for a, b in self.pts:
            p.drawEllipse(toa(a, b), 2.4, 2.4)
        p.setPen(QColor("#94A3B8"))
        p.drawText(2, r.top() + 8, "%g" % y1)
        p.drawText(2, r.bottom(), "%g" % y0)
        p.drawText(r.left(), r.bottom() + 16, "%g" % x0)
        p.drawText(r.right() - 34, r.bottom() + 16, "%g" % x1)


class FxSetupDialog(QDialog):
    """Nhap / sua bang gay khuc cua mot khoi F(x). Ket qua nam o .pts va .ten."""

    def __init__(self, pts=None, ten="", parent=None, main=None):
        super().__init__(parent)
        self.setWindowTitle("Cai dat khoi F(x)")
        self.resize(560, 680)
        self._main = main
        self.pts = [tuple(q) for q in (pts or [])]
        self.ten = ten or ""
        v = QVBoxLayout(self)

        h = QHBoxLayout()
        h.addWidget(QLabel("Ten:"))
        self.ed_ten = QLineEdit(self.ten)
        self.ed_ten.setPlaceholderText("vd: GAIN CALC FOR CORRN BY MWD")
        h.addWidget(self.ed_ten, 1)
        v.addLayout(h)

        b2 = QPushButton("Lay bang tu mot khoi F(x) that trong du an...")
        b2.setToolTip("Chep nguyen bang gay khuc cua mot trong 4.290 khoi F(x) co that")
        b2.clicked.connect(self._chep_that)
        v.addWidget(b2)

        self.tb = QTableWidget(0, 2)
        self.tb.setHorizontalHeaderLabels(["X (vao)", "Y (ra)"])
        self.tb.horizontalHeader().setStretchLastSection(True)
        self.tb.itemChanged.connect(self._ve_lai)
        v.addWidget(self.tb, 1)

        h3 = QHBoxLayout()
        for nhan, ham in (("+ Diem", self._them), ("- Diem", self._bot),
                          ("Sap theo X", self._sap)):
            bb = QPushButton(nhan)
            bb.clicked.connect(ham)
            h3.addWidget(bb)
        h3.addStretch(1)
        v.addLayout(h3)

        v.addWidget(QLabel("Dan bang (moi dong mot cap x y, ngan bang dau cach / tab / phay):"))
        self.ed_dan = QPlainTextEdit()
        self.ed_dan.setFixedHeight(58)
        v.addWidget(self.ed_dan)
        bn = QPushButton("Nap tu o dan")
        bn.clicked.connect(self._nap_dan)
        v.addWidget(bn)

        self.xem = Xem()
        v.addWidget(self.xem)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("color:#94A3B8")
        v.addWidget(self.lbl)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._xong)
        box.rejected.connect(self.reject)
        v.addWidget(box)
        self._nap_bang(self.pts)

    # ---------- bang ----------
    def _nap_bang(self, pts):
        self.tb.blockSignals(True)
        self.tb.setRowCount(0)
        for x, y in pts or []:
            r = self.tb.rowCount()
            self.tb.insertRow(r)
            self.tb.setItem(r, 0, QTableWidgetItem("%g" % x))
            self.tb.setItem(r, 1, QTableWidgetItem("%g" % y))
        self.tb.blockSignals(False)
        self._ve_lai()

    def _doc_bang(self):
        ra = []
        for r in range(self.tb.rowCount()):
            a, b = self.tb.item(r, 0), self.tb.item(r, 1)
            if a is None or b is None:
                continue
            ta, tb = a.text().strip(), b.text().strip()
            if not ta and not tb:
                continue
            try:
                ra.append((float(ta.replace(",", ".")), float(tb.replace(",", "."))))
            except ValueError:
                continue
        return ra

    def _ve_lai(self, *_):
        pts = self._doc_bang()
        self.xem.dat(sorted(pts))
        if len(pts) < 2:
            self.lbl.setText("Can it nhat 2 diem hop le.")
            return
        xs = sorted(a for a, _ in pts)
        self.lbl.setText("%d diem, X tu %g den %g. Ngoai khoang nay khoi giu nguyen muc "
                         "dau/cuoi (khong ngoai suy)." % (len(pts), xs[0], xs[-1]))

    def _them(self):
        r = self.tb.rowCount()
        self.tb.insertRow(r)
        self.tb.setItem(r, 0, QTableWidgetItem("0"))
        self.tb.setItem(r, 1, QTableWidgetItem("0"))

    def _bot(self):
        r = self.tb.currentRow()
        self.tb.removeRow(r if r >= 0 else self.tb.rowCount() - 1)
        self._ve_lai()

    def _sap(self):
        self._nap_bang(sorted(self._doc_bang()))

    def _nap_dan(self):
        pts = []
        for dong in self.ed_dan.toPlainText().splitlines():
            t = dong.replace(",", " ").replace(";", " ").split()
            if len(t) < 2:
                continue
            try:
                pts.append((float(t[0]), float(t[1])))
            except ValueError:
                continue      # dong tieu de kieu "X  Y" thi bo qua, khong bao loi
        if not pts:
            QMessageBox.warning(self, "Khong doc duoc",
                                "Khong tim thay cap so nao trong o dan.")
            return
        self._nap_bang(sorted(pts))

    def _chep_that(self):
        """Lay bang cua mot khoi F(x) that trong du an lam diem xuat phat."""
        from ui import internal_panels as _P
        d = QDialog(self)
        d.setWindowTitle("Chep bang tu mot khoi F(x) that")
        d.resize(560, 620)
        lo = QVBoxLayout(d)
        pn = _P.FxPanel(self._main)
        lo.addWidget(pn)

        def nhan(info):
            pts, ten, ghi = _P.diem_fx(info["db"], info["sheet"], info["tag"])
            if not pts:
                QMessageBox.warning(d, "Khong lay duoc bang",
                                    ghi or "Khoi nay khong con bang gay khuc.")
                return
            self._nap_bang(pts)
            if ten or info.get("ten"):
                self.ed_ten.setText(ten or info["ten"])
            d.accept()

        pn.chon.connect(nhan)
        d.exec()

    def _xong(self):
        pts, ghi = chuan_hoa(self._doc_bang())
        if not pts:
            QMessageBox.warning(self, "Bang chua dung", ghi)
            return
        if ghi:
            QMessageBox.information(self, "Da chinh bang", ghi)
        self.pts = pts
        self.ten = self.ed_ten.text().strip()
        self.accept()
