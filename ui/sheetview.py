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
COL_BLK = QColor("#33415c")
COL_BODY = QColor("#f5f7fa")
COL_WIRE = QColor("#4a5a75")
COL_GRID = QColor("#c0c8d4")
COL_RED = QColor("#c00000")
COL_NET = QColor("#1560b0")
COL_TXT = QColor("#12305a")


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
        self.svg_mode = False        # True = ve ky hieu SVG giong PDF
        self.build()

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
        self._wires()
        self._blocks()
        self._terminals()
        self._texts()
        self._frame()
        r = self.itemsBoundingRect()
        self.setSceneRect(r.adjusted(-40, -40, 40, 40))

    # --- day noi theo hinh hoc goc ---
    def _wires(self):
        for w in self.sh.wires:
            for poly in w.polylines:
                if len(poly) < 2:
                    continue
                path = QPainterPath(QPointF(self.sx(poly[0][0]), self.sy(poly[0][1])))
                for (x, y) in poly[1:]:
                    path.lineTo(self.sx(x), self.sy(y))
                it = self.addPath(path, QPen(COL_WIRE, 1.1))
                it.setZValue(-2)
            if w.signalid and w.signalid[:1] == "a" and w.polylines:
                pl = max(w.polylines, key=len)
                mx, my = pl[len(pl) // 2]
                t = self.addText(w.signalid, QFont("Segoe UI", 10))
                t.setDefaultTextColor(COL_NET)
                t.setPos(self.sx(mx) - 6, self.sy(my) - 16)

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

            # nen trang che day (KHONG vien) - de ky hieu tu ve khung cua no
            self.addRect(left, top, wpx, hpx, QPen(Qt.PenStyle.NoPen), QBrush(QColor("white")))
            pen = QPen(QColor("#111827"), 1.0)
            blk = QBrush(QColor("#111827"))
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
                it.setDefaultTextColor(QColor(col or "#000000"))
                it.setPos(X(x) - 2, Y(y) - ps)
            self._block_hits.append((QRectF(left, top, wpx, hpx), b.code, b.name))
            if b.tag:
                tg = self.addText(str(b.tag), QFont("Segoe UI", 11, QFont.Weight.Bold))
                tg.setDefaultTextColor(COL_RED); tg.setPos(left, top - 40)
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
        self._block_hits.append((QRectF(left, top, w, h), b.code, b.name))
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
        self._block_hits.append((QRectF(x0, y0, w, h), b.code, b.name))
        self.addRect(x0, y0, w, 18, QPen(Qt.PenStyle.NoPen), QBrush(COL_BLK))
        tl = self.addText(str(b.name)[:12], QFont("Segoe UI", 11, QFont.Weight.Bold))
        tl.setDefaultTextColor(QColor("white")); tl.setPos(x0 + 2, y0 - 1)
        if b.exorder >= 0:
            eo = self.addText("%02d" % b.exorder, QFont("Segoe UI", 11, QFont.Weight.Bold))
            eo.setDefaultTextColor(COL_RED); eo.setPos(x0 + w - 18, y0 + h - 1)

    # --- terminal 2 mep dang cot (cat chu vua o de khong tran) ---
    def _cell(self, x0, w, y, text, clickable=False, wrap=False):
        font = QFont("Segoe UI", 11, QFont.Weight.Bold if clickable else QFont.Weight.Normal)
        t = self.addText("", font)
        t.setDefaultTextColor(COL_NET if clickable else COL_TXT)
        if wrap:                              # ten dai -> tu xuong dong
            t.setTextWidth(w - 8)
            t.setPlainText(str(text))
        else:                                 # gia tri ngan -> cat vua o
            fm = QFontMetrics(font)
            t.setPlainText(fm.elidedText(str(text), Qt.TextElideMode.ElideRight, int(w - 8)))
        th = max(20, t.boundingRect().height() + 2)
        rect = self.addRect(x0, y - 10, w, th, QPen(COL_GRID, 1), QBrush(QColor("white")))
        rect.setZValue(-1)                    # dua khung ra SAU chu
        t.setPos(x0 + 3, y - 11)
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
        for t in self.sh.terms:
            y = self.sy(t.y)
            has = bool(t.targets) or bool(getattr(t, "xcpu", None))
            if t.side == "L":
                ch = self._refcell(250, 80, y, t.refs, clickable=has)
                lh = self._cell(0, 250, y, t.linename, wrap=True)
                self._cell(330, 110, y, t.lid, clickable=has)
                if has:
                    self._hits.append((QRectF(0, y - 10, MARGIN_L, max(ch, lh, 20)), t))
            else:
                x0 = self._right_x0
                ch = self._refcell(x0 + 90, 80, y, t.refs, clickable=has)
                self._cell(x0, 90, y, t.lid, clickable=has)
                lh = self._cell(x0 + 180, 260, y, t.linename, wrap=True)
                if has:
                    self._hits.append((QRectF(x0, y - 10, MARGIN_R, max(ch, lh, 20)), t))

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

    def block_at(self, sp):
        """Tra ve (code, name) cua khoi tai vi tri sp, hoac None."""
        for rect, code, name in self._block_hits:
            if rect.contains(sp):
                return (code, name)
        return None

    def click_at(self, sp):
        """Xu ly 1 cu click tai vi tri scene sp (ZoomView goi khi bam trai khong keo)."""
        for rect, t in self._hits:
            if rect.contains(sp) and self.on_navigate:
                self.on_navigate(t)
                return
        for rect, code, name in self._block_hits:
            if rect.contains(sp) and self.on_block_click:
                self.on_block_click(code, name)
                return

    def mousePressEvent(self, ev):
        self.click_at(ev.scenePos())
        super().mousePressEvent(ev)
