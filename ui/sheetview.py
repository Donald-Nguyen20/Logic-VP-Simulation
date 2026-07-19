# -*- coding: utf-8 -*-
"""
SheetScene: ve 1 Sheet (tu core.sheet_render) TRUNG THUC nhu UCS.pdf:
khoi + tag + nhan + exec(do) + tham so, day theo TOA DO GOC (CAD_LIN_DETAIL),
ten net tren day, terminal 2 mep (Line Name/From/LID/To), khung 7 cot.
"""
from __future__ import annotations
import os
import re
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF

SC = 8.0            # ti le DB-unit -> pixel
MARGIN_L = 440      # be rong vung cot Line Name/From/LID trai
MARGIN_R = 440      # vung phai
MARGIN_T = 60
COL_BLK = QColor("#2C3E5C")
COL_BODY = QColor("#F4F7FC")
COL_WIRE = QColor("#5C6B84")
COL_GRID = QColor("#D2DAE6")
COL_RED = QColor("#D64545")
COL_NET = QColor("#1E66C7")
COL_TXT = QColor("#223047")
COL_SYM = QColor("#3B6FE0")   # accent indigo cho ky hieu (hien dai)


# --- Bo ky hieu rieng (trich tu SVG -> core/symbol_shapes.json) de ve khoi giong PDF ---
import json as _json
_SYMS = None


def _symbol_shapes():
    global _SYMS
    if _SYMS is None:
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "symbol_shapes.json")
        try:
            _SYMS = _json.load(open(p, encoding="utf-8"))
        except Exception:
            _SYMS = {}
    return _SYMS


class SheetScene(QGraphicsScene):
    def __init__(self, sheet, parent=None):
        super().__init__(parent)
        self.sh = sheet
        self.ymax = sheet.ymax
        self.xmax = sheet.xmax
        self._right_x0 = MARGIN_L + self.xmax * SC + 30
        self.on_navigate = None      # callback(term) khi click terminal co diem den
        self.on_block_click = None   # callback(code, name) khi click 1 khoi
        self._hits = []              # [(QRectF, term)]
        self._block_hits = []        # [(QRectF, code, name)]
        self._term_hits = []         # [(QRectF, net, linename)] moi terminal (de chuot phai xem node)
        self.svg_mode = True         # luon ve bang bo ky hieu (native)
        # --- mo phong tren trang ---
        self.sim_values = None       # {net: 0/1/None} (digital) khi bat mo phong
        self.sim_kind = {}           # {net: 'D'/'A'/'?'}
        self.sim_inputs = set()      # net la dau vao (click de set)
        self.sim_analog = {}         # {net: float} gia tri analog nguoi nhap
        self.on_sim_toggle = None    # callback(net) khi click dau vao DIGITAL
        self.on_sim_set_analog = None  # callback(net) khi click dau vao ANALOG
        self.on_sim_dyn_config = None  # callback(bid) khi click khoi DONG de cai dat
        self.on_func_view = None     # callback(bid, name) khi click khoi F(x)
        self.func_codes = set()      # cac macrocode la F(x)
        self.sim_dyn = {}            # {bid: {"ti","out","code","label"}} khoi DONG (tich phan...)
        self.build()

    # --- mo phong: bat/tat + mau ---
    def set_sim(self, values, kinds, inputs, analog=None, dyn=None):
        self.sim_values = dict(values or {})
        self.sim_kind = dict(kinds or {})
        self.sim_inputs = set(inputs or [])
        self.sim_analog = dict(analog or {})
        self.sim_dyn = dict(dyn or {})
        self.build()

    def clear_sim(self):
        self.sim_values = None
        self.sim_kind = {}
        self.sim_inputs = set()
        self.sim_analog = {}
        self.sim_dyn = {}
        self.build()

    def _sim_on(self):
        return self.sim_values is not None

    def _sim_cell_col(self, net):
        """(bg, fg) cho o terminal: analog=xanh duong, digital=xanh/do/xam theo 0/1."""
        if self.sim_kind.get(net) == "A":
            return QColor("#DBEAFE"), QColor("#1D4ED8")
        v = self.sim_values.get(net) if self.sim_values else None
        if v == 1:
            return QColor("#DCFCE7"), QColor("#15803D")
        if v == 0:
            return QColor("#FEE2E2"), QColor("#B91C1C")
        return QColor("#F1F5F9"), QColor("#94A3B8")

    def _sim_wire_pen(self, net):
        """(QColor, width) cho day: analog=xanh duong manh, digital=xanh/do theo 0/1."""
        if self.sim_kind.get(net) == "A":
            return QColor("#93C5FD"), 1.6
        v = self.sim_values.get(net) if self.sim_values else None
        if v == 1:
            return QColor("#16A34A"), 2.4
        if v == 0:
            return QColor("#DC2626"), 2.4
        return QColor("#CBD5E1"), 1.1

    # --- bien doi toa do ---
    def sx(self, x):
        return MARGIN_L + x * SC

    def sy(self, y):
        return (self.ymax - y) * SC + MARGIN_T

    def set_svg_mode(self, on):
        self.svg_mode = bool(on)
        self.build()

    def build(self):
        self.clear()
        self._hits = []
        self._block_hits = []
        self._term_hits = []
        self._term_lids = set(t.lid for t in self.sh.terms if getattr(t, "lid", None))
        self._sim_wire_hits = []      # [(QRectF, net)] diem settable NOI BO tren day
        # vi tri NGO RA cua tung net (de dat nhan gia tri ngay tai khoi sinh ra no)
        self._out_pin_pos = {}
        self._block_centers = []
        for b in self.sh.blocks:
            if getattr(b, "box", None):
                xl, yb, xr, yt = b.box
                self._block_centers.append(((self.sx(xl) + self.sx(xr)) / 2,
                                            (self.sy(yb) + self.sy(yt)) / 2))
            for pin in getattr(b, "pins", []):
                if len(pin) > 5 and pin[2] and pin[5]:      # is_out va co net
                    self._out_pin_pos[pin[5]] = (self.sx(pin[0]), self.sy(pin[1]))
        self._wires()
        self._blocks()
        self._terminals()
        self._texts()
        self._frame()
        if self._sim_on() and getattr(self, "sim_dyn", None):
            self._sim_dyn_badges()
        r = self.itemsBoundingRect()
        self.setSceneRect(r.adjusted(-40, -40, 40, 40))

    # --- day noi theo hinh hoc goc ---
    def _wires(self):
        for w in self.sh.wires:
            if self._sim_on() and getattr(w, "signalid", None):
                wc, ww = self._sim_wire_pen(w.signalid)
                wpen = QPen(wc, ww)
            else:
                wpen = QPen(COL_WIRE, 1.1)
            for poly in w.polylines:
                if len(poly) < 2:
                    continue
                path = QPainterPath(QPointF(self.sx(poly[0][0]), self.sy(poly[0][1])))
                for (x, y) in poly[1:]:
                    path.lineTo(self.sx(x), self.sy(y))
                it = self.addPath(path, wpen)
                it.setZValue(-2)
            if w.signalid and w.signalid[:1] == "a" and w.polylines:
                pl = max(w.polylines, key=len)
                mx, my = pl[len(pl) // 2]
                t = self.addText(w.signalid, QFont("Segoe UI", 10))
                t.setDefaultTextColor(COL_NET)
                t.setPos(self.sx(mx) - 6, self.sy(my) - 16)
            # mo phong: hien gia tri / diem nhap TREN DAY cho net NOI BO (khong o mep)
            if self._sim_on() and w.signalid and w.polylines \
                    and w.signalid not in self._term_lids:
                self._wire_value(w.signalid, w.polylines)

    def _wire_value(self, net, polylines):
        isin = net in self.sim_inputs                 # net noi bo NHUNG la dau vao -> cho nhap
        v = self.sim_values.get(net) if self.sim_values else None
        analog = self.sim_kind.get(net) == "A"
        if not isin and not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            return                                    # khong phai dau vao & chua co gia tri -> bo qua
        if analog:
            has = isinstance(v, (int, float)) and not isinstance(v, bool)
            txt = ("✎ %g" % v) if (isin and has) else ("✎ ?" if isin else "%g" % v)
            col = QColor("#7C3AED")
        else:
            vs = "1" if v == 1 else ("0" if v == 0 else "?")
            if not isin and vs == "?":
                return
            txt = ("▸ " + vs) if isin else vs
            col = QColor("#16A34A") if v == 1 else (QColor("#DC2626") if v == 0 else QColor("#94A3B8"))
        # dat nhan ngay tai NGO RA cua khoi sinh ra net nay (neu biet)
        if net in self._out_pin_pos:
            px, py = self._out_pin_pos[net]
            bx, by = px + 6, py - 8
        else:
            # du phong: dinh day gan tam khoi nhat
            pts = [(self.sx(x), self.sy(y)) for poly in polylines for (x, y) in poly]
            if self._block_centers and pts:
                def d2near(px, py):
                    return min((px - cx) ** 2 + (py - cy) ** 2 for cx, cy in self._block_centers)
                px, py = min(pts, key=lambda p: d2near(p[0], p[1]))
            else:
                pl = max(polylines, key=len)
                mx, my = pl[len(pl) // 2]
                px, py = self.sx(mx), self.sy(my)
            bx, by = px + 4, py - 18
        w = 13 + 8 * len(txt)
        r = self.addRect(bx - 2, by, w, 17, QPen(col, 1.4 if isin else 1.0), QBrush(QColor("white")))
        r.setZValue(5)
        tt = self.addText(txt, QFont("Segoe UI", 11, QFont.Weight.Bold))
        tt.setDefaultTextColor(col); tt.setPos(bx, by - 3); tt.setZValue(6)
        if isin:
            self._sim_wire_hits.append((QRectF(bx - 2, by, w, 17), net))

    # --- khoi (dung box + vi tri chan CHUAN theo macro) ---
    def _blocks(self):
        for b in self.sh.blocks:
            if self.svg_mode and self._block_symbol(b):
                continue
            if b.box:
                self._block_real(b)
            else:
                self._block_fallback(b)

    def _block_symbol(self, b):
        """Ve khoi bang bo ky hieu rieng (native). Tra False neu khong co -> fallback."""
        if not getattr(b, "box", None):
            return False
        sh = _symbol_shapes().get(getattr(b, "sym", ""))
        if not sh:
            return False
        try:
            xl, yb, xr, yt = b.box
            left, top = self.sx(xl), self.sy(yt)
            wpx, hpx = (xr - xl) * SC, (yt - yb) * SC
            if wpx <= 1 or hpx <= 1:
                return False

            def X(v):
                return left + v * SC

            def Y(v):
                return top + v * SC

            # nen trang che day (KHONG vien, KHONG tint)
            self.addRect(left, top, wpx, hpx, QPen(Qt.PenStyle.NoPen), QBrush(QColor("white")))
            pen = QPen(COL_SYM, 1.4)
            blk = QBrush(COL_SYM)
            nob = QBrush(Qt.BrushStyle.NoBrush)
            for x1, y1, x2, y2 in sh.get("lines", []):
                self.addLine(X(x1), Y(y1), X(x2), Y(y2), pen)
            for x, y, w, h, fl in sh.get("rects", []):
                self.addRect(X(x), Y(y), w * SC, h * SC, pen, blk if fl else nob)
            for cx, cy, r, fl in sh.get("circles", []):
                self.addEllipse(X(cx - r), Y(cy - r), 2 * r * SC, 2 * r * SC, pen, blk if fl else nob)
            for tx in sh.get("texts", []):
                x, y, size = tx[0], tx[1], tx[2]
                txt, col = tx[3], (tx[4] if len(tx) > 4 else "#000000")
                ps = max(5, int(size * SC))
                fnt = QFont("Segoe UI")
                fnt.setPixelSize(ps)
                it = self.addText(str(txt), fnt)
                cc = COL_SYM if (not col or col.lower() in ("#000000", "#000", "black")) else QColor(col)
                it.setDefaultTextColor(cc)
                it.setPos(X(x) - 2, Y(y) - ps)
            self._block_hits.append((QRectF(left, top, wpx, hpx), b.code, b.name, b.bid))
            # phu chu (giu nhu che do o): tag KKS + mo ta + nhan vi tri + tham so + exec
            if b.tag:
                tg = self.addText(str(b.tag), QFont("Segoe UI", 11, QFont.Weight.Bold))
                tg.setDefaultTextColor(COL_RED); tg.setPos(left, top - 60)
                if b.tdes:
                    td = self.addText(str(b.tdes)[:26], QFont("Segoe UI", 10))
                    td.setDefaultTextColor(QColor("#444")); td.setPos(left, top - 39)
            plc = sh.get("params")
            if plc:
                # dat gia tri that vao DUNG o placeholder cua ky hieu
                pm = getattr(b, "parammap", {}) or {}
                for x, y, size, n in plc:
                    val = pm.get(n)
                    if not val:
                        continue
                    # tranh lap: mã KKS + mo ta da hien mau DO/xam o tren
                    if b.tag and str(val).strip() in (str(b.tag).strip(), str(b.tdes).strip()):
                        continue
                    ps = max(7, int(size * SC))
                    fnt = QFont("Segoe UI"); fnt.setPixelSize(ps)
                    it = self.addText(str(val)[:12], fnt)
                    it.setDefaultTextColor(COL_SYM); it.setPos(X(x) - 2, Y(y) - ps)
            else:
                if b.label:
                    lb = self.addText(str(b.label), QFont("Segoe UI", 10))
                    lb.setDefaultTextColor(COL_TXT); lb.setPos(left, top - 18)
                yy = top + hpx + 2
                for pv in b.params[:4]:
                    pt = self.addText(str(pv)[:14], QFont("Segoe UI", 10))
                    pt.setDefaultTextColor(QColor("#333")); pt.setPos(left, yy); yy += 13
            if b.exorder >= 0:
                eo = self.addText("%02d" % b.exorder, QFont("Segoe UI", 11, QFont.Weight.Bold))
                eo.setDefaultTextColor(COL_RED); eo.setPos(left + wpx - 18, top + hpx - 1)
            return True
        except Exception:
            return False

    def _block_real(self, b):
        xl, yb, xr, yt = b.box
        left, top = self.sx(xl), self.sy(yt)
        right, bot = self.sx(xr), self.sy(yb)
        w, h = right - left, bot - top
        self.addRect(left, top, w, h, QPen(COL_BLK, 1.1), QBrush(COL_BODY))
        self._block_hits.append((QRectF(left, top, w, h), b.code, b.name, b.bid))
        self.addRect(left, top, w, 18, QPen(Qt.PenStyle.NoPen), QBrush(COL_BLK))
        tl = self.addText(str(b.name)[:16], QFont("Segoe UI", 11, QFont.Weight.Bold))
        tl.setDefaultTextColor(QColor("white")); tl.setPos(left + 2, top - 1)
        if b.tag:
            tg = self.addText(str(b.tag), QFont("Segoe UI", 11, QFont.Weight.Bold))
            tg.setDefaultTextColor(COL_RED); tg.setPos(left, top - 60)
            if b.tdes:
                td = self.addText(str(b.tdes)[:26], QFont("Segoe UI", 10))
                td.setDefaultTextColor(QColor("#444")); td.setPos(left, top - 39)
        if b.label:
            lb = self.addText(str(b.label), QFont("Segoe UI", 10))
            lb.setDefaultTextColor(COL_TXT); lb.setPos(left, top - 18)
        if b.exorder >= 0:
            eo = self.addText("%02d" % b.exorder, QFont("Segoe UI", 11, QFont.Weight.Bold))
            eo.setDefaultTextColor(COL_RED); eo.setPos(right - 18, bot - 1)
        yy = bot + 2
        for pv in b.params[:4]:
            pt = self.addText(str(pv)[:14], QFont("Segoe UI", 10))
            pt.setDefaultTextColor(QColor("#333")); pt.setPos(left, yy); yy += 13
        for pin in b.pins:
            px, py, is_out, name = pin[0], pin[1], pin[2], pin[3]
            conn = pin[4] if len(pin) > 4 else True
            sxp, syp = self.sx(px), self.sy(py)
            fill = COL_BLK if conn else QColor("#c8ccd4")
            r = 2.6 if conn else 1.8
            self.addEllipse(sxp - r, syp - r, 2 * r, 2 * r, QPen(COL_BLK, 0.7), QBrush(fill))
            if name:
                f = QFont("Segoe UI", 10)
                col = COL_TXT if conn else QColor("#9098a6")
                if is_out:
                    tt = self.addText(str(name)[:10], f)
                    tt.setDefaultTextColor(col)
                    tt.setPos(sxp - 6 - 7.2 * len(str(name)[:10]) * 0.62, syp - 8)
                else:
                    tt = self.addText(str(name)[:12], f)
                    tt.setDefaultTextColor(col); tt.setPos(sxp + 5, syp - 8)

    def _block_fallback(self, b):
        x0, y0 = self.sx(b.x), self.sy(b.y)
        w, h = 9 * SC, 6 * SC
        self.addRect(x0, y0, w, h, QPen(COL_BLK, 1.1), QBrush(COL_BODY))
        self._block_hits.append((QRectF(x0, y0, w, h), b.code, b.name, b.bid))
        self.addRect(x0, y0, w, 18, QPen(Qt.PenStyle.NoPen), QBrush(COL_BLK))
        tl = self.addText(str(b.name)[:12], QFont("Segoe UI", 11, QFont.Weight.Bold))
        tl.setDefaultTextColor(QColor("white")); tl.setPos(x0 + 2, y0 - 1)
        if b.exorder >= 0:
            eo = self.addText("%02d" % b.exorder, QFont("Segoe UI", 11, QFont.Weight.Bold))
            eo.setDefaultTextColor(COL_RED); eo.setPos(x0 + w - 18, y0 + h - 1)

    # --- terminal 2 mep dang cot (cat chu vua o de khong tran) ---
    def _cell(self, x0, w, y, text, clickable=False, wrap=False, bg=None, fg=None):
        bold = clickable or (fg is not None)
        font = QFont("Segoe UI", 11, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        t = self.addText("", font)
        t.setDefaultTextColor(fg if fg is not None else (COL_NET if clickable else COL_TXT))
        if wrap:                              # ten dai -> tu xuong dong
            t.setTextWidth(w - 8)
            t.setPlainText(str(text))
        else:                                 # gia tri ngan -> cat vua o
            fm = QFontMetrics(font)
            t.setPlainText(fm.elidedText(str(text), Qt.TextElideMode.ElideRight, int(w - 8)))
        th = max(20, t.boundingRect().height() + 2)
        rect = self.addRect(x0, y - 10, w, th, QPen(COL_GRID, 1),
                            QBrush(bg if bg is not None else QColor("white")))
        rect.setZValue(-1)                    # dua khung ra SAU chu
        t.setPos(x0 + 3, y - 11)
        return th

    def _sim_lid_cell(self, x0, w, y, t, isin, bg):
        """O LID khi mo phong: GIA TRI (to, mau tim) o tren, dia chi LID o duoi."""
        net = t.lid
        kind = self.sim_kind.get(net)
        if kind == "A":
            # gia tri analog: uu tien gia tri TINH RA (sim_values), roi toi gia tri nguoi nhap
            av = self.sim_values.get(net) if self.sim_values else None
            if not isinstance(av, (int, float)):
                av = self.sim_analog.get(net)
            vs = ("%g" % av) if isinstance(av, (int, float)) else "~"
            mk = "✎ " if isin else ""
        else:
            v = self.sim_values.get(net) if self.sim_values else None
            vs = "1" if v == 1 else ("0" if v == 0 else "?")
            mk = "▸ " if isin else ""
        th = 42
        rect = self.addRect(x0, y - 10, w, th, QPen(COL_GRID, 1),
                            QBrush(bg if bg is not None else QColor("white")))
        rect.setZValue(-1)
        vf = QFont("Segoe UI", 14, QFont.Weight.Bold)
        tv = self.addText(mk + vs, vf)
        tv.setDefaultTextColor(QColor("#7C3AED"))     # tim
        tv.setPos(x0 + 3, y - 12)
        lf = QFont("Segoe UI", 9)
        fm = QFontMetrics(lf)
        tl = self.addText(fm.elidedText(str(net), Qt.TextElideMode.ElideRight, int(w - 8)), lf)
        tl.setDefaultTextColor(COL_TXT)
        tl.setPos(x0 + 3, y + 12)
        return th

    def _refcell(self, x0, w, y, refs, clickable=False):
        rows = refs or [""]
        h = max(20, 14 * len(rows) + 6)
        self.addRect(x0, y - 10, w, h, QPen(COL_GRID, 1), QBrush(QColor("white")))
        font = QFont("Segoe UI", 11, QFont.Weight.Bold if clickable else QFont.Weight.Normal)
        fm = QFontMetrics(font)
        yy = y - 11
        for r in rows:
            txt = fm.elidedText(str(r), Qt.TextElideMode.ElideRight, int(w - 8))
            t = self.addText(txt, font)
            t.setDefaultTextColor(COL_NET if clickable else COL_TXT)
            t.setPos(x0 + 3, yy); yy += 14
        return h

    def _terminals(self):
        simon = self._sim_on()
        for t in self.sh.terms:
            y = self.sy(t.y)
            has = bool(t.targets) or bool(getattr(t, "xcpu", None))
            # mau mo phong cho o ten tin hieu
            bg = fg = None
            isin = simon and t.lid in self.sim_inputs
            if simon and t.lid:
                bg, fg = self._sim_cell_col(t.lid)
            if t.side == "L":
                ch = self._refcell(250, 80, y, t.refs, clickable=has)
                lh = self._cell(0, 250, y, t.linename, wrap=True, bg=bg, fg=fg)
                if simon and t.lid:
                    self._sim_lid_cell(330, 110, y, t, isin, bg)
                else:
                    self._cell(330, 110, y, t.lid, clickable=has, bg=bg, fg=fg)
                rct = QRectF(0, y - 10, MARGIN_L, max(ch, lh, 20))
                if has:
                    self._hits.append((rct, t))
            else:
                x0 = self._right_x0
                ch = self._refcell(x0 + 90, 80, y, t.refs, clickable=has)
                if simon and t.lid:
                    self._sim_lid_cell(x0, 90, y, t, isin, bg)
                else:
                    self._cell(x0, 90, y, t.lid, clickable=has, bg=bg, fg=fg)
                lh = self._cell(x0 + 180, 260, y, t.linename, wrap=True, bg=bg, fg=fg)
                rct = QRectF(x0, y - 10, MARGIN_R, max(ch, lh, 20))
                if has:
                    self._hits.append((rct, t))
            if t.lid:
                self._term_hits.append((rct, t.lid, t.linename))


    def _texts(self):
        for tx in self.sh.texts:
            it = self.addText(tx.s, QFont("Segoe UI", 10))
            it.setDefaultTextColor(QColor("#555"))
            it.setPos(self.sx(tx.x), self.sy(tx.y))

    def _frame(self):
        top = MARGIN_T - 38
        rx = self._right_x0
        bot = self.sy(self.sh.ymin) + 30
        heads = [(0, "Line Name"), (255, "From"), (335, "LID"),
                 (MARGIN_L + 20, "Logic Chart"),
                 (rx, "LID"), (rx + 95, "To"), (rx + 185, "Line Name")]
        for x, s in heads:
            h = self.addText(s, QFont("Segoe UI", 13, QFont.Weight.Bold))
            h.setDefaultTextColor(COL_TXT); h.setPos(x + 2, top)
        for xx in [0, MARGIN_L, rx, rx + MARGIN_R]:
            self.addLine(xx, top + 22, xx, bot, QPen(COL_GRID, 1))
        self.addLine(0, top + 20, rx + MARGIN_R, top + 20, QPen(COL_GRID, 1))
        info = "%s-%s   %s   [%s]" % (self.sh.pa, self.sh.sheetno, self.sh.title, self.sh.drawno)
        ti = self.addText(info, QFont("Segoe UI", 13, QFont.Weight.Bold))
        ti.setDefaultTextColor(COL_TXT); ti.setPos(rx, bot + 6)

    def _sim_dyn_badges(self):
        """Danh dau khoi DONG (tich phan...) + in TI va gia tri hien tai ngay tren khoi."""
        orange = QColor("#EA580C")
        for rect, code, name, bid in self._block_hits:
            info = self.sim_dyn.get(bid)
            if not info:
                continue
            # vien cam quanh khoi dong
            fr = self.addRect(rect.adjusted(-2, -2, 2, 2), QPen(orange, 2.0), QBrush(Qt.BrushStyle.NoBrush))
            fr.setZValue(7)
            ti = info.get("ti")
            outv = self.sim_values.get(info.get("out")) if self.sim_values else None
            vs = ("%g" % outv) if isinstance(outv, (int, float)) and not isinstance(outv, bool) else "?"
            pstr = ("%g" % ti) if ti is not None else "?"
            k = info.get("kind")
            if k == "D":
                txt = "d/dt  G=%s  y=%s" % (pstr, vs)
            elif k == "L":
                txt = "F(t)  T=%s  y=%s" % (pstr, vs)
            else:
                txt = "∫ I  TI=%s  y=%s" % (pstr, vs)
            bx, by = rect.left(), rect.top() - 17
            r = self.addRect(bx, by, 16 + 7 * len(txt), 16, QPen(orange, 1.0), QBrush(QColor("#FFF7ED")))
            r.setZValue(7)
            t = self.addText(txt, QFont("Segoe UI", 10, QFont.Weight.Bold))
            t.setDefaultTextColor(orange); t.setPos(bx + 2, by - 3); t.setZValue(8)

    def block_at(self, sp):
        """Tra ve (code, name) cua khoi tai vi tri sp, hoac None."""
        for rect, code, name, bid in self._block_hits:
            if rect.contains(sp):
                return (code, name, bid)
        return None

    def term_at(self, sp):
        """Tra ve (net, linename) cua terminal/tin hieu tai vi tri sp, hoac None."""
        for rect, net, linename in self._term_hits:
            if rect.contains(sp):
                return (net, linename)
        return None

    def click_at(self, sp):
        """Xu ly 1 cu click tai vi tri scene sp (ZoomView goi khi bam trai khong keo)."""
        # che do mo phong: click dau vao -> digital doi 0/1, analog nhap so
        if self._sim_on():
            hit = self.term_at(sp)
            net = hit[0] if (hit and hit[0] in self.sim_inputs) else None
            if net is None:                        # thu diem settable NOI BO tren day
                for rect, n in getattr(self, "_sim_wire_hits", []):
                    if rect.contains(sp):
                        net = n; break
            if net is not None and net in self.sim_inputs:
                if self.sim_kind.get(net) == "A":
                    if self.on_sim_set_analog:
                        self.on_sim_set_analog(net)
                        return
                elif self.on_sim_toggle:
                    self.on_sim_toggle(net)
                    return
            # click khoi DONG (cam) -> cai dat TI / gia tri dau
            if self.sim_dyn and self.on_sim_dyn_config:
                for rect, code, name, bid in self._block_hits:
                    if bid in self.sim_dyn and rect.contains(sp):
                        self.on_sim_dyn_config(bid)
                        return
        for rect, t in self._hits:
            if rect.contains(sp) and self.on_navigate:
                self.on_navigate(t)
                return
        # click khoi F(x) -> xem bang x-y
        for rect, code, name, bid in self._block_hits:
            if rect.contains(sp) and code in getattr(self, "func_codes", set()) \
                    and self.on_func_view:
                self.on_func_view(bid, name)
                return
        for rect, code, name, bid in self._block_hits:
            if rect.contains(sp) and self.on_block_click:
                self.on_block_click(code, name)
                return

    def mousePressEvent(self, ev):
        is_left = ev.button() == Qt.MouseButton.LeftButton
        if is_left:
            self.click_at(ev.scenePos())
        super().mousePressEvent(ev)
