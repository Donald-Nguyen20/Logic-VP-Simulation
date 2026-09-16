# -*- coding: utf-8 -*-
"""O ve DUONG DAC TINH analog va BANG TRI SO cho cua so Help.

Tach khoi ui/block_diagram.py de moi file deu duoi 800 dong. Dung chung mau va ham
_pen/_so voi ban ve cong logic nen hai cua so doc len van khop nhau.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath

from core.block_curve import _so
from .block_diagram import (
    _pen, COL_NA, COL_NEN, COL_NHAT, COL_FILL,
)
from core.help_i18n import tr

# ------------------------------------------------------- duong dac tinh analog
COL_DUONG = QColor("#2563EB")     # duong dac tinh (ngo ra la so)
COL_MOC = QColor("#7C3AED")       # diem gay khuc cua bang F(x)
COL_NGUONG = QColor("#B45309")    # vach nguong / muc gioi han
COL_BONG = QColor("#FDE68A")      # vung co bao "dang bi kep" = 1
COL_NAY = QColor("#0F766E")       # diem lam viec hien tai
COL_LUOI = QColor("#EDF1F6")
COL_TRUC = QColor("#94A3B8")


class CurveDiagram(QWidget):
    """Ve ket qua core.block_curve.curve() dang 'xy'. Khong sua duoc gi - chi de doc.

    Truc X la DAU VAO cua khoi, truc Y la DAU RA. Cac so tren truc lay tu chinh khoi
    nay (nguong, muc gioi han, bang gay khuc) chu khong phai mot thang do chung: hai
    khoi cung ma nhung cai dat khac nhau se ra hai do thi khac nhau, dung nhu that.
    """

    _L, _R, _T, _B = 78.0, 26.0, 20.0, 46.0
    _LECH = 5.0     # do lech pixel cua nhanh di xuong, xem _ve_hai_nhanh()

    def __init__(self, cv, parent=None):
        super().__init__(parent)
        self.c = cv
        self._box = (self._L, self._T, 60.0, 60.0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(250)

    # ---------- pham vi ----------
    def _pham_vi(self):
        """(x0, x1, y0, y1) that cua do thi.

        Ngo ra 0/1 ep cung -0.15..1.15: neu de truc Y tu chay theo du lieu thi khoi nao
        dau ra ket o mot muc se ve thanh duong nam giua khung, nhin ra 0.5."""
        c = self.c
        xs = c["x"]
        x0, x1 = float(xs[0]), float(xs[-1])
        if x1 - x0 < 1e-12:
            x0, x1 = x0 - 1.0, x1 + 1.0
        if c.get("digital"):
            # Khoi co vong tre phai chua san mot dai trong duoi muc 0 cho dong chu giai
            # thich net lien / net dut - de chu do de len duong ra thi doc ra so.
            return x0, x1, (-0.34 if c.get("yb") else -0.15), 1.15
        ys = [v for v in list(c["y"]) + list(c["yb"]) if isinstance(v, (int, float))]
        ys += [p[1] for p in (c.get("bpts") or []) if isinstance(p[1], (int, float))]
        if not ys:
            ys = [0.0, 1.0]
        y0, y1 = min(ys), max(ys)
        if y1 - y0 < 1e-12:
            d = abs(y0) * 0.2 or 1.0
            return x0, x1, y0 - d, y1 + d
        d = (y1 - y0) * 0.12
        return x0, x1, y0 - d, y1 + d

    # ---------- ve ----------
    def paintEvent(self, ev):
        c = self.c
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.fillRect(self.rect(), COL_NEN)
        if not c.get("ok") or not c.get("x"):
            q.end()
            return
        f = QFont(); f.setPointSize(8); q.setFont(f)
        L, T = self._L, self._T
        W = max(60.0, self.width() - L - self._R)
        H = max(60.0, self.height() - T - self._B)
        self._box = (L, T, W, H)
        x0, x1, y0, y1 = self._pham_vi()

        def px(x):
            return L + W * (float(x) - x0) / (x1 - x0)

        def py(y):
            return T + H - H * (float(y) - y0) / (y1 - y0)

        q.fillRect(QRectF(L, T, W, H), COL_FILL)
        self._ve_bong(q, px)
        self._ve_luoi(q, px, py, x0, x1, y0, y1)
        q.setClipRect(QRectF(L - 1, T - 1, W + 2, H + 2))
        self._ve_nguong(q, px)
        self._ve_duong(q, px, py)
        self._ve_moc(q, px, py)
        self._ve_hien_tai(q, px, py)
        q.setClipping(False)
        q.setPen(QPen(COL_TRUC, 1.2))
        q.setBrush(Qt.BrushStyle.NoBrush)
        q.drawRect(QRectF(L, T, W, H))
        self._ve_ten_truc(q)
        q.end()

    def _ve_bong(self, q, px):
        """Vung dau ra co bao cua ho gioi han = 1. Ve TRUOC luoi de khong de len duong."""
        L, T, W, H = self._box
        for a, b, nhan in (self.c.get("shade") or []):
            xa, xb = px(a), px(b)
            r = QRectF(max(L, min(xa, xb)), T, max(2.0, abs(xb - xa)), H)
            q.fillRect(r, QBrush(COL_BONG))
            q.setPen(QPen(QColor("#92400E"), 1.0))
            q.drawText(QRectF(r.left() - 40, T + H - 16, r.width() + 80, 14),
                       int(Qt.AlignmentFlag.AlignCenter), nhan)

    def _ve_luoi(self, q, px, py, x0, x1, y0, y1):
        L, T, W, H = self._box
        dig = bool(self.c.get("digital"))
        muc = [0.0, 1.0] if dig else [y0 + k * (y1 - y0) / 4.0 for k in range(5)]
        for y in muc:
            q.setPen(QPen(COL_LUOI, 1.0))
            q.drawLine(QPointF(L, py(y)), QPointF(L + W, py(y)))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(16, py(y) - 8, L - 22, 16),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       ("%d" % y) if dig else _so(y))
        for k in range(5):
            x = x0 + k * (x1 - x0) / 4.0
            q.setPen(QPen(COL_LUOI, 1.0))
            q.drawLine(QPointF(px(x), T), QPointF(px(x), T + H))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(px(x) - 44, T + H + 4, 88, 14),
                       int(Qt.AlignmentFlag.AlignCenter), _so(x))
        # Truc 0 dam hon: khoi ABS/tru co ca hai dau, khong co vach nay thi khong biet
        # duong cong dang o phia am hay phia duong.
        if not dig and y0 < 0.0 < y1:
            q.setPen(QPen(QColor("#CBD5E1"), 1.2))
            q.drawLine(QPointF(L, py(0.0)), QPointF(L + W, py(0.0)))
        if not dig and x0 < 0.0 < x1:
            q.setPen(QPen(QColor("#CBD5E1"), 1.2))
            q.drawLine(QPointF(px(0.0), T), QPointF(px(0.0), T + H))

    def _ve_nguong(self, q, px):
        """Vach dung tai muc cai dat that cua khoi, kem tri so.

        Nhan viet DOC theo chinh vach do. Viet ngang thi o do thi 0/1 no nam de len duong
        ra (chi co hai cao do 0 va 1, khong con cho trong nao), doc ra hai thu chong nhau.
        """
        L, T, W, H = self._box
        net = QPen(COL_NGUONG, 1.2)
        net.setStyle(Qt.PenStyle.DashLine)
        for x, nhan in (self.c.get("guides") or []):
            X = px(x)
            q.setPen(net)
            q.drawLine(QPointF(X, T), QPointF(X, T + H))
            q.setPen(QPen(COL_NGUONG, 1.0))
            phai = X + 18 <= L + W
            day = 22.0 if self.c.get("yb") else 6.0   # tranh dong chu net lien/net dut
            q.save()
            q.translate(X + (4.0 if phai else -18.0), T + H - day)
            q.rotate(-90.0)
            q.drawText(QRectF(0, 0, max(40.0, H - day - 6), 14),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       nhan)
            q.restore()

    def _ve_duong(self, q, px, py):
        if self.c.get("digital"):
            self._ve_bac(q, px, py, self.c["y"], 2.4, False, 0.0)
            if self.c.get("yb"):
                self._ve_hai_nhanh(q, px, py)
            return
        xs, ys = self.c["x"], self.c["y"]
        q.setPen(QPen(COL_DUONG, 2.4))
        duong = QPainterPath()
        mo = False
        for i, y in enumerate(ys):
            if not isinstance(y, (int, float)):
                mo = False
                continue
            p = QPointF(px(xs[i]), py(y))
            if mo:
                duong.lineTo(p)
            else:
                duong.moveTo(p)
                mo = True
        q.drawPath(duong)

    def _ve_hai_nhanh(self, q, px, py):
        """Nhanh di xuong cua khoi co vong tre.

        Hai nhanh trung nhau tren gan het be ngang, ve chong len dung mot cao do thi chi
        thay mot duong. Nen nhanh xuong day len vai pixel (_LECH) va noi ro o chu thich -
        day len la de NHIN thay, tri so that van la 0 va 1."""
        self._ve_bac(q, px, py, self.c["yb"], 1.8, True, -self._LECH)
        q.setPen(QPen(COL_NHAT, 1.0))
        L, T, W, H = self._box
        q.drawText(QRectF(L + 4, T + H - 17, W - 8, 14),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                   tr("solid = input rising      dashed = input falling"))

    def _ve_bac(self, q, px, py, ys, day, net, lech):
        """Ngo ra 0/1 ve dang bac thang, mau theo dung quy uoc cua ban ve chinh."""
        xs = self.c["x"]
        for i in range(1, len(xs)):
            v = ys[i - 1]
            if v is None:
                continue
            b = _pen(v, day)
            if net:
                b.setStyle(Qt.PenStyle.DashLine)
            q.setPen(b)
            yv = py(1 if v else 0) + lech
            q.drawLine(QPointF(px(xs[i - 1]), yv), QPointF(px(xs[i]), yv))
            if ys[i] is not None and bool(ys[i]) != bool(v):
                b2 = _pen(ys[i], day)
                if net:
                    b2.setStyle(Qt.PenStyle.DashLine)
                q.setPen(b2)
                q.drawLine(QPointF(px(xs[i]), py(0) + lech),
                           QPointF(px(xs[i]), py(1) + lech))

    def _ve_moc(self, q, px, py):
        """Cac diem gay khuc THAT trong bang F(x) cua khoi nay."""
        pts = self.c.get("bpts") or []
        if not pts:
            return
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(COL_MOC))
        for x, y in pts:
            q.drawEllipse(QPointF(px(x), py(y)), 3.0, 3.0)
        q.setBrush(Qt.BrushStyle.NoBrush)

    def _ve_hien_tai(self, q, px, py):
        """Diem lam viec dang chay tren khoi nay, neu da co ket qua mo phong."""
        c = self.c
        x, y = c.get("x_now"), c.get("y_now")
        if not isinstance(x, (int, float)) or not (c["x"][0] <= x <= c["x"][-1]):
            return
        L, T, W, H = self._box
        cham = QPen(COL_NAY, 1.1)
        cham.setStyle(Qt.PenStyle.DotLine)
        q.setPen(cham)
        q.drawLine(QPointF(px(x), T), QPointF(px(x), T + H))
        nhan = tr("now: %s") % _so(x)
        if isinstance(y, (int, float)):
            yv = py(1 if y else 0) if c.get("digital") else py(y)
            q.setPen(cham)
            q.drawLine(QPointF(L, yv), QPointF(L + W, yv))
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QBrush(COL_NAY))
            q.drawEllipse(QPointF(px(x), yv), 3.6, 3.6)
            q.setBrush(Qt.BrushStyle.NoBrush)
            nhan += "  ->  %s" % (("%d" % int(y)) if c.get("digital") else _so(y))
        f = q.font(); f.setBold(True); q.setFont(f)
        q.setPen(QPen(COL_NAY, 1.0))
        q.drawText(QRectF(L + 4, T + 2, W - 8, 14),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop), nhan)
        f.setBold(False); q.setFont(f)

    def _ve_ten_truc(self, q):
        L, T, W, H = self._box
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(L, T + H + 20, W, 14), int(Qt.AlignmentFlag.AlignCenter),
                   self.c.get("xlabel") or tr("Input"))
        q.save()
        q.translate(13.0, T + H / 2.0)
        q.rotate(-90.0)
        q.drawText(QRectF(-H / 2.0, -7.0, H, 14), int(Qt.AlignmentFlag.AlignCenter),
                   self.c.get("ylabel") or tr("Output"))
        q.restore()


class ValueTable(QWidget):
    """Khoi khong ve duoc thanh duong cong: in CONG THUC that + tri so tung chan.

    Ho nhieu dau vao (cong, tru, max, trung vi...) khong co mot duong dac tinh nao het -
    quet mot chan roi ve se ra mot duong thang vo nghia, nguoi doc lai tuong do la toan
    bo hanh vi cua khoi. Nen o day in thang cong thuc va so that dang chay.
    """

    def __init__(self, cv, parent=None):
        super().__init__(parent)
        self.c = cv
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(self._o_cong_thuc())
        if cv.get("rows"):
            v.addWidget(self._bang())
        v.addWidget(self._dong_ra())

    def _o_cong_thuc(self):
        o = QFrame()
        o.setFrameShape(QFrame.Shape.StyledPanel)
        o.setStyleSheet("QFrame{border:1px solid #CBD5E1;border-radius:6px;"
                        "background:#FFFFFF;}")
        ov = QVBoxLayout(o)
        t = QLabel(self.c.get("formula") or "")
        f = QFont("Consolas"); f.setPointSize(11); f.setBold(True)
        t.setFont(f)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("border:none;color:#1E293B")
        t.setWordWrap(True)
        ov.addWidget(t)
        return o

    def _bang(self):
        rows = self.c["rows"]
        t = QTableWidget(len(rows), 3)
        t.setHorizontalHeaderLabels([tr("Input"), tr("Signal"), tr("Value now")])
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for i, (ten, net, gt) in enumerate(rows):
            for j, s in enumerate((ten, net, gt)):
                it = QTableWidgetItem(str(s))
                if j == 2 and s == tr("not known"):
                    it.setForeground(COL_NA)
                t.setItem(i, j, it)
        h = t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        # Chieu cao do theo dung kieu chu dang chay: dat cung 24px/dong thi may nao chu
        # to hon se moc ra thanh cuon giua bang hai dong.
        cao_d = t.verticalHeader().defaultSectionSize()
        cao_h = t.horizontalHeader().sizeHint().height()
        t.setFixedHeight(min(len(rows), 6) * cao_d + cao_h + 4)
        return t

    def _dong_ra(self):
        out = self.c.get("out")
        if isinstance(out, (int, float)):
            s = tr("Output now = %s") % (("%d" % int(out)) if self.c.get("digital")
                                     else _so(out))
            mau = "#166534"
        else:
            s = tr("Output now = not known - run Simulate to fill the live values in.")
            mau = "#6B7280"
        lb = QLabel(s)
        f = QFont(); f.setBold(True)
        lb.setFont(f)
        lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lb.setStyleSheet("color:%s" % mau)
        return lb
