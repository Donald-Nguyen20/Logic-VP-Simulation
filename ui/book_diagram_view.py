# -*- coding: utf-8 -*-
"""O "So do so tay" cua cua so Help: ve LAI NGUYEN ban ve vector cua hang.

Net va chu lay tu core/manual_drawing.py (tach mot lan tu PDF so tay), dung tung toa
do - nguoi cam so tay nhin vao phai thay dung cai hinh minh van doc. Ban ve cua hang la
ban RUT GON (vd MOV2-NSH: 26 cong tren giay, than lenh DEF co 47) nen logic day du van
nam o o "So do" ngay tren; o nay chi them MOT thu vao hinh goc: to mau gia tri dang
chay len e-lip chan vao/ra, nut OPS va o hien thi.

Mau to nam DUOI net ve, nhat, de chu va net cua hang van doc ro nhu ban in.
Bam mot chan / o hien thi: to dam duong day di tu no qua cac cong (chan ra, o hien
thi: lui ve moi thu quyet dinh no) - day noi dung lai tu hinh hoc o core/book_trace.py.
Gia tri: chan vao lay tu mo phong; o hien thi / chan ra tinh tu do thi so tay
(core/book_diagram.py) - nut chot S/R va nut OPS khong suy ra duoc thi de trang,
khong doan bua.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, QEvent
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QToolTip, QWidget

from core.book_trace import ban_do, duong_sang
from core.help_i18n import tr
from .block_diagram import COL_0, COL_1

TL = 2.4                    # px tren 1 pt cua trang PDF: chu 4.8pt thanh ~11.5px
_CO_GOC = 100.0             # co font dung de do / ve roi thu nho: font ~5px bi lam tron xau
_DAU_BUT = {0: Qt.PenCapStyle.FlatCap, 1: Qt.PenCapStyle.RoundCap,
            2: Qt.PenCapStyle.SquareCap}
# Ten font trong PDF -> ho font tren may. MS PGothic co tren Windows ban tieng Nhat /
# goi font bo sung; khong co thi Arial, keo gian cho dung be dai tren giay.
_SANG = QColor(255, 140, 0, 150)   # but da quang cam: net dang do, ve duoi net den
_SANG_DAY = 1.6                    # pt - day hon net hang (~0.5pt) de nhin thay tu xa
_HO_FONT = (("gothic", ["MS PGothic", "MS UI Gothic", "Arial"]),
            ("arial", ["Arial"]),
            ("times", ["Times New Roman"]))


def _nhat(c, alpha):
    q = QColor(c)
    q.setAlpha(alpha)
    return q


class BookDrawing(QWidget):
    """Ban ve cua hang + o to mau gia tri. ve = ket qua manual_drawing.load()."""

    def __init__(self, ve, gia_tri, chu_thich, parent=None):
        """gia_tri: {chi so o neo: 0/1/None}; chu_thich: {chi so o neo: chuoi tooltip}."""
        super().__init__(parent)
        self.ve = ve
        self.gia_tri = dict(gia_tri)
        self.chu_thich = dict(chu_thich)
        self._net = [self._duong(n) for n in ve["net"]]
        self._font = {}
        self._bd = None             # ban do day noi: dung lan bam dau (~0.2-0.3s)
        self.chon_o = None          # o neo dang do duong
        self._sang = None           # QPainterPath cac doan dang to
        w, h = ve["khung"]
        self.setMinimumSize(int(w * TL) + 2, int(h * TL) + 2)
        self.setMouseTracking(True)

    def sizeHint(self):
        return self.minimumSize()

    # ---------- chuan bi ----------
    @staticmethod
    def _duong(n):
        p = QPainterPath()
        for d in n["d"]:
            p.moveTo(d[1], d[2])
            for i in range(3, len(d) - 1, 2):
                p.lineTo(d[i], d[i + 1])
            if d[0]:
                p.closeSubpath()
        but = Qt.PenStyle.NoPen
        if n.get("s"):
            but = QPen(QColor(n["s"]), max(n["w"], 0.01))
            but.setCapStyle(_DAU_BUT.get(n.get("c"), Qt.PenCapStyle.FlatCap))
            but.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        to = QBrush(QColor(n["f"])) if n.get("f") else Qt.BrushStyle.NoBrush
        return p, but, to

    def _font_cho(self, ten):
        if ten not in self._font:
            f = QFont()
            thap = ten.lower()
            ho = next((h for k, h in _HO_FONT if k in thap), ["Arial"])
            f.setFamilies(ho)
            f.setPixelSize(int(_CO_GOC))
            f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            self._font[ten] = (f, QFontMetricsF(f))
        return self._font[ten]

    # ---------- ve ----------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.translate(1, 1)
        p.scale(TL, TL)
        self._ve_mau(p)
        self._ve_sang(p)
        for duong, but, to in self._net:
            p.setPen(but)
            p.setBrush(to)
            p.drawPath(duong)
        for c in self.ve["chu"]:
            self._ve_chu(p, c)
        p.end()

    def _ve_mau(self, p):
        """O to gia tri, ve TRUOC net cua hang nen nam duoi net va chu."""
        p.setPen(Qt.PenStyle.NoPen)
        for i, o in enumerate(self.ve["neo"]):
            v = self.gia_tri.get(i)
            if v is None:
                continue
            p.setBrush(_nhat(COL_1 if v else COL_0, 110))
            x0, y0, x1, y1 = o["r"]
            r = QRectF(x0, y0, x1 - x0, y1 - y0)
            if o["hinh"] == "e":
                p.drawEllipse(r)
            else:
                p.drawRect(r)

    def _ve_sang(self, p):
        """Duong dang do: net but da quang day, nam duoi net den cua hang."""
        if self._sang is None:
            return
        but = QPen(_SANG, _SANG_DAY)
        but.setCapStyle(Qt.PenCapStyle.RoundCap)
        but.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(but)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(self._sang)

    def _ve_chu(self, p, c):
        """Chu dat dung duong chan chu cua PDF, keo gian ngang cho khop be dai tren giay."""
        x, y, co, ten_font, chu, goc, dai = c[:7]
        f, fm = self._font_cho(ten_font)
        rong = fm.horizontalAdvance(chu) * co / _CO_GOC
        gian = dai / rong if rong > 0 and dai > 0 else 1.0
        p.save()
        p.translate(x, y)
        if goc:
            p.rotate(goc)
        p.scale(gian * co / _CO_GOC, co / _CO_GOC)
        p.setFont(f)
        p.setPen(QColor(c[7] if len(c) > 7 else "#000000"))
        p.drawText(QPointF(0, 0), chu)
        p.restore()

    # ---------- chu thich khi re chuot ----------
    def o_tai(self, pos):
        """Chi so o neo nam duoi diem pos (toa do widget), hoac None."""
        x, y = (pos.x() - 1) / TL, (pos.y() - 1) / TL
        for i, o in enumerate(self.ve["neo"]):
            x0, y0, x1, y1 = o["r"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    # ---------- bam de do duong ----------
    def chon(self, i):
        """To sang duong day cua o neo i; None = xoa."""
        self.chon_o = i
        self._sang = None
        if i is not None:
            if self._bd is None:
                self._bd = ban_do(self.ve)
            duong = QPainterPath()
            for x0, y0, x1, y1 in duong_sang(self._bd, self.ve["neo"][i]):
                duong.moveTo(x0, y0)
                duong.lineTo(x1, y1)
            self._sang = duong
        self.update()

    def mousePressEvent(self, e):
        """Bam o neo: do duong; bam lai chinh no hoac cho trong: xoa."""
        if e.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            return
        i = self.o_tai(e.position())
        self.chon(None if i == self.chon_o else i)

    def mouseMoveEvent(self, e):
        if self.o_tai(e.position()) is None:
            self.unsetCursor()
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().mouseMoveEvent(e)

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            i = self.o_tai(e.pos())
            if i is None:
                QToolTip.hideText()
                e.ignore()
            else:
                QToolTip.showText(e.globalPos(), self.chu_thich.get(i, ""), self)
            return True
        return super().event(e)


# ---------------------------------------------------------------- gia tri
def gia_tri_nguon(nguon, g, pin_vals, node_vals):
    """0/1/None cho mot nguon cua file book_layouts: pin:N, reg:X, ra:N, ops:X."""
    loai, _, ten = nguon.partition(":")
    if loai == "pin":
        return pin_vals.get(int(ten))
    if loai == "reg":
        src = (g.get("regs") or {}).get(ten)
    elif loai == "ra":
        src = (g.get("outs") or {}).get(int(ten))
    else:
        return None                 # nut OPS: nguoi van hanh bam, mo phong khong co
    if not src:
        return None
    if src.startswith("pin:"):
        return pin_vals.get(int(src[4:]))
    return node_vals.get(src)


def _chu_thich(o, v, pin_sigs, so=None):
    """Tooltip mot o: nhan tren giay, nguon, ten tin hieu that (neu la chan), gia tri.

    so = tri so thuc cua chan vao analog (SV, PV, SENS-A...): o do khong to mau vi khong
    phai 0/1, nhung con so thi biet - phai hien, khong duoc noi 'khong biet'."""
    dong = ["<b>%s</b> &nbsp;<span style='color:#64748B'>%s</span>" % (o["nhan"], o["nguon"])]
    loai, _, ten = o["nguon"].partition(":")
    if loai in ("pin", "ra"):
        sig = pin_sigs.get(int(ten))
        if sig:
            dong.append(sig)
    if v is not None:
        dong.append(tr("Value: %d") % v)
    elif so is not None:
        dong.append(tr("Value: %g") % so)
    else:
        dong.append(tr("Value: no 0/1 here (latch memory, operator button or analog signal)"))
    return "<br>".join(dong)


def book_panel(code, pin_vals=None, pin_sigs=None, pin_nums=None):
    """(BookDrawing, "") hoac (None, ly do khong ve duoc).

    Ban ve lay tu so tay, logic lay tu DEF: may khong co thu muc DEF thi van ve duoc
    hinh, chi mat phan to mau o hien thi / chan ra (chan vao van to). pin_nums = {chan
    vao analog: so thuc}, chi de hien trong tooltip."""
    from core.block_fbd import eval_bool
    from core.book_diagram import book_graph
    from core.manual_drawing import load

    ve, why = load(code)
    if ve is None:
        return None, why
    pv = pin_vals or {}
    g = book_graph(code)
    nv = eval_bool(g, pv) if g["ok"] else {}
    gt, ct = {}, {}
    nums = pin_nums or {}
    for i, o in enumerate(ve["neo"]):
        gt[i] = gia_tri_nguon(o["nguon"], g, pv, nv)
        loai, _, so = o["nguon"].partition(":")
        x = nums.get(int(so)) if loai == "pin" else None
        ct[i] = _chu_thich(o, gt[i], pin_sigs or {}, x)
    return BookDrawing(ve, gt, ct), ""
