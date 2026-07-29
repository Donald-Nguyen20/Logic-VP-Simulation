# -*- coding: utf-8 -*-
"""Xem logic BEN TRONG 1 khoi (station/PID/lead-lag...) dang SO DO NUT SONG DONG -
khong phai anh tinh: moi nut (SELECT/INTEG/CLAMP/SRLATCH/...) hien gia tri mo phong
ngay tren so do, cap nhat theo tung buoc Step/Run. Bo tri theo VUNG (band) tren-xuong
giong dung thu tu manual thuc te (chot che do -> SV -> MV/delta -> lech/MV ERR ->
ABN), chan wire xep 1 cot trai theo dung thu tu pin trong manual, va MOI loai nut
duoc ve dung KY HIEU cua no (OR cong, T-switch, vong tron chot S/R, tich phan ∫,
gioi han ⌐_, Z^-1, |X|, ...) thay vi o chu nhat chung chung.

Co them CHE DO THIET KE (nut "Edit layout"): bat len -> keo tha tung o (chan wire/
khoi tinh toan) bang chuot de tu chinh vi tri khop dung anh manual; bam "Save layout"
de ghi toa do hien tai vao core/analog_manual_pos.json (dung lai cho lan sau, va cho
ca sheet_dyn/khoi khac neu chia se cung ma tram)."""
from __future__ import annotations
import os
import json as _json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QCheckBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QScrollArea, QGraphicsScene, QGraphicsView,
    QGraphicsItemGroup, QGraphicsItem, QMessageBox,
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtCore import QRectF
from core.analog_sim import AnalogSim
from core.analog_layout import layout_manual, load_manual_pos, save_manual_pos

_BOXW, _BOXH = 128, 46
_LEAFW, _LEAFH = 104, 32
_COLGAP, _BANDGAP, _LEAFGAP = 186, 128, 46
_NODE_X0 = 230

_GLYPH = {
    "INTEG": "∫", "DELAY": "Z⁻¹", "ABS": "|X|", "GT": "≥",
    "SUB": "Δ", "SUM": "Σ", "NOT": "¬", "RATELIM": "RL",
    "MUL": "×", "GAIN": "K", "REF": "=",
}
_BAND_NAME = {0: "Che do (Auto/Manual)", 1: "Chuoi SV", 2: "Chuoi MV / Delta",
              3: "Chuoi lech - MV ERR", 4: "Chuoi ABN"}

# --- Ky hieu THAT lay tu core/symbol_shapes.json (cung thu vien dung ve khoi tren
# so do chinh - ui/sheetview.py) - dung khi co ma khop, thay cho hinh tu ve gan dung ---
_SYM_MAP = {
    "OR": "OR2_I",        # cong OR
    "AND": "AND2_I",       # cong AND
    "SRLATCH": "FFS_TS",   # chot S/R (FF/S)
    "SELECT": "XFR_TS",    # chuyen mach / transfer (T)
    "CLAMP": "LMI_TS",     # gioi han (limiter, HI/LO)
    "TON": "DI2_I",        # timer dropout (DI)
}
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


def _sym_geo_bbox(shp):
    """Khung bao (bx,by,bw,bh) cua PHAN THAN ky hieu (khong tinh cac duong day dan
    dai noi sang ky hieu ke tiep trong ban ve SVG goc). Uu tien 'rects' (than chinh);
    neu ky hieu khong co rects (VD DI2_I chi ve bang duong net) thi dung tat ca lines."""
    rects = shp.get("rects") or []
    if rects:
        xs, ys = [], []
        for rx, ry, rw, rh, *_r in rects:
            xs += [rx, rx + rw]; ys += [ry, ry + rh]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    xs, ys = [], []
    for x1, y1, x2, y2 in shp.get("lines", []):
        xs += [x1, x2]; ys += [y1, y2]
    if not xs:
        return 0.0, 0.0, shp.get("w", 10.0), shp.get("h", 10.0)
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


class _NodeGroup(QGraphicsItemGroup):
    """1 o (chan wire hoac khoi tinh toan) tren so do - gom hinh + nhan + gia tri,
    keo duoc khi bat 'Edit layout'. Moi lan doi vi tri se ve lai duong day."""

    def __init__(self, name, dialog):
        super().__init__()
        self.name = name
        self._dialog = dialog
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._dialog._redraw_edges()
        return super().itemChange(change, value)


class InternalLogicSimDialog(QDialog):
    """Chinh dau vao/tham so, bam Step/Run - gia tri mo phong hien truc tiep tren
    so do nut ben trong khoi (khong phai anh manual tinh). Bam 'Edit layout' de
    tu keo tha chinh vi tri tung o, 'Save layout' de luu lai."""

    def __init__(self, code, name="", parent=None):
        super().__init__(parent)
        self.sim = AnalogSim(code)
        self.setWindowTitle("Internal logic (live values): %s (%s)"
                            % (name or self.sim.spec.get("name", ""), code))
        self.resize(1150, 720)
        lay = QVBoxLayout(self)
        self._hint = QLabel(
            "Adjust inputs/params on the left, click Step/Run - values update live on every "
            "node of the diagram (dt=%.2fs). This is the actual computed logic, not a manual scan."
            % self.sim.dt)
        lay.addWidget(self._hint)
        bar = QHBoxLayout()
        for txt, fn in [("Step", lambda: self._run(1)), ("Run 20", lambda: self._run(20)),
                        ("Reset", self._reset)]:
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        bar.addSpacing(20)
        self.b_edit = QPushButton("Edit layout")
        self.b_edit.setCheckable(True)
        self.b_edit.toggled.connect(self._toggle_edit)
        bar.addWidget(self.b_edit)
        self.b_save = QPushButton("Save layout")
        self.b_save.clicked.connect(self._save_layout)
        bar.addWidget(self.b_save)
        bar.addStretch(1)
        lay.addLayout(bar)

        body = QHBoxLayout()
        lay.addLayout(body, 1)

        left = QWidget(); lv = QVBoxLayout(left)
        gin = QGroupBox("Inputs"); fin = QFormLayout(gin)
        self.widgets = {}
        for nm, meta in self.sim.input_meta().items():
            if meta.get("bool"):
                w = QCheckBox()
                w.setChecked(bool(self.sim.inputs.get(nm)))
                w.stateChanged.connect(self._apply)
            else:
                w = QDoubleSpinBox(); w.setRange(-1e6, 1e6); w.setDecimals(2)
                w.setValue(self.sim.inputs.get(nm, 0.0))
                w.valueChanged.connect(self._apply)
            self.widgets[("in", nm)] = w
            fin.addRow(nm + ("  (%s)" % meta["desc"] if meta.get("desc") else ""), w)
        lv.addWidget(gin)

        gp = QGroupBox("Parameters"); fp = QFormLayout(gp)
        for pn, pv in self.sim.spec.get("params", {}).items():
            w = QDoubleSpinBox(); w.setRange(-1e9, 1e9); w.setDecimals(3)
            w.setValue(self.sim.params.get(pn, 0.0))
            w.valueChanged.connect(self._apply)
            self.widgets[("p", pn)] = w
            fp.addRow(pn + ("  (%s)" % pv["desc"] if pv.get("desc") else ""), w)
        lv.addWidget(gp)
        lv.addStretch(1)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(left); sa.setFixedWidth(280)
        body.addWidget(sa)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        body.addWidget(self.view, 1)

        self._pos, self._edges, self._leaf_order = layout_manual(self.sim.spec)
        self._hand = load_manual_pos().get(self.sim.code, {})
        # neu chan wire dung toa do tay (trich tu PDF, thuong x~150-900) nhung nut
        # tinh toan chua co toa do tay -> se roi ve auto-layout; can dich auto-layout
        # sang vung toa do cua chan wire de khong bi tach roi 2 khung toa do khac nhau
        hleaves = (self._hand or {}).get("leaves") or {}
        if hleaves:
            xs = [v[0] + v[2] for v in hleaves.values()]
            ys = [v[1] for v in hleaves.values()]
            self._auto_x0 = max(xs) + 60
            self._auto_y0 = min(ys)
        else:
            self._auto_x0 = _NODE_X0
            self._auto_y0 = 0
        self._value_items = {}
        self._groups = {}
        self._orig_xy = {}
        self._orig_wh = {}
        self._edge_items = []
        self._build_diagram()
        self._apply()
        self.sim.step()
        self._update_values()
        self.sim.reset()
        self._update_values()

    def _apply(self, *_a):
        for (kind, nm), w in self.widgets.items():
            v = (1.0 if w.isChecked() else 0.0) if isinstance(w, QCheckBox) else w.value()
            (self.sim.set_input if kind == "in" else self.sim.set_param)(nm, v)

    def _run(self, n):
        self._apply()
        for _ in range(n):
            self.sim.step()
        self._update_values()

    def _reset(self):
        self.sim.reset()
        self.sim.step()
        self._update_values()

    def _toggle_edit(self, on):
        for g in self._groups.values():
            g.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, on)
        self._hint.setText(
            "CHE DO THIET KE: keo tha tung o de chinh vi tri, roi bam 'Save layout' de luu."
            if on else
            "Adjust inputs/params on the left, click Step/Run - values update live on every "
            "node of the diagram (dt=%.2fs)." % self.sim.dt)

    def _save_layout(self):
        all_data = load_manual_pos()
        code = self.sim.code
        entry = all_data.setdefault(code, {})
        leaves_d = entry.setdefault("leaves", {})
        nodes_d = entry.setdefault("nodes", {})
        nodes = self.sim.spec.get("nodes", {})
        for name in self._pos:
            x, y = self._cur_xy(name)
            w, h = self._orig_wh[name]
            (leaves_d if name not in nodes else nodes_d)[name] = [
                round(x, 1), round(y, 1), round(w, 1), round(h, 1)]
        save_manual_pos(all_data)
        self._hand = all_data.get(code, {})
        QMessageBox.information(self, "Da luu",
            "Da luu vi tri vao core/analog_manual_pos.json cho khoi %s." % code)

    def _box(self, name):
        """(x, y, w, h) ban dau khi dung ve - cot 0 (chan wire) dung ellipse nho xep
        doc theo dung thu tu manual; cac band (1..) dung o dung ky hieu, xep tren-xuong.
        Neu code nay co toa do tay (core/analog_manual_pos.json) thi dung truoc."""
        nodes = self.sim.spec.get("nodes", {})
        is_leaf = name not in nodes
        if self._hand:
            grp = self._hand.get("leaves" if is_leaf else "nodes", {})
            if name in grp:
                x, y, w, h = grp[name]
                return x, y, w, h
        c, r = self._pos.get(name, (0, 0))
        if is_leaf:
            return 0, r * _LEAFGAP + 8, _LEAFW, _LEAFH
        return self._auto_x0 + (c - 1) * _COLGAP, self._auto_y0 + r * _BANDGAP + 30, _BOXW, _BOXH

    def _cur_xy(self, name):
        """Vi tri HIEN TAI (x,y) = vi tri ban dau + do dich chuyen do nguoi dung keo
        (group luc dung len o pos (0,0), keo chuot chi doi group.pos() thanh delta)."""
        ox, oy = self._orig_xy[name]
        p = self._groups[name].pos()
        return ox + p.x(), oy + p.y()

    def _draw_symbol(self, x, y, w, h, sym_key, pen, brush, label_color):
        """Ve DUNG ky hieu that lay tu core/symbol_shapes.json (thu vien dung ve
        khoi tren so do chinh), can ty le va can giua trong khung (x,y,w,h). Bo qua
        cac duong day dan dai (stub noi sang ky hieu ke tiep trong ban ve SVG goc)
        vi so do nay tu ve day noi rieng qua _redraw_edges(). Tra ve list item
        (chua add vao group), hoac None neu khong co ky hieu nay trong thu vien."""
        shp = _symbol_shapes().get(sym_key)
        if not shp:
            return None
        bx, by, bw, bh = _sym_geo_bbox(shp)
        bw = bw or 1.0
        bh = bh or 1.0
        scale = min(w / bw, h / bh) * 0.92
        ox = x + (w - bw * scale) / 2 - bx * scale
        oy = y + (h - bh * scale) / 2 - by * scale

        def X(v):
            return ox + v * scale

        def Y(v):
            return oy + v * scale

        has_rects = bool(shp.get("rects"))
        margin = 3.0
        lo_x, hi_x = bx - margin, bx + bw + margin
        lo_y, hi_y = by - margin, by + bh + margin

        items = []
        for rx, ry, rw, rh, *fl in shp.get("rects", []):
            filled = bool(fl and fl[0])
            it = self.scene.addRect(QRectF(X(rx), Y(ry), rw * scale, rh * scale),
                                     pen, QBrush(pen.color()) if filled else brush)
            items.append(it)
        for cx, cy, cr, *fl in shp.get("circles", []):
            filled = bool(fl and fl[0])
            it = self.scene.addEllipse(
                QRectF(X(cx - cr), Y(cy - cr), 2 * cr * scale, 2 * cr * scale),
                pen, QBrush(pen.color()) if filled else brush)
            items.append(it)
        for x1, y1, x2, y2 in shp.get("lines", []):
            if has_rects and not (lo_x <= x1 <= hi_x and lo_x <= x2 <= hi_x
                                   and lo_y <= y1 <= hi_y and lo_y <= y2 <= hi_y):
                continue     # bo qua stub day dan dai (khong thuoc ve than ky hieu)
            items.append(self.scene.addLine(X(x1), Y(y1), X(x2), Y(y2), pen))
        for tx in shp.get("texts", []):
            tx0, ty0, tsize = tx[0], tx[1], tx[2]
            txt = str(tx[3])
            ps = max(6, int(tsize * scale))
            fnt = QFont("Segoe UI")
            fnt.setPixelSize(ps)
            fnt.setBold(True)
            t = self.scene.addText(txt, fnt)
            t.setDefaultTextColor(label_color)
            t.setPos(X(tx0) - 2, Y(ty0) - ps)
            items.append(t)
        return items

    def _draw_shape(self, x, y, w, h, op, is_leaf, pen, brush):
        """Ve hinh chinh + cac chi tiet phu (nhan S/R, T, OR...). Tra ve list item
        (chua add vao group - caller se addToGroup tung cai)."""
        sc = self.scene
        if is_leaf:
            return [sc.addEllipse(QRectF(x, y, w, h), pen, brush)]
        sym_key = _SYM_MAP.get(op)
        if sym_key:
            items = self._draw_symbol(x, y, w, h, sym_key, pen, brush, QColor("#3346B5"))
            if items:
                return items
        if op == "SRLATCH":
            items = [sc.addEllipse(QRectF(x, y, w, h), pen, brush)]
            for lbl, dy in (("S", 2), ("R", h - 16)):
                t = sc.addText(lbl, QFont("Segoe UI", 8, QFont.Weight.Bold))
                t.setPos(x - 14, y + dy); t.setZValue(2)
                t.setDefaultTextColor(QColor("#0A8A9C"))
                items.append(t)
            return items
        if op == "SELECT":       # T-switch (chuyen mach): 2 dau vao trai, chon->1 dau ra phai
            path = QPainterPath()
            path.moveTo(x, y); path.lineTo(x, y + h)
            path.lineTo(x + w, y + h * 0.72)
            path.lineTo(x + w, y + h * 0.28)
            path.closeSubpath()
            items = [sc.addPath(path, pen, brush)]
            t = sc.addText("T", QFont("Segoe UI", 9, QFont.Weight.Bold))
            t.setPos(x + w * 0.3, y + h * 0.3); t.setZValue(2)
            t.setDefaultTextColor(QColor("#3346B5"))
            items.append(t)
            return items
        if op == "OR":            # hinh OR cong (khien luoi)
            path = QPainterPath()
            path.moveTo(x, y)
            path.quadTo(x + w * 0.55, y, x + w, y + h / 2)
            path.quadTo(x + w * 0.55, y + h, x, y + h)
            path.quadTo(x + w * 0.25, y + h / 2, x, y)
            path.closeSubpath()
            items = [sc.addPath(path, pen, brush)]
            t = sc.addText("OR", QFont("Segoe UI", 8, QFont.Weight.Bold))
            t.setPos(x + w * 0.3, y + h * 0.35); t.setZValue(2)
            t.setDefaultTextColor(QColor("#3346B5"))
            items.append(t)
            return items
        if op == "AND":            # hinh AND (D-shape, mat sau phang)
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x + w * 0.5, y)
            path.arcTo(QRectF(x, y, w, h), 90, -180)
            path.lineTo(x, y + h)
            path.closeSubpath()
            items = [sc.addPath(path, pen, brush)]
            t = sc.addText("AND", QFont("Segoe UI", 7, QFont.Weight.Bold))
            t.setPos(x + w * 0.12, y + h * 0.35); t.setZValue(2)
            t.setDefaultTextColor(QColor("#3346B5"))
            items.append(t)
            return items
        return [sc.addRect(QRectF(x, y, w, h), pen, brush)]

    def _draw_glyph(self, x, y, w, h, op):
        """Ve glyph phu cho cac op KHONG co ky hieu that trong symbol_shapes.json
        (∫, Δ, |X|, ...). CLAMP/TON/OR/AND/SRLATCH/SELECT da co ky hieu that ve
        trong _draw_shape() nen khong can glyph rieng nua. Tra ve list item chua
        add vao group."""
        g = _GLYPH.get(op)
        if not g:
            return []
        t = self.scene.addText(g, QFont("Segoe UI", 15, QFont.Weight.Bold))
        br = t.boundingRect()
        t.setPos(x + w / 2 - br.width() / 2, y + h / 2 - br.height() / 2)
        t.setDefaultTextColor(QColor("#3346B5"))
        t.setZValue(2)
        return [t]

    def _redraw_edges(self):
        for it in self._edge_items:
            self.scene.removeItem(it)
        self._edge_items = []
        pen_edge = QPen(QColor("#9AA4BE"), 1.0)
        for a, b in self._edges:
            if a not in self._groups or b not in self._groups:
                continue
            xa, ya = self._cur_xy(a); wa, ha = self._orig_wh[a]
            xb, yb = self._cur_xy(b); wb, hb = self._orig_wh[b]
            line = self.scene.addLine(xa + wa, ya + ha / 2, xb, yb + hb / 2, pen_edge)
            line.setZValue(0)
            self._edge_items.append(line)

    def _build_diagram(self):
        self.scene.clear()
        self._value_items = {}
        self._groups = {}
        self._orig_xy = {}
        self._orig_wh = {}
        self._edge_items = []
        pen_leaf = QPen(QColor("#0A8A9C"), 1.3)
        pen_node = QPen(QColor("#3346B5"), 1.3)
        outs = set(self.sim.spec.get("out_map", {}).values())
        nodes = self.sim.spec.get("nodes", {})

        # nhan vung (band) - chi khi dung auto-layout; toa do tay da khop dung
        # anh manual nen khong can nhan vung nua (de khong chong len duong day)
        if not self._hand:
            seen_bands = set()
            for name in self._pos:
                if name in nodes:
                    _, r = self._pos[name]
                    if r not in seen_bands:
                        seen_bands.add(r)
                        _, by, _, _ = self._box(name)
                        lbl = self.scene.addText(_BAND_NAME.get(r, ""), QFont("Segoe UI", 8, QFont.Weight.DemiBold))
                        lbl.setPos(_NODE_X0, by - 26); lbl.setZValue(2)
                        lbl.setDefaultTextColor(QColor("#7C8291"))

        for name in self._pos:
            x, y, w, h = self._box(name)
            self._orig_xy[name] = (x, y)
            self._orig_wh[name] = (w, h)
            is_leaf = name not in nodes
            pen = pen_leaf if is_leaf else pen_node
            fill = QColor("#EAF6FF") if is_leaf else (QColor("#FEF3C7") if name in outs else QColor("#FFFFFF"))
            op = nodes.get(name, {}).get("op", "")

            grp = _NodeGroup(name, self)
            for item in self._draw_shape(x, y, w, h, op, is_leaf, pen, QBrush(fill)):
                item.setZValue(1)
                grp.addToGroup(item)
            if not is_leaf:
                for item in self._draw_glyph(x, y, w, h, op):
                    grp.addToGroup(item)
            if is_leaf:
                title = self.scene.addText(name, QFont("Segoe UI", 7))
                title.setPos(x + 2, y + h / 2 - 9); title.setTextWidth(w - 4); title.setZValue(2)
                val = self.scene.addText("", QFont("Segoe UI", 9, QFont.Weight.Bold))
                val.setPos(x + w + 4, y + h / 2 - 9); val.setZValue(2)
            else:
                title = self.scene.addText(name, QFont("Segoe UI", 7, QFont.Weight.Bold))
                tw = title.boundingRect().width()          # khong ep textWidth -> khong xuong dong
                title.setPos(x + w / 2 - tw / 2, y - 15); title.setZValue(2)
                val = self.scene.addText("", QFont("Segoe UI", 10, QFont.Weight.Bold))
                val.setPos(x + w / 2 - 12, y + h + 2); val.setZValue(2)
            title.setDefaultTextColor(QColor("#1E2433"))
            val.setDefaultTextColor(QColor("#B45309"))
            grp.addToGroup(title)
            grp.addToGroup(val)

            self.scene.addItem(grp)
            grp.setZValue(1)
            self._groups[name] = grp
            self._value_items[name] = val

        self._redraw_edges()

    def _update_values(self):
        memo = dict(self.sim.last_memo or {})
        for nm, v in self.sim.inputs.items():
            memo.setdefault(nm, v)
        for nm, v in self.sim.params.items():
            memo.setdefault(nm, v)
        for name, item in self._value_items.items():
            v = memo.get(name)
            item.setPlainText("%.4g" % v if isinstance(v, (int, float)) else "?")
