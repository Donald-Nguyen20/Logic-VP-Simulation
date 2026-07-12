# -*- coding: utf-8 -*-
"""Canvas: BlockItem + WireItem (day vuong) + LogicScene (khung bao cao 7 cot)."""
from __future__ import annotations
import os
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsPathItem
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF

from core.model import BLOCK_SPECS

W = 96
HEADER = 22
PORT_GAP = 22
PORT_R = 5
TERM_H = 22

COL_ON = QColor("#22aa44")
COL_OFF = QColor("#888888")
COL_BLOCK = QColor("#f5f7fa")
COL_BORDER = QColor("#33415c")
COL_HEADER = QColor("#33415c")
COL_IO = QColor("#eaf2ff")
COL_TERM = QColor("#ffffff")
COL_WIRE = QColor("#5a6b85")
COL_GRID = QColor("#c8d0dc")


def block_height(btype):
    s = BLOCK_SPECS[btype]
    if s.get("term"):
        return TERM_H
    n = max(s["inputs"], s["outputs"], 1)
    return HEADER + n * PORT_GAP + 8


class BlockItem(QGraphicsItem):
    def __init__(self, block, scene_ref):
        super().__init__()
        self.b = block
        self.sref = scene_ref
        self.state = False
        self.out_states = []
        self.spec = BLOCK_SPECS[block.btype]
        self.term = self.spec.get("term")
        self.h = block_height(block.btype)
        self.w = self._calc_w()
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(block.x, block.y)
        self.svg = None
        self._load_svg()

    def _calc_w(self):
        if self.term:
            return 300
        s = self.spec
        names = s.get("in_names", []) + s.get("out_names", [])
        real = any(not (str(x).startswith(("I", "O", "Q", "A", "B", "S", "R", "D")) and len(str(x)) <= 2) for x in names)
        if not names or not real:
            return W
        fm = QFontMetrics(QFont("Segoe UI", 6))
        mi = max([fm.horizontalAdvance(str(x)) for x in s.get("in_names", [])] or [0])
        mo = max([fm.horizontalAdvance(str(x)) for x in s.get("out_names", [])] or [0])
        return max(W, mi + mo + 34)

    def _load_svg(self):
        d = getattr(self.sref, "svg_dir", None)
        if not d or self.term:
            return
        SVG_MAP = {"AND": "AND2_1", "OR": "OR2_1", "XOR": "XOR2_1", "NOT": "NOT_1"}
        cand = [self.b.tag] if self.b.tag else []
        cand.append(SVG_MAP.get(self.b.btype, self.b.btype))
        for name in cand:
            p = os.path.join(d, name + ".svg")
            if os.path.exists(p):
                try:
                    from PySide6.QtSvgWidgets import QGraphicsSvgItem
                    self.svg = QGraphicsSvgItem(p, self)
                    r = self.svg.boundingRect()
                    if r.width() > 0:
                        self.svg.setScale(min(self.w / r.width(), self.h / r.height()))
                    return
                except Exception:
                    self.svg = None

    def in_pos(self, i):
        if self.term:
            return QPointF(0, self.h / 2)
        return QPointF(0, HEADER + i * PORT_GAP + PORT_GAP / 2)

    def out_pos(self, j):
        if self.term:
            return QPointF(self.w, self.h / 2)
        return QPointF(self.w, HEADER + j * PORT_GAP + PORT_GAP / 2)

    def in_scene(self, i):
        return self.mapToScene(self.in_pos(i))

    def out_scene(self, j):
        return self.mapToScene(self.out_pos(j))

    def _has_tagtop(self):
        return (not self.term) and bool(self.b.tag)

    def boundingRect(self):
        top = -26 if self._has_tagtop() else -2
        return QRectF(-PORT_R - 2, top, self.w + 2 * PORT_R + 4, self.h + 4 - top - (-2))

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.term:
            self._paint_terminal(p)
            return
        s = self.spec
        p.setPen(QPen(COL_BORDER, 2 if self.isSelected() else 1))
        p.setBrush(QBrush(COL_IO if self.b.btype in ("DI", "DO") else COL_BLOCK))
        p.drawRoundedRect(QRectF(0, 0, self.w, self.h), 6, 6)
        p.setBrush(QBrush(COL_HEADER))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, self.w, HEADER), 6, 6)
        p.drawRect(QRectF(0, HEADER - 6, self.w, 6))
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, self.w, HEADER), Qt.AlignmentFlag.AlignCenter,
                   str(s.get("label", self.b.btype))[:16])
        p.setPen(QColor("#12305a"))
        p.setFont(QFont("Segoe UI", 7))
        if self.b.btype == "TON":
            p.drawText(QRectF(2, HEADER, self.w - 4, 16), Qt.AlignmentFlag.AlignCenter,
                       "PT=%s" % self.b.param.get("preset", 3))
        # tag + mo ta phia tren khoi (giong ban goc)
        if self.b.tag:
            p.setPen(QColor("#b00000"))
            p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            p.drawText(QRectF(-40, -25, self.w + 120, 12),
                       Qt.AlignmentFlag.AlignLeft, str(self.b.tag)[:24])
            tdes = self.b.param.get("tdes", "")
            if tdes:
                p.setPen(QColor("#333"))
                p.setFont(QFont("Segoe UI", 6))
                p.drawText(QRectF(-40, -14, self.w + 120, 12),
                           Qt.AlignmentFlag.AlignLeft, str(tdes)[:28])
        halfw = self.w / 2 - 8
        p.setFont(QFont("Segoe UI", 6))
        for i in range(s["inputs"]):
            pt = self.in_pos(i)
            self._port(p, pt, "", True)
            nm = s["in_names"][i] if i < len(s["in_names"]) else ""
            if nm:
                p.setPen(QColor("#33415c"))
                p.drawText(QRectF(pt.x() + 7, pt.y() - 7, halfw, 14),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(nm))
        for j in range(s["outputs"]):
            on = self.out_states[j] if j < len(self.out_states) else False
            pt = self.out_pos(j)
            self._port(p, pt, "", False, on)
            nm = s["out_names"][j] if j < len(s["out_names"]) else ""
            if nm:
                p.setPen(QColor("#33415c"))
                p.drawText(QRectF(pt.x() - 7 - halfw, pt.y() - 7, halfw, 14),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(nm))

    def _paint_terminal(self, p):
        w, h = self.w, self.h
        p.setPen(QPen(COL_GRID, 1))
        p.setBrush(QBrush(COL_TERM))
        p.drawRect(QRectF(0, 0, w, h))
        crs = str(self.b.param.get("crs", ""))
        lid = str(self.b.param.get("lid", ""))
        name = str(self.b.tag or "")
        side = self.b.param.get("side", "L")
        # 3 o con: trai [Name|From|LID], phai [LID|To|Name]
        if side == "L":
            cells = [(0, 180, name, Qt.AlignmentFlag.AlignLeft),
                     (180, 240, crs, Qt.AlignmentFlag.AlignHCenter),
                     (240, 300, lid, Qt.AlignmentFlag.AlignHCenter)]
        else:
            cells = [(0, 60, lid, Qt.AlignmentFlag.AlignHCenter),
                     (60, 120, crs, Qt.AlignmentFlag.AlignHCenter),
                     (120, 300, name, Qt.AlignmentFlag.AlignLeft)]
        p.setFont(QFont("Segoe UI", 7))
        for x0, x1, txt, al in cells:
            p.setPen(QPen(COL_GRID, 1))
            p.drawLine(int(x1), 0, int(x1), int(h))
            p.setPen(QColor("#12305a"))
            p.drawText(QRectF(x0 + 4, 0, x1 - x0 - 8, h),
                       al | Qt.AlignmentFlag.AlignVCenter, txt[:26])
        on = self.out_states[0] if self.out_states else False
        p.setBrush(QBrush(COL_ON if on else COL_OFF))
        p.setPen(QPen(COL_BORDER, 1))
        p.drawEllipse(self.out_pos(0) if self.term == "in" else self.in_pos(0), PORT_R, PORT_R)

    def _port(self, p, pt, name, is_in, on=False):
        p.setBrush(QBrush(COL_ON if (not is_in and on) else COL_OFF))
        p.setPen(QPen(COL_BORDER, 1))
        p.drawEllipse(pt, PORT_R, PORT_R)
        if name:
            p.setPen(QColor("#33415c"))
            p.setFont(QFont("Segoe UI", 6))
            if is_in:
                p.drawText(QRectF(pt.x() + 6, pt.y() - 7, 30, 14),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            else:
                p.drawText(QRectF(pt.x() - 36, pt.y() - 7, 30, 14),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.b.x = self.pos().x()
            self.b.y = self.pos().y()
            if self.sref:
                self.sref.update_wires()
        return super().itemChange(change, value)


class WireItem(QGraphicsPathItem):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setZValue(-1)
        self.set_state(False)

    def set_state(self, on):
        self.setPen(QPen(COL_ON if on else COL_WIRE, 2.2 if on else 1.3))

    def update_path(self, p1, p2):
        path = QPainterPath(p1)
        if p2.x() >= p1.x() + 20:
            mx = (p1.x() + p2.x()) / 2
            path.lineTo(mx, p1.y())
            path.lineTo(mx, p2.y())
            path.lineTo(p2.x(), p2.y())
        else:
            path.lineTo(p1.x() + 16, p1.y())
            my = (p1.y() + p2.y()) / 2
            path.lineTo(p1.x() + 16, my)
            path.lineTo(p2.x() - 16, my)
            path.lineTo(p2.x() - 16, p2.y())
            path.lineTo(p2.x(), p2.y())
        self.setPath(path)


class LogicScene(QGraphicsScene):
    def __init__(self, circuit, parent=None):
        super().__init__(parent)
        self.circuit = circuit
        self.setSceneRect(-400, -200, 4000, 3000)
        self.items_by_id = {}
        self.wires = []
        self.pending = None
        self.svg_dir = None
        self.on_status = None
        self.sim_mode = False
        self.on_di_click = None
        self.on_block_info = None
        self.selectionChanged.connect(self._on_sel)
        self.rebuild()

    def _on_sel(self):
        for it in self.selectedItems():
            if hasattr(it, 'b') and self.on_block_info:
                self.on_block_info(it.b)
                return

    def status(self, msg):
        if self.on_status:
            self.on_status(msg)

    def _draw_report_frame(self):
        rep = getattr(self.circuit, "report", None)
        if not rep:
            return
        top, bot = rep["top"], rep["bottom"]
        lx, tw = rep["left_x"], rep["term_w"]
        rx, rw = rep["right_x"], rep["right_w"]
        pen = QPen(COL_GRID, 1)
        hy = top - 26
        # tieu de 7 cot
        titles = [(lx, tw * 0.6, "Line Name"), (lx + tw * 0.6, tw * 0.2, "From"),
                  (lx + tw * 0.8, tw * 0.2, "LID"),
                  (rep["logic_x0"], rx - rep["logic_x0"], "Logic Chart"),
                  (rx, rw * 0.2, "LID"), (rx + rw * 0.2, rw * 0.2, "To"),
                  (rx + rw * 0.4, rw * 0.6, "Line Name")]
        f = QFont("Segoe UI", 9, QFont.Weight.Bold)
        for x, w, t in titles:
            ti = self.addText(t, f)
            ti.setDefaultTextColor(QColor("#12305a"))
            ti.setPos(x + 4, hy)
        # duong ke doc phan vung + ngang tieu de
        for xx in [lx, lx + tw, rx, rx + rw]:
            self.addLine(xx, hy, xx, bot, pen)
        self.addLine(lx, hy + 22, rx + rw, hy + 22, pen)
        self.addLine(lx, hy, rx + rw, hy, pen)

    def rebuild(self):
        self.clear()
        self.items_by_id.clear()
        self.wires.clear()
        self.pending = None
        self._draw_report_frame()
        for b in self.circuit.blocks.values():
            it = BlockItem(b, self)
            self.addItem(it)
            self.items_by_id[b.id] = it
        for c in self.circuit.conns:
            w = WireItem(c)
            self.addItem(w)
            self.wires.append(w)
        self.update_wires()

    def update_wires(self):
        for w in self.wires:
            src = self.items_by_id.get(w.conn.src)
            dst = self.items_by_id.get(w.conn.dst)
            if src and dst:
                w.update_path(src.out_scene(w.conn.src_port), dst.in_scene(w.conn.dst_port))

    def _hit_port(self, sp):
        for it in self.items_by_id.values():
            s = BLOCK_SPECS[it.b.btype]
            for j in range(s["outputs"]):
                if (it.out_scene(j) - sp).manhattanLength() < 12:
                    return (it, "out", j)
            for i in range(s["inputs"]):
                if (it.in_scene(i) - sp).manhattanLength() < 12:
                    return (it, "in", i)
        return None

    def mousePressEvent(self, ev):
        sp = ev.scenePos()
        if self.sim_mode and ev.button() == Qt.MouseButton.LeftButton:
            for it in self.items_by_id.values():
                if it.b.btype == "DI" and it.sceneBoundingRect().contains(sp):
                    if self.on_di_click:
                        self.on_di_click(it.b.id)
                    return
        hit = self._hit_port(sp)
        if hit and ev.button() == Qt.MouseButton.LeftButton:
            it, kind, idx = hit
            if self.pending is None:
                if kind == "out":
                    self.pending = (it.b.id, idx)
                    self.status("Da chon ngo ra. Bam vao 1 cong vao de noi.")
                else:
                    self.status("Hay bam vao CONG RA (ben phai) truoc.")
            else:
                if kind == "in":
                    self.circuit.connect(self.pending[0], self.pending[1], it.b.id, idx)
                    self.pending = None
                    self.rebuild()
                    self.status("Da noi day.")
                else:
                    self.pending = (it.b.id, idx)
                    self.status("Doi ngo ra nguon.")
            return
        super().mousePressEvent(ev)

    def apply_sim(self, out):
        for bid, it in self.items_by_id.items():
            no = BLOCK_SPECS[it.b.btype].get("outputs", 0)
            it.out_states = [bool(out.get((bid, j), False)) for j in range(no)]
            it.state = any(it.out_states)
            it.update()
        for w in self.wires:
            w.set_state(bool(out.get((w.conn.src, w.conn.src_port), False)))
