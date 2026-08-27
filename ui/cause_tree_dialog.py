# -*- coding: utf-8 -*-
"""SO DO LOGIC NGUYEN NHAN (chi tiet cho 1 tin hieu dich trong Ma tran nhan qua).

Ma tran (bang) tra loi "nhung gi gay ra tin hieu nay" cho NHIEU tin hieu dich cung
luc - tot de so sanh va lam tai lieu. Cua so nay bu phan con thieu: CAU TRUC - cai
gi long trong cai gi, nhom nao la AND (phai du ca nhom), nhanh nao bi phu dinh, chot
SR o dau. Ve theo kieu ban ve goc: tin hieu di tu TRAI (nguyen nhan) sang PHAI (dich).

Du lieu lay tu core/ce_matrix.expand_full() - dung cay ma ma tran dang dung, khong
tinh lai gi khac, nen bang va so do luon khop nhau.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QGraphicsScene, QGraphicsView, QCheckBox, QLineEdit)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPainterPath, QFontMetrics

COL_GATE = QColor("#1D4ED8")
COL_LEAF = QColor("#0F172A")
COL_WIRE = QColor("#64748B")
COL_HL = QColor("#DC2626")          # duong dan toi nguyen nhan dang chon
COL_CMP = QColor("#B45309")
COL_CROSS = QColor("#7C3AED")

NODE_H = 26
V_GAP = 18        # chua du cho dong chu nho "CPU / sheet" duoi moi o
H_GAP = 60        # khoang HO giua 2 cot (be rong moi cot tinh theo o rong nhat trong cot)
LEAF_W = 260
GATE_W = 62
MAX_NODES = 700                      # tran an toan (cay MFT day co the vai tram node)


def prune_to(node, want):
    """Cat cay chi giu NHANH DAN TOI nguyen nhan `want` (va cac anh em AND cua no -
    vi de hieu 'tai sao', phai thay ca nhung dieu kien PHAI KEM THEO). Tra None neu
    nhanh nay khong dan toi dau. Cay MFT day co the 400+ khoi - cat nhu vay con vai
    chuc, doc duoc bang mat."""
    if not node or not want:
        return None
    lb = (node.get("label") or node.get("net") or "").strip().upper()
    if lb and (want == lb or want.startswith(lb + " ")):
        return node                       # den dich - giu nguyen ca nhanh con
    ch = node.get("children") or []
    kept = []
    for c in ch:
        k = prune_to(c, want)
        if k is not None:
            kept.append(k)
    if not kept:
        return None
    out = dict(node)
    if node.get("op") == "AND":
        # nhom AND: giu ca cac dieu kien di kem, nhung thu gon (khong mo tiep ben duoi)
        sib = []
        for c in ch:
            if any(c is k for k in kept):
                continue
            s = dict(c)
            s["children"] = []
            s["_folded"] = bool(c.get("children"))
            sib.append(s)
        out["children"] = kept + sib
    else:
        out["children"] = kept
    return out


class DnfScene(QGraphicsScene):
    """So do GON: DICH = A hoac B hoac (C va D) ... - dung cach doc mach bao ve.
    Cot trai = cac dieu kien; nhom AND duoc gom lai bang 1 khoi AND rieng; tat ca do
    ve 1 khoi OR duy nhat roi ra tin hieu dich."""

    ROW_H = 30
    GRP_GAP = 16
    T_W = 420                    # be rong o dieu kien

    def __init__(self, products, target, highlight=None):
        super().__init__()
        self.products = products
        self.target = target
        self.hl = (highlight or "").strip().upper()
        self.on_jump = None
        self._hits = []
        self._cpu_names = {}
        self.build()

    def _cpu_name(self, node):
        db = node.get("db")
        if not db:
            return ""
        if db not in self._cpu_names:
            try:
                from core import dbreader as D
                m = D.db_meta(db)
                self._cpu_names[db] = m.get("cpuname") or ("CPU%s" % m.get("cpuno"))
            except Exception:
                self._cpu_names[db] = ""
        return self._cpu_names[db]

    def _is_hl(self, node):
        if not self.hl:
            return False
        from core import ce_matrix as CE
        lb = (CE.term_label(node) or "").strip().upper()
        raw = (node.get("label") or node.get("net") or "").strip().upper()
        return (self.hl == lb or self.hl == raw
                or (raw and self.hl.startswith(raw + " ")))

    def build(self):
        self.clear()
        self._hits = []
        from core import ce_matrix as CE
        x_term = 0.0
        x_and = x_term + self.T_W + 70
        x_or = x_and + 90
        x_tgt = x_or + 110

        y = 0.0
        or_pts = []
        for prod in self.products:
            hl_prod = any(self._is_hl(n) for n in prod)
            ys = []
            for n in prod:
                self._term(x_term, y, n, hl_prod and self._is_hl(n), hl_prod)
                ys.append(y)
                y += self.ROW_H
            y += self.GRP_GAP
            if len(prod) == 1:
                or_pts.append((x_term + self.T_W, ys[0], hl_prod))
            else:
                ymid = (ys[0] + ys[-1]) / 2.0
                self._gate(x_and, ymid, "AND", hl_prod, w=54,
                           tip="Phai du CA %d dieu kien nay" % len(prod))
                for yy in ys:
                    self._wire(x_term + self.T_W, yy, x_and, ymid, hl_prod)
                or_pts.append((x_and + 54, ymid, hl_prod))

        if not or_pts:
            self.setSceneRect(QRectF(0, 0, 400, 100))
            return
        ymid = (or_pts[0][1] + or_pts[-1][1]) / 2.0
        self._gate(x_or, ymid, "OR", False, w=64,
                   tip="Chi can 1 trong cac nhanh ben trai")
        for (px, py, h) in or_pts:
            self._wire(px, py, x_or, ymid, h)
        self._term(x_tgt, ymid, self.target, False, True, is_target=True)
        r = self.itemsBoundingRect()
        self.setSceneRect(r.adjusted(-40, -40, 40, 40))

    def _wire(self, x1, y1, x2, y2, hl):
        pen = QPen(COL_HL if hl else COL_WIRE, 2.0 if hl else 1.2)
        mid = (x1 + x2) / 2.0
        p = QPainterPath(QPointF(x1, y1))
        p.lineTo(mid, y1); p.lineTo(mid, y2); p.lineTo(x2, y2)
        it = self.addPath(p, pen); it.setZValue(-1)

    def _gate(self, x, y, txt, hl, w=60, tip=""):
        rect = QRectF(x, y - 13, w, 26)
        it = self.addRect(rect, QPen(COL_HL if hl else COL_GATE, 2.2 if hl else 1.6),
                          QBrush(QColor("#EFF6FF")))
        if tip:
            it.setToolTip(tip)
        t = self.addText(txt, QFont("Segoe UI", 9, QFont.Weight.Bold))
        t.setDefaultTextColor(COL_HL if hl else COL_GATE)
        br = t.boundingRect()
        t.setPos(x + (w - br.width()) / 2, y - br.height() / 2)

    def _term(self, x, y, node, hl, in_hl_group, is_target=False):
        from core import ce_matrix as CE
        lb = CE.term_label(node) if not is_target else str(node)
        col = COL_LEAF
        if not is_target:
            if node.get("type") == "cmp":
                col = COL_CMP
            elif node.get("kind") == "cross":
                col = COL_CROSS
        f = QFont("Segoe UI", 9, QFont.Weight.Bold if (hl or is_target) else QFont.Weight.Normal)
        fm = QFontMetrics(f)
        w = self.T_W if not is_target else 260
        txt = fm.elidedText(str(lb), Qt.TextElideMode.ElideRight, w - 108)
        rect = QRectF(x, y - 13, w, 26)
        pen = QPen(COL_HL if hl else (COL_GATE if is_target else QColor("#CBD5E1")),
                   2.2 if (hl or is_target) else 1.0)
        bg = QColor("#FEF2F2") if hl else (QColor("#EFF6FF") if is_target
                                           else (QColor("#FFFBEB") if in_hl_group else QColor("white")))
        it = self.addRect(rect, pen, QBrush(bg))
        it.setToolTip(str(lb))
        t = self.addText(txt, f)
        t.setDefaultTextColor(COL_HL if hl else col)
        t.setPos(x + 6, y - t.boundingRect().height() / 2)
        if not is_target:
            src = node.get("sheetlbl") or ""
            cpu = self._cpu_name(node)
            if src or cpu:
                # dat BEN TRONG o, canh phai - de ngoai se de len duong day
                sf = QFont("Segoe UI", 7)
                stxt = ("%s / %s" % (cpu, src)).strip(" /")
                sw = QFontMetrics(sf).horizontalAdvance(stxt)
                s = self.addText(stxt, sf)
                s.setDefaultTextColor(COL_WIRE)
                s.setPos(x + w - sw - 8, y - s.boundingRect().height() / 2)
                s.setZValue(2)
            self._hits.append((rect, node))

    def click_at(self, sp):
        for rect, node in self._hits:
            if rect.contains(sp):
                if self.on_jump and node.get("db") and node.get("sheet") is not None:
                    self.on_jump(node["db"], node["sheet"])
                return


class LayerScene(QGraphicsScene):
    """SO DO THEO LOP: nguyen nhan goc (trai) -> tin hieu lien quan (giua) -> dich (phai).

    Hai che do cu deu bo mat mot nua cau chuyen:
      - "Day du" ve nguyen mach: 448 khoi / 30 tang cho MFT, khong doc noi bang mat.
      - "Gon (DNF)" dep het tang giua: con 64 nhanh nguyen nhan goc phang li - thay
        "FURN PRS HI HI" nhung KHONG biet no thuoc nhom nao, vao dich qua duong nao.
    Che do nay giu CA HAI: moi nguyen nhan goc van nam duoi TIN HIEU CO TEN da gom no
    lai. Lop 1 + lop 2 cua MFT chi 24 o - vua 1 man hinh.

    Chi ve nhung lop DA MO. O nao con bung duoc co dau [+] ben trai: bam de mo them 1
    lop tai cho, bam [-] de thu lai. O KHONG co dau [+] la NGUYEN NHAN GOC that su
    (tin hieu hien truong, so sanh nguong, hoac tin hieu tu CPU khac chua doc duoc) -
    ve vien xanh la de tach khoi tin hieu trung gian.
    """

    ROW_H = 30
    GRP_GAP = 16
    BOX_W = 340
    STEP = BOX_W + 190           # be rong 1 lop = o + cho dat cong AND/OR
    EXP_W = 18                   # nut [+] / [-]

    def __init__(self, target_disp, products, drill_fn, highlight=None):
        """products: lop 1 dang [[node,...],...] (OR cua cac nhom AND) - dung dang ma
        CE.first_layer() / CE.drill() tra ve. drill_fn(node) -> products cua lop ke tiep."""
        super().__init__()
        self.target = target_disp
        self.drill_fn = drill_fn
        self.hl = (highlight or "").strip().upper()
        self.on_jump = None          # callback(db, sheet)
        self.on_changed = None       # callback() sau khi mo/dong 1 lop
        self._cpu_names = {}
        self.root = {"node": None, "prods": [[self._mk(n) for n in g] for g in products],
                     "open": True, "depth": 0, "y": 0.0, "root_cause": False}
        self.build()

    # ------------------------------------------------------------------ mo hinh
    @staticmethod
    def _mk(node):
        return {"node": node, "prods": None, "open": False, "root_cause": False}

    def _fill(self, item):
        """Doc lop ke tiep cua 1 o (chi lan dau, sau do dung lai ket qua)."""
        if item["prods"] is None:
            try:
                prods = self.drill_fn(item["node"]) or []
            except Exception:
                prods = []
            item["prods"] = [[self._mk(n) for n in g] for g in prods]
            # bung ra rong -> day thuc su la nguyen nhan goc, khong con gi sau nua
            item["root_cause"] = not item["prods"]
        return item["prods"]

    def _toggle(self, item):
        item["open"] = False if item["open"] else bool(self._fill(item))
        self.build()
        if self.on_changed:
            self.on_changed()

    def open_all(self, max_new=40):
        """Mo dong loat moi o dang hien con bung duoc - xem nhanh ca 1 lop sau nua."""
        from core import ce_matrix as CE
        todo = []

        def walk(it):
            for g in (it["prods"] or []) if it["open"] else []:
                for c in g:
                    todo.append(c)
                    walk(c)

        walk(self.root)
        n = 0
        for it in todo:
            if n >= max_new or it["open"] or it["root_cause"]:
                continue
            if not CE.can_drill(it["node"]):
                continue
            if self._fill(it):
                it["open"] = True
                n += 1
        self.build()
        if self.on_changed:
            self.on_changed()
        return n

    def reveal_highlight(self, max_rounds=4):
        """Mo dan cac lop cho toi khi thay nguyen nhan dang to, roi DONG lai nhung
        nhanh khong chua no. Vao tu ma tran (bam 1 o) thi nguyen nhan can xem thuong
        nam sau vai lop - neu chi ve lop 1 thi nguoi dung khong thay gi, phai tu bam
        [+] mo tung o mo mam. Sau khi tim thay chi giu lai duong dan, nen so do van gon."""
        if not self.hl:
            return False
        for _ in range(max_rounds):
            if self._find_hl(self.root):
                self._prune_to_hl(self.root)
                self.build()
                if self.on_changed:
                    self.on_changed()
                return True
            if not self.open_all(max_new=60):
                break
        # khong tim thay -> tra ve dung trang thai ban dau, dung de nguoi dung nhan
        # ca dong bung ra (do thu tim) roi khong hieu vi sao so do bong to ra
        self._close_below(self.root)
        self.build()
        return False

    def _close_below(self, item):
        for g in (item["prods"] or []):
            for c in g:
                c["open"] = False
                self._close_below(c)

    def _find_hl(self, item):
        for g in (item["prods"] or []) if item["open"] else []:
            for c in g:
                if self._is_hl(c["node"]) or self._find_hl(c):
                    return True
        return False

    def _prune_to_hl(self, item):
        """Dong moi nhanh con khong dan toi nguyen nhan dang to (giu nguyen lop 1)."""
        for g in (item["prods"] or []) if item["open"] else []:
            for c in g:
                if self._is_hl(c["node"]):
                    continue
                if self._find_hl(c):
                    self._prune_to_hl(c)
                else:
                    c["open"] = False

    def collapse_all(self):
        def walk(it):
            for g in (it["prods"] or []):
                for c in g:
                    c["open"] = False
                    walk(c)

        walk(self.root)
        self.build()
        if self.on_changed:
            self.on_changed()

    def counts(self):
        """(so o dang ve, so nguyen nhan goc dang hien) - de ghi vao dong trang thai."""
        from core import ce_matrix as CE
        n = [0, 0]

        def walk(it):
            for g in (it["prods"] or []) if it["open"] else []:
                for c in g:
                    n[0] += 1
                    if not c["open"] and (c["root_cause"] or not CE.can_drill(c["node"])):
                        n[1] += 1
                    walk(c)

        walk(self.root)
        return tuple(n)

    # ------------------------------------------------------------------ bo tri
    def build(self):
        self.clear()
        self._hits = []          # (rect, node) -> bam de nhay toi sheet nguon
        self._exp = []           # (rect, item) -> bam de mo/dong lop
        self._y = 0.0
        self._maxd = 0
        self._layout(self.root, 0)
        self._draw(self.root)
        self._captions()
        r = self.itemsBoundingRect()
        self.setSceneRect(r.adjusted(-40, -50, 40, 40))

    def _layout(self, item, depth):
        item["depth"] = depth
        self._maxd = max(self._maxd, depth)
        if item["open"] and item["prods"]:
            gys = []
            for grp in item["prods"]:
                cys = [self._layout(c, depth + 1) for c in grp]
                gys.append(sum(cys) / len(cys))
                self._y += self.GRP_GAP
            item["_gys"] = gys
            item["y"] = (gys[0] + gys[-1]) / 2.0
        else:
            item["y"] = self._y
            self._y += self.ROW_H
        return item["y"]

    def _x(self, depth):
        return -depth * self.STEP

    # ------------------------------------------------------------------ ve
    def _draw(self, item):
        d = item["depth"]
        self._box(self._x(d), item["y"], item, is_target=(item["node"] is None))
        if not (item["open"] and item["prods"]):
            return
        hl_any = self._hl_under(item)
        x_right = self._x(d + 1) + self.BOX_W       # canh phai cua cot con
        x_and = x_right + 25
        x_or = x_and + 54 + 32
        pts = []
        for grp, gy in zip(item["prods"], item["_gys"]):
            for c in grp:
                self._draw(c)
            hl_g = any(self._hl_under(c) for c in grp)
            if len(grp) > 1:
                self._gate(x_and, gy, "AND", hl_g, w=54,
                           tip="Phai du CA %d dieu kien nay moi gay ra o ben phai" % len(grp))
                for c in grp:
                    self._wire(x_right, c["y"], x_and, gy, self._hl_under(c))
                pts.append((x_and + 54, gy, hl_g))
            else:
                pts.append((x_right, grp[0]["y"], hl_g))
        if len(pts) > 1:
            ymid = (pts[0][1] + pts[-1][1]) / 2.0
            self._gate(x_or, ymid, "OR", hl_any, w=54,
                       tip="Chi can 1 trong %d nhanh ben trai" % len(pts))
            for (px, py, h) in pts:
                self._wire(px, py, x_or, ymid, h)
            self._wire(x_or + 54, ymid, self._x(d), item["y"], hl_any)
        else:
            px, py, h = pts[0]
            self._wire(px, py, self._x(d), item["y"], h)

    def _captions(self):
        """Ghi ten tung cot ngay tren dau - de biet dang doc toi lop may."""
        for d in range(self._maxd + 1):
            txt = "TIN HIEU DICH" if d == 0 else "LOP %d" % d
            t = self.addText(txt, QFont("Segoe UI", 8, QFont.Weight.Bold))
            t.setDefaultTextColor(QColor("#94A3B8"))
            t.setPos(self._x(d), -36)

    def _wire(self, x1, y1, x2, y2, hl):
        pen = QPen(COL_HL if hl else COL_WIRE, 2.0 if hl else 1.2)
        mid = (x1 + x2) / 2.0
        p = QPainterPath(QPointF(x1, y1))
        p.lineTo(mid, y1); p.lineTo(mid, y2); p.lineTo(x2, y2)
        it = self.addPath(p, pen); it.setZValue(-1)

    def _gate(self, x, y, txt, hl, w=54, tip=""):
        it = self.addRect(QRectF(x, y - 13, w, 26),
                          QPen(COL_HL if hl else COL_GATE, 2.2 if hl else 1.6),
                          QBrush(QColor("#EFF6FF")))
        if tip:
            it.setToolTip(tip)
        t = self.addText(txt, QFont("Segoe UI", 9, QFont.Weight.Bold))
        t.setDefaultTextColor(COL_HL if hl else COL_GATE)
        br = t.boundingRect()
        t.setPos(x + (w - br.width()) / 2, y - br.height() / 2)

    def _cpu_name(self, node):
        db = node.get("db")
        if not db:
            return ""
        if db not in self._cpu_names:
            try:
                from core import dbreader as D
                m = D.db_meta(db)
                self._cpu_names[db] = m.get("cpuname") or ("CPU%s" % m.get("cpuno"))
            except Exception:
                self._cpu_names[db] = ""
        return self._cpu_names[db]

    def _is_hl(self, node):
        if not self.hl or node is None:
            return False
        from core import ce_matrix as CE
        lb = (CE.term_label(node) or "").strip().upper()
        raw = (node.get("label") or node.get("net") or "").strip().upper()
        return self.hl == lb or self.hl == raw or (raw and self.hl.startswith(raw + " "))

    def _hl_under(self, item):
        if self._is_hl(item.get("node")):
            return True
        for g in (item["prods"] or []) if item["open"] else []:
            if any(self._hl_under(c) for c in g):
                return True
        return False

    def _box(self, x, y, item, is_target=False):
        from core import ce_matrix as CE
        node = item.get("node")
        if is_target:
            lb, col, is_root = str(self.target), COL_GATE, False
        else:
            lb = CE.term_label(node)
            can = item["open"] or bool(item["prods"]) or CE.can_drill(node)
            is_root = item["root_cause"] or not can
            col = COL_LEAF
            if node.get("type") == "cmp" or node.get("kind") == "cmp":
                col = COL_CMP
            elif node.get("kind") == "cross":
                col = COL_CROSS
        hl = False if is_target else self._is_hl(node)
        w = 260 if is_target else self.BOX_W
        f = QFont("Segoe UI", 9,
                  QFont.Weight.Bold if (hl or is_target or is_root) else QFont.Weight.Normal)
        rect = QRectF(x, y - 13, w, 26)
        if is_target:
            pen, bg = QPen(COL_GATE, 2.2), QBrush(QColor("#EFF6FF"))
        elif hl:
            pen, bg = QPen(COL_HL, 2.2), QBrush(QColor("#FEF2F2"))
        elif is_root:
            # NGUYEN NHAN GOC - vien dam mau khac de tach khoi tin hieu trung gian
            pen, bg = QPen(QColor("#0F766E"), 1.8), QBrush(QColor("#F0FDFA"))
        else:
            pen, bg = QPen(QColor("#CBD5E1"), 1.0), QBrush(QColor("white"))
        it = self.addRect(rect, pen, bg)
        fm = QFontMetrics(f)
        t = self.addText(fm.elidedText(str(lb), Qt.TextElideMode.ElideRight, w - 112), f)
        t.setDefaultTextColor(COL_HL if hl else col)
        t.setPos(x + 6, y - t.boundingRect().height() / 2)
        if is_target:
            return
        it.setToolTip(str(lb) + ("\n\nNGUYEN NHAN GOC - khong con gi sau nua."
                                 if is_root else
                                 "\n\nBam [+] ben trai de xem cai gi gay ra tin hieu nay."))
        src = node.get("sheetlbl") or ""
        stxt = ("%s / %s" % (self._cpu_name(node), src)).strip(" /")
        if stxt:
            sf = QFont("Segoe UI", 7)
            sw = QFontMetrics(sf).horizontalAdvance(stxt)
            sitm = self.addText(stxt, sf)
            sitm.setDefaultTextColor(COL_WIRE)
            sitm.setPos(x + w - sw - 8, y - sitm.boundingRect().height() / 2)
            sitm.setZValue(2)
        self._hits.append((rect, node))
        if is_root:
            return
        # nut [+] / [-] ben TRAI o - nguyen nhan nam ben trai, mo ra la no rong sang trai
        ex = QRectF(x - self.EXP_W - 8, y - self.EXP_W / 2.0, self.EXP_W, self.EXP_W)
        b = self.addRect(ex, QPen(COL_GATE, 1.4), QBrush(QColor("#DBEAFE")))
        b.setToolTip("Dong lop nay" if item["open"] else "Mo them 1 lop nguyen nhan")
        st = self.addText("-" if item["open"] else "+",
                          QFont("Segoe UI", 9, QFont.Weight.Bold))
        st.setDefaultTextColor(COL_GATE)
        br = st.boundingRect()
        st.setPos(ex.center().x() - br.width() / 2, ex.center().y() - br.height() / 2)
        self._exp.append((ex, item))

    # ------------------------------------------------------------------ bam chuot
    def click_at(self, sp):
        for rect, item in self._exp:
            if rect.contains(sp):
                self._toggle(item)
                return
        for rect, node in self._hits:
            if rect.contains(sp):
                if self.on_jump and node.get("db") and node.get("sheet") is not None:
                    self.on_jump(node["db"], node["sheet"])
                return


class CauseTreeScene(QGraphicsScene):
    def __init__(self, tree, highlight=None, hide_and=False):
        super().__init__()
        self.tree = tree
        self.hl_text = (highlight or "").strip().upper()
        self.hide_and = hide_and
        self.on_jump = None            # callback(db, sheet)
        self._cpu_names = {}           # db -> ten CPU (cay chi luu SO cpu)
        self._hits = []                # [(QRectF, node)]
        self._count = 0
        self._truncated = False
        self.build()

    # ---------------------------------------------------------------- bo cuc
    def _visible_children(self, node):
        ch = node.get("children") or []
        if not ch and node.get("type") == "opaque":
            return []
        return ch

    def _match(self, node):
        """Node co phai la nguyen nhan dang duoc chon trong bang khong."""
        if not self.hl_text:
            return False
        lb = (node.get("label") or node.get("net") or "").strip().upper()
        # nhan trong bang co the da duoc bo sung mo ta ('X  [dieu kien]' / 'X (khoi...)')
        return bool(lb) and (lb == self.hl_text or self.hl_text.startswith(lb + " ")
                             or self.hl_text.startswith(lb + "  ["))

    def _layout(self, node, depth, ystate):
        """Gan (x, y) cho tung node. Tra (y_tam, chieu_cao_nhanh, tren_duong_hl).
        Khi cham tran MAX_NODES: danh dau '_trunc' de _draw KHONG di tiep xuong con
        (cac node con chua duoc gan toa do) - neu khong se loi KeyError '_x'."""
        self._count += 1
        node["_trunc"] = False
        if self._count > MAX_NODES:
            self._truncated = True
            node["_x"] = depth; node["_y"] = ystate[0]
            node["_hl"] = False
            node["_trunc"] = True          # co con nhung khong ve tiep
            node["_w"] = LEAF_W
            ystate[0] += NODE_H + V_GAP
            self._note_w(depth, LEAF_W)
            return node["_y"], NODE_H, False
        ch = self._visible_children(node)
        mine = self._match(node)
        # be rong o: la = hop ten dai; khoi = vua chu (AND/OR/NOT/SR hoac ten khoi)
        op = node.get("op") or node.get("block") or "?"
        node["_w"] = LEAF_W if not ch else max(GATE_W, 12 + len(str(op)) * 7)
        self._note_w(depth, node["_w"])
        if not ch:
            y = ystate[0]
            ystate[0] += NODE_H + V_GAP
            node["_x"] = depth; node["_y"] = y
            node["_hl"] = mine
            return y, NODE_H, mine
        ys = []
        any_hl = False
        for c in ch:
            cy, _h, chl = self._layout(c, depth + 1, ystate)
            ys.append(cy)
            any_hl = any_hl or chl
        y = (min(ys) + max(ys)) / 2.0
        node["_x"] = depth; node["_y"] = y
        node["_hl"] = mine or any_hl
        return y, max(ys) - min(ys) + NODE_H, node["_hl"]

    def _note_w(self, depth, w):
        self.maxd = max(self.maxd, depth)
        if w > self._colw.get(depth, 0):
            self._colw[depth] = w

    # ---------------------------------------------------------------- ve
    def build(self):
        self.clear()
        self._hits = []
        self._count = 0
        self._truncated = False
        self.maxd = 0
        self._colw = {}
        ystate = [0.0]
        self._layout(self.tree, 0, ystate)
        # Vi tri X tung cot: cot SAU (nguyen nhan goc) o BEN TRAI, dich o phai. Moi cot
        # rong bang o rong nhat trong cot do - neu dung 1 buoc co dinh thi o dai (ten
        # tin hieu) se DAM VAO khoi cha o cot ke.
        self._colx = {}
        x = 0.0
        for d in range(self.maxd, -1, -1):
            self._colx[d] = x
            x += self._colw.get(d, GATE_W) + H_GAP
        self._draw(self.tree)
        r = self.itemsBoundingRect()
        self.setSceneRect(r.adjusted(-40, -40, 40, 40))

    def _px(self, node):
        """Toa do X: node cang SAU (nguyen nhan goc) cang nam BEN TRAI, dich o phai."""
        return self._colx.get(node["_x"], 0.0)

    def _draw(self, node):
        if "_x" not in node:               # node chua duoc gan toa do (bi cat) -> bo qua
            return
        ch = [] if node.get("_trunc") else self._visible_children(node)
        x = self._px(node); y = node["_y"]
        hl = node.get("_hl")
        if ch:
            self._draw_gate(node, x, y, hl)
            for c in ch:
                if "_x" not in c:
                    continue
                self._draw(c)
                self._wire(self._px(c) + c.get("_w", GATE_W), c["_y"], x, y,
                           c.get("_hl") and hl)
        else:
            self._draw_leaf(node, x, y, hl)

    def _wire(self, x1, y1, x2, y2, hl):
        pen = QPen(COL_HL if hl else COL_WIRE, 2.0 if hl else 1.2)
        mid = (x1 + x2) / 2.0
        p = QPainterPath(QPointF(x1, y1))
        p.lineTo(mid, y1); p.lineTo(mid, y2); p.lineTo(x2, y2)
        it = self.addPath(p, pen)
        it.setZValue(-1)

    def _cpu_name(self, node):
        """Ten CPU doc duoc (DB chi luu SO cpu trong cay dieu kien)."""
        db = node.get("db")
        if not db:
            return str(node.get("cpu") or "")
        if db not in self._cpu_names:
            try:
                from core import dbreader as D
                m = D.db_meta(db)
                self._cpu_names[db] = m.get("cpuname") or ("CPU%s" % m.get("cpuno"))
            except Exception:
                self._cpu_names[db] = str(node.get("cpu") or "")
        return self._cpu_names[db]

    def _draw_gate(self, node, x, y, hl):
        # Khoi co dau vao nhung KHONG phai cong logic (khoi TAG/Data-Link da mo rong
        # xuyen qua) thi khong co 'op' - hien TEN KHOI that thay vi dau '?'
        op = node.get("op") or node.get("block") or "?"
        neg = node.get("neg")
        w = node.get("_w") or max(GATE_W, 12 + len(str(op)) * 7)
        rect = QRectF(x, y - NODE_H / 2, w, NODE_H)
        pen = QPen(COL_HL if hl else COL_GATE, 2.2 if hl else 1.5)
        self.addRect(rect, pen, QBrush(QColor("#EFF6FF")))
        t = self.addText(str(op), QFont("Segoe UI", 10, QFont.Weight.Bold))
        t.setDefaultTextColor(COL_HL if hl else COL_GATE)
        br = t.boundingRect()
        t.setPos(x + (w - br.width()) / 2, y - br.height() / 2)
        node["_w"] = w
        if neg:      # bong phu dinh o dau ra
            self.addEllipse(QRectF(x + w, y - 4, 8, 8),
                            QPen(COL_HL if hl else COL_GATE, 1.5), QBrush(QColor("white")))
        if node.get("op") == "SR" and node.get("priority"):
            s = self.addText("uu tien %s" % node["priority"], QFont("Segoe UI", 7))
            s.setDefaultTextColor(COL_WIRE)
            s.setPos(x, y + NODE_H / 2)
        # nhan tin hieu trung gian (ten net) ghi nho phia tren khoi
        lb = node.get("label") or node.get("net") or ""
        if lb:
            n = self.addText(str(lb)[:34], QFont("Segoe UI", 7))
            n.setDefaultTextColor(COL_WIRE)
            n.setPos(x, y - NODE_H / 2 - 13)
        self._hits.append((rect, node))

    def _draw_leaf(self, node, x, y, hl):
        t = node.get("type")
        lb = node.get("label") or node.get("net") or "?"
        if node.get("neg"):
            lb = "NOT " + lb
        col = COL_LEAF
        suffix = ""
        if t == "cmp":
            col = COL_CMP
            try:
                from core import ce_matrix as CE
                d = CE._cmp_detail(node)
            except Exception:
                d = ""
            if d:
                suffix = "   [%s]" % d
        elif t == "const":
            col = COL_WIRE
        elif node.get("kind") == "cross":
            col = COL_CROSS
            suffix = "   (tu %s)" % (node.get("cpu") or "noi khac")
        if node.get("_folded"):
            suffix += "   [+ con nua]"      # nhanh bi thu gon do khong dan toi dich
        elif node.get("_trunc"):
            suffix += "   [... cat bot]"    # cham tran so khoi ve duoc
        txt = lb + suffix
        f = QFont("Segoe UI", 9, QFont.Weight.Bold if hl else QFont.Weight.Normal)
        fm = QFontMetrics(f)
        txt = fm.elidedText(txt, Qt.TextElideMode.ElideRight, LEAF_W - 14)
        rect = QRectF(x, y - NODE_H / 2, LEAF_W, NODE_H)
        pen = QPen(COL_HL if hl else QColor("#CBD5E1"), 2.2 if hl else 1.0)
        bg = QColor("#FEF2F2") if hl else QColor("white")
        self.addRect(rect, pen, QBrush(bg))
        it = self.addText(txt, f)
        it.setDefaultTextColor(COL_HL if hl else col)
        it.setPos(x + 6, y - it.boundingRect().height() / 2)
        # goc duoi: CPU / sheet de biet nguyen nhan nay o dau
        src = node.get("sheetlbl") or ""
        cpu = self._cpu_name(node)
        if src or cpu:
            s = self.addText(("%s / %s" % (cpu, src)).strip(" /"), QFont("Segoe UI", 7))
            s.setDefaultTextColor(COL_WIRE)
            s.setPos(x + 6, y + NODE_H / 2 - 3)
            s.setZValue(2)
        self._hits.append((rect, node))

    # ---------------------------------------------------------------- tuong tac
    def click_at(self, sp):
        for rect, node in self._hits:
            if rect.contains(sp):
                if self.on_jump and node.get("db") and node.get("sheet") is not None:
                    self.on_jump(node["db"], node["sheet"])
                return


class CauseTreeDialog(QDialog):
    """Cua so so do logic cho 1 tin hieu dich (mo tu Ma tran nhan qua)."""

    def __init__(self, target_disp, cands, cpu_paths, main_window=None,
                 highlight=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint)
        self.setWindowTitle("So do logic: %s" % target_disp)
        self.resize(1180, 760)
        self.mw = main_window
        self.disp = target_disp
        self.cands = cands or []
        self.cpu_paths = cpu_paths or {}
        self.highlight = highlight

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Nguon:"))
        from PySide6.QtWidgets import QComboBox
        self.cb_cand = QComboBox()
        for c in self.cands:
            self.cb_cand.addItem("%s / sheet %s  (%s)"
                                 % (c.get("cpuname") or "?", c.get("sheetlbl") or "?",
                                    c.get("net") or ""), c)
        self.cb_cand.currentIndexChanged.connect(lambda _i: self._reload())
        top.addWidget(self.cb_cand, 1)
        self.ed_hl = QLineEdit(self.highlight or "")
        self.ed_hl.setPlaceholderText("To do duong dan toi nguyen nhan (go ten)...")
        self.ed_hl.returnPressed.connect(self._reload)
        top.addWidget(self.ed_hl, 1)
        b = QPushButton("To do"); b.clicked.connect(self._reload)
        top.addWidget(b)
        self.cb_view = QComboBox()
        self.cb_view.addItem("Theo lop: nguyen nhan goc + tin hieu lien quan", "layer")
        self.cb_view.addItem("Gon: OR cua cac nhom AND", "dnf")
        self.cb_view.addItem("Day du: ca mach logic", "full")
        self.cb_view.setToolTip(
            "Theo lop (nen dung) = dich ben PHAI, di dan sang TRAI qua tung lop.\n"
            "   Moi nguyen nhan goc van nam duoi TIN HIEU CO TEN da gom no lai, nen\n"
            "   doc duoc ca 'cai gi gay ra' lan 'qua duong nao'. Bam [+] mo them lop.\n"
            "Gon = liet ke cac CACH lam tin hieu dich len 1:\n"
            "   DICH = A hoac B hoac (C va D va E) ...\n"
            "   (bo het ten net trung gian - mat phan 'qua duong nao')\n"
            "Day du = ve nguyen mach nhu ban ve goc, tung cong mot (MFT: 448 khoi).")
        self.cb_view.currentIndexChanged.connect(lambda _i: self._reload())
        top.addWidget(self.cb_view)
        self.b_more = QPushButton("Mo them 1 lop")
        self.b_more.setToolTip("Mo dong loat moi o dang hien con bung duoc")
        self.b_more.clicked.connect(self._layer_more)
        top.addWidget(self.b_more)
        self.b_less = QPushButton("Thu gon")
        self.b_less.setToolTip("Dong het cac lop da mo, ve lai lop 1")
        self.b_less.clicked.connect(self._layer_less)
        top.addWidget(self.b_less)
        self.chk_only = QCheckBox("Chi nhanh lien quan")
        self.chk_only.setToolTip("Cat bo moi nhanh khong dan toi nguyen nhan dang to do.\n"
                                 "Van giu cac dieu kien PHAI KEM THEO trong nhom AND (thu gon).")
        self.chk_only.setChecked(bool(highlight))
        self.chk_only.toggled.connect(lambda _b: self._reload())
        top.addWidget(self.chk_only)
        lay.addLayout(top)

        self.info = QLabel(""); self.info.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(self.info)
        self._tree_cache = {}

        from ui.app import ZoomView
        self.view = ZoomView(QGraphicsScene())
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        lay.addWidget(self.view, 1)

        self.legend = QLabel("")
        legend = self.legend
        legend.setWordWrap(True)
        legend.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(legend)

        self._auto_pick()
        self._reload()

    # ------------------------------------------------------------------ chon nguon
    def _tree_of(self, cand):
        key = (cand.get("db"), cand.get("sheet"), cand.get("net"))
        if key not in self._tree_cache:
            from core import ce_matrix as CE
            try:
                self._tree_cache[key] = CE.expand_full(cand["db"], cand["sheet"],
                                                       cand["net"], cpu_paths=self.cpu_paths)
            except Exception:
                self._tree_cache[key] = None
        return self._tree_cache[key]

    @staticmethod
    def _size_of(node):
        if not node:
            return 0
        return 1 + sum(CauseTreeDialog._size_of(c) for c in (node.get("children") or []))

    @staticmethod
    def _has_label(node, want):
        if not node or not want:
            return False
        lb = (node.get("label") or node.get("net") or "").strip().upper()
        if lb and (want == lb or want.startswith(lb + " ")):
            return True
        return any(CauseTreeDialog._has_label(c, want) for c in (node.get("children") or []))

    def _auto_pick(self, max_try=8):
        """Cung 1 ten tin hieu dich thuong duoc san xuat o NHIEU noi, phan lon chi la
        diem phat lai (cay chi co 1 node). Tu chon nguon co logic THAT SU - uu tien
        nguon co chua nguyen nhan dang duoc to do."""
        want = (self.highlight or "").strip().upper()
        best_i, best_k = 0, -1
        for i in range(min(max_try, self.cb_cand.count())):
            t = self._tree_of(self.cb_cand.itemData(i))
            k = self._size_of(t)
            if k > 1:
                self.cb_cand.setItemText(i, self.cb_cand.itemText(i) + "  - %d khoi" % k)
            if want and k > 1 and self._has_label(t, want):
                best_i = i
                break
            if k > best_k:
                best_i, best_k = i, k
        self.cb_cand.blockSignals(True)
        self.cb_cand.setCurrentIndex(best_i)
        self.cb_cand.blockSignals(False)

    LEGEND_LAYER = (
        "Tin hieu dich o BEN PHAI, doc nguoc dan sang TRAI qua tung lop.   "
        "O vien XANH LA = nguyen nhan goc (khong con gi phia sau).   "
        "Bam [+] ben trai 1 o de mo them 1 lop, [-] de dong lai.   "
        "AND = phai du ca nhom;  OR = chi can 1 nhanh.   "
        "Bam vao o de nhay toi sheet ve no.")
    LEGEND_TREE = (
        "Tin hieu chay tu TRAI (nguyen nhan goc) sang PHAI (tin hieu dich).   "
        "Khoi AND = phai du MOI dau vao;  OR = chi can 1;  SR = chot.   "
        "Vong tron o dau ra = phu dinh.   Chu cam = so sanh nguong,  tim = tin hieu tu "
        "CPU/sheet khac.   Do = duong dan toi nguyen nhan dang to.   Bam 1 o de nhay toi sheet.")

    def _reload(self):
        cand = self.cb_cand.currentData()
        if not cand:
            self.info.setText("Khong xac dinh duoc noi san xuat tin hieu nay.")
            return
        self.info.setText("Dang dung so do...")
        view = self.cb_view.currentData() or "layer"
        self.legend.setText(self.LEGEND_LAYER if view == "layer" else self.LEGEND_TREE)
        self.b_more.setVisible(view == "layer")
        self.b_less.setVisible(view == "layer")
        self.chk_only.setVisible(view != "layer")
        if view == "layer":
            # doc lop 1 thoi - KHONG goi _tree_of() (bung ca cay, MFT mat vai giay)
            self._reload_layer(cand)
            return
        tree = self._tree_of(cand)
        if tree is None:
            self.info.setText("Khong dung duoc so do cho nguon nay.")
            return
        if view == "dnf":
            self._reload_dnf(tree)
            return
        want = (self.ed_hl.text() or "").strip().upper()
        note = ""
        full_n = self._size_of(tree)
        if self.chk_only.isChecked() and want:
            pruned = prune_to(tree, want)
            if pruned is None:
                note = ("  (Khong tim thay '%s' trong nhanh nay - dang hien toan bo. "
                        "Thu doi 'Nguon' o tren.)" % self.ed_hl.text())
            else:
                tree = pruned
                note = "  (da cat tu %d khoi xuong con nhanh lien quan)" % full_n
        sc = CauseTreeScene(tree, highlight=self.ed_hl.text())
        sc.on_jump = self._jump
        self._note = note
        self.view.setScene(sc)
        self.view.resetTransform(); self.view._zoom = 1.0
        r = sc.sceneRect()
        zoomed_out = False
        if r.width() > 0 and r.height() > 0:
            # Cay lon (MFT day: 448 khoi, cao vai chuc nghin diem) - "vua man hinh" se
            # thu nho toi muc khong doc duoc chu gi. Chi thu nho toi 1 muc con doc duoc,
            # roi DUA MAN HINH toi dung cho can xem (nguyen nhan dang to, khong thi la
            # tin hieu dich o ben phai).
            vp = self.view.viewport().size()
            fit = min(vp.width() / r.width(), vp.height() / r.height())
            z = max(min(fit, 1.0), 0.45)
            self.view.scale(z, z)
            self.view._zoom = z
            zoomed_out = fit < 0.45
            focus = None
            for _rect, n in sc._hits:
                if n.get("_hl") and not (n.get("children") or []):
                    focus = n
                    break
            if focus is None:
                focus = sc.tree
            if isinstance(focus, dict) and "_x" in focus:
                self.view.centerOn(sc._px(focus) + LEAF_W / 2, focus["_y"])
        msg = "%d khoi/tin hieu trong so do.%s" % (sc._count, getattr(self, "_note", ""))
        if sc._truncated:
            msg += "  (Da cat bot vi cay qua lon.)"
        if zoomed_out:
            msg += ("  So do lon hon man hinh - lan chuot de thu/phong, giu chuot trai de keo. "
                    "Bat 'Chi nhanh lien quan' de gon lai.")
        self.info.setText(msg)

    def showEvent(self, ev):
        """Luc __init__ chay thi cua so chua duoc bay ra, layout chua chia kich thuoc -
        view moi chi 638x478 chu khong phai 1180x760, nen "vua man hinh" tinh sai (thu
        nho con 0.45 du thua cho). Tinh lai dung 1 lan sau khi cua so hien."""
        super().showEvent(ev)
        if getattr(self, "_fitted", False):
            return
        self._fitted = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._refit)

    def _refit(self):
        if isinstance(self.view.scene(), LayerScene):
            self._fit_layer()

    def _reload_layer(self, cand):
        """Che do THEO LOP: chi doc LOP 1 (CE.first_layer), cac lop sau doc khi nguoi
        dung bam [+]. Khac han 2 che do kia - chung deu goi expand_full() bung ca cay
        (MFT: 448 khoi) roi moi ve; o day khong doc gi ngoai nhung lop dang hien."""
        from core import ce_matrix as CE
        try:
            prods = CE.first_layer(cand, self.cpu_paths)
        except Exception as e:
            self.info.setText("Loi khi doc lop 1: %s" % e)
            return
        if not prods:
            self.info.setText("Khong tim thay nguyen nhan truc tiep o nguon nay - "
                              "thu doi 'Nguon' o tren, hoac xem che do 'Day du'.")
            self.view.setScene(QGraphicsScene())
            return
        sc = LayerScene(self.disp, prods,
                        lambda n: CE.drill(n, self.cpu_paths),
                        highlight=self.ed_hl.text())
        sc.on_jump = self._jump
        # truoc khi gan on_changed (scene chua duoc lap vao view)
        self._hl_miss = bool(sc.hl) and not sc.reveal_highlight()
        if not sc.hl and sc.counts()[0] < 6:
            # Lop 1 cua nhieu tin hieu dich chi co 1-2 o (MFT: 2 - deu la khoi trung
            # gian giua cac CPU), mo ra khong noi len dieu gi. Bung san 1 lop nua cho
            # nguoi dung thay ngay noi dung that (MFT: 23 o - van vua 1 man hinh).
            sc.open_all()
        sc.on_changed = self._layer_status
        self.view.setScene(sc)
        self.view.resetTransform(); self.view._zoom = 1.0
        self._fit_layer()
        self._layer_status()

    def _fit_layer(self):
        """Vua man hinh nhung khong thu nho qua muc doc duoc chu."""
        sc = self.view.scene()
        r = sc.sceneRect()
        if r.width() <= 0 or r.height() <= 0:
            return
        vp = self.view.viewport().size()
        z = max(min(vp.width() / r.width(), vp.height() / r.height(), 1.0), 0.45)
        self.view.resetTransform()
        self.view.scale(z, z); self.view._zoom = z
        self.view.centerOn(r.center())

    def _layer_status(self):
        sc = self.view.scene()
        if not isinstance(sc, LayerScene):
            return
        n_box, n_root = sc.counts()
        miss = ("KHONG thay '%s' trong 4 lop dau - thu bam 'Mo them 1 lop', doi 'Nguon' "
                "o tren, hoac xem che do 'Day du'.   "
                % self.ed_hl.text()) if getattr(self, "_hl_miss", False) else ""
        self.info.setText(miss +
            "%d o dang hien, trong do %d la NGUYEN NHAN GOC (vien xanh la - khong con "
            "gi sau nua).  Bam [+] ben trai 1 o de mo them 1 lop;  bam vao o de nhay "
            "toi sheet nguon." % (n_box, n_root))

    def _layer_more(self):
        sc = self.view.scene()
        if not isinstance(sc, LayerScene):
            return
        n = sc.open_all()
        self._fit_layer()
        if not n:
            self.info.setText("Khong con o nao mo them duoc - moi thu dang hien deu la "
                              "nguyen nhan goc.")

    def _layer_less(self):
        sc = self.view.scene()
        if isinstance(sc, LayerScene):
            sc.collapse_all()
            self._fit_layer()

    def _reload_dnf(self, tree):
        """Che do GON: rut cay ve 'DICH = A hoac B hoac (C va D)' roi ve 3 cot."""
        from core import ce_matrix as CE
        try:
            prods = CE.to_dnf(tree)
        except Exception as e:
            self.info.setText("Loi khi rut gon: %s" % e)
            return
        want = (self.ed_hl.text() or "").strip().upper()
        n_all = len(prods)
        if self.chk_only.isChecked() and want:
            keep = [p for p in prods
                    if any(want == (CE.term_label(n) or "").strip().upper()
                           or want.startswith((n.get("label") or n.get("net") or "?").strip().upper() + " ")
                           or want == (n.get("label") or n.get("net") or "").strip().upper()
                           for n in p)]
            if keep:
                prods = keep
        sc = DnfScene(prods, self.disp, highlight=self.ed_hl.text())
        sc.on_jump = self._jump
        self.view.setScene(sc)
        self.view.resetTransform(); self.view._zoom = 1.0
        r = sc.sceneRect()
        if r.width() > 0 and r.height() > 0:
            vp = self.view.viewport().size()
            fit = min(vp.width() / r.width(), vp.height() / r.height())
            z = max(min(fit, 1.0), 0.45)
            self.view.scale(z, z); self.view._zoom = z
            self.view.centerOn(r.center().x(), r.top() + vp.height() / (2 * z))
        n_or = sum(1 for p in prods if len(p) == 1)
        n_and = len(prods) - n_or
        msg = ("'%s' len 1 khi: %d nguyen nhan doc lap (OR), %d nhom phai du dieu kien (AND)."
               % (self.disp, n_or, n_and))
        if len(prods) != n_all:
            msg += "  (loc con %d/%d nhanh lien quan)" % (len(prods), n_all)
        self.info.setText(msg)

    def _jump(self, db, sheet):
        if self.mw is None:
            return
        try:
            self.mw._open_cross(db, sheet)
        except Exception:
            return
        self.raise_()
