# -*- coding: utf-8 -*-
"""
Cua so SO DO NODE tin hieu.
- Pham vi Trong sheet / Toan du an (xuyen sheet + xuyen CPU qua C-NET).
- Toan du an mac dinh TACH theo sheet: moi (CPU, sheet, tin hieu) = 1 node.
  Moi sheet = 1 COT doc; cac cot xep TRAI->PHAI theo dong chay (swimlane doc).
- O check "Merge by name" de gop cung ten thanh 1 node cho gon.
"""
from __future__ import annotations
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QCheckBox, QGraphicsScene, QGraphicsView,
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal

from core import signal_graph as SG
from core import cond_tree as CT

BG = "#FCFDFF"
ROOT = "#B45309"
BLOCK = "#3B6FE0"
TERM = "#94A3B8"
EDGE = "#C4CDDA"
XSHEET = "#2563EB"
CNET = "#EA580C"
LANE_BG = "#F5F8FC"
LANE_BD = "#DCE3EE"
TXT = "#FFFFFF"


class _GView(QGraphicsView):
    node_dbl = Signal(str)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._zoom = 1.0

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f); self._zoom *= f

    def mouseDoubleClickEvent(self, ev):
        it = self.itemAt(ev.position().toPoint())
        while it is not None:
            data = it.data(0)
            if data:
                self.node_dbl.emit(str(data)); return
            it = it.parentItem()
        super().mouseDoubleClickEvent(ev)


class SignalGraphPanel(QWidget):
    """Panel so do node — nhung lam 1 TAB trong app. Dung set_target() de doi tin hieu."""
    def __init__(self, parent=None, cpu_paths=None):
        super().__init__(parent)
        self.db_path = None
        self.sheet_id = None
        self.start_net = None
        self.title = ""
        self.on_open_sheet = None
        self.cpu_paths = cpu_paths or {}
        self._nodes = {}
        lay = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Scope:"))
        self.scope = QComboBox()
        self.scope.addItem("In sheet", "sheet")
        self.scope.addItem("Whole project (cross-sheet + CPU)", "project")
        bar.addWidget(self.scope)
        bar.addWidget(QLabel("Direction:"))
        self.cbo = QComboBox()
        self.cbo.addItem("Both directions", "both")
        self.cbo.addItem("Sources (feeding it)", "up")
        self.cbo.addItem("Targets (it feeds)", "down")
        bar.addWidget(self.cbo)
        bar.addWidget(QLabel("Depth:"))
        self.sp = QSpinBox(); self.sp.setRange(1, 30); self.sp.setValue(4)
        bar.addWidget(self.sp)
        self.chk_lbl = QCheckBox("Block labels"); self.chk_lbl.setChecked(True)
        bar.addWidget(self.chk_lbl)
        self.chk_cnet = QCheckBox("C-NET (cross-CPU)"); self.chk_cnet.setChecked(True)
        self.chk_cnet.setEnabled(False)
        bar.addWidget(self.chk_cnet)
        self.chk_merge = QCheckBox("Merge by name"); self.chk_merge.setChecked(False)
        self.chk_merge.setEnabled(False)
        bar.addWidget(self.chk_merge)
        self.chk_rel = QCheckBox("Related nodes only"); self.chk_rel.setChecked(True)
        bar.addWidget(self.chk_rel)
        self.chk_logic = QCheckBox("Show logic relations"); self.chk_logic.setChecked(False)
        bar.addWidget(self.chk_logic)
        btn = QPushButton("Redraw"); btn.clicked.connect(self._rebuild)
        bar.addWidget(btn)
        self.lbl = QLabel(""); self.lbl.setStyleSheet("color:#475569; font-weight:bold;")
        bar.addWidget(self.lbl); bar.addStretch(1)
        leg = QLabel(
            '<span style="color:#B45309">●</span> goc &nbsp;'
            '<span style="color:#3B6FE0">●</span> co ten &nbsp;'
            '<span style="color:#94A3B8">●</span> khong ten &nbsp;&nbsp;'
            '<span style="color:#C4CDDA">━</span> trong sheet &nbsp;'
            '<span style="color:#2563EB">┄</span> xuyen sheet &nbsp;'
            '<span style="color:#EA580C">┄</span> C-NET (xuyen CPU)')
        leg.setStyleSheet("font-size:11px;")
        lay.addLayout(bar)
        lay.addWidget(leg)

        self.scene = QGraphicsScene(); self.scene.setBackgroundBrush(QBrush(QColor(BG)))
        self.view = _GView(self.scene)
        self.view.node_dbl.connect(self._reroot)
        lay.addWidget(self.view, 1)

        hint = QLabel("Double-click a signal = set as new root.  Scroll = zoom, drag = pan.")
        hint.setStyleSheet("color:#94A3B8; font-size:11px;")
        lay.addWidget(hint)

        self.scope.currentIndexChanged.connect(self._on_scope)
        self.cbo.currentIndexChanged.connect(self._rebuild)
        self.sp.valueChanged.connect(self._rebuild)
        self.chk_lbl.stateChanged.connect(self._rebuild)
        self.chk_cnet.stateChanged.connect(self._rebuild)
        self.chk_merge.stateChanged.connect(self._rebuild)
        self.chk_rel.stateChanged.connect(self._rebuild)
        self.chk_logic.stateChanged.connect(self._rebuild)

    def _formula(self, n):
        """(text, opword) cua node co ten, cache theo id."""
        fc = getattr(self, "_fcache", None)
        if fc is None:
            fc = self._fcache = {}
        k = n.get("id")
        if k not in fc:
            try:
                fc[k] = CT.formula(n["db"], n["sheet"], n["net"]) if (n.get("named") and n.get("db")) else ("", "")
            except Exception:
                fc[k] = ("", "")
        return fc[k]

    def set_target(self, db_path, sheet_id, net, title="", cpu_paths=None):
        """Nap 1 tin hieu moi vao tab node."""
        self.db_path = db_path
        self.sheet_id = sheet_id
        self.start_net = net
        self.title = title or ""
        if cpu_paths is not None:
            self.cpu_paths = cpu_paths
        self._rebuild()

    def _on_scope(self):
        proj = self.scope.currentData() == "project"
        self.chk_cnet.setEnabled(proj)
        self.chk_merge.setEnabled(proj)
        if proj:
            self.chk_lbl.setChecked(False)
            if self.sp.value() > 3:
                self.sp.blockSignals(True); self.sp.setValue(3); self.sp.blockSignals(False)
        self._rebuild()

    def _reroot(self, node_id):
        n = self._nodes.get(node_id)
        if not n:
            return
        self.db_path = n.get("db", self.db_path)
        self.sheet_id = n.get("sheet", self.sheet_id)
        self.start_net = n.get("net", self.start_net)
        self._rebuild()

    def _rebuild(self):
        if not self.db_path or self.start_net is None:
            self.scene.clear(); self.lbl.setText("(no signal selected)")
            return
        scope = self.scope.currentData()
        self._lane_mode = False
        try:
            if scope == "project":
                cps = self.cpu_paths if self.chk_cnet.isChecked() else {}
                merge = self.chk_merge.isChecked()
                self._lane_mode = not merge
                nodes, edges, start = SG.trace_project(
                    self.db_path, self.sheet_id, self.start_net,
                    direction=self.cbo.currentData(), depth=self.sp.value(),
                    cpu_paths=cps, merge=merge)
            else:
                nodes, edges, start = SG.trace(
                    self.db_path, self.sheet_id, self.start_net,
                    direction=self.cbo.currentData(), depth=self.sp.value())
        except Exception as e:
            self.lbl.setText("Error: %s" % e); return
        if self.chk_rel.isChecked():
            nodes, edges = self._filter_lineage(nodes, edges, start)
        cpus = sorted({n.get("cpu") for n in nodes if n.get("cpu") is not None})
        sheets = {(n.get("cpu"), n.get("sheet")) for n in nodes}
        extra = ""
        if len(cpus) > 1:
            extra += "  |  %d CPU" % len(cpus)
        if self._lane_mode and len(sheets) > 1:
            extra += "  |  %d sheet" % len(sheets)
        self.lbl.setText("%d signals, %d connections%s" % (len(nodes), len(edges), extra))
        self._render(nodes, edges, start)

    def _filter_lineage(self, nodes, edges, start):
        """Chi giu node NAM TREN duong dan lien quan node goc:
        = to tien (di nguoc toi goc) + hau due (goc di toi) + chinh goc."""
        fwd = defaultdict(list); bwd = defaultdict(list)
        for e in edges:
            fwd[e["src"]].append(e["dst"]); bwd[e["dst"]].append(e["src"])

        def bfs(adj, s):
            seen = {s}; st = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if v not in seen:
                        seen.add(v); st.append(v)
            return seen
        keep = bfs(fwd, start) | bfs(bwd, start)
        # GIU them dau vao/ra TRUC TIEP cua moi node giu lai (halo 1 buoc):
        # de moi sheet van thay du cac node VAO/RA that su, khong bi cat cut.
        halo = set()
        for e in edges:
            if e["src"] in keep:
                halo.add(e["dst"])
            if e["dst"] in keep:
                halo.add(e["src"])
        keep |= halo
        nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges if e["src"] in keep and e["dst"] in keep]
        return nodes, edges

    # ---- bo cuc ----
    def _levels(self, start, edges, by_id):
        lv = {start: 0}
        adj = [(e["src"], e["dst"]) for e in edges]
        for _ in range(len(by_id) + 1):
            ch = False
            for s, d in adj:
                if s in lv and d not in lv:
                    lv[d] = lv[s] + 1; ch = True
                elif d in lv and s not in lv:
                    lv[s] = lv[d] - 1; ch = True
            if not ch:
                break
        for k in by_id:
            lv.setdefault(k, 0)
        return lv

    def _order(self, by_lv, lv, edges, by_id):
        adj = defaultdict(list)
        for e in edges:
            adj[e["src"]].append(e["dst"]); adj[e["dst"]].append(e["src"])
        order = {l: sorted(ids, key=lambda i: by_id[i]["label"]) for l, ids in by_lv.items()}
        pos = {}

        def reindex():
            for l, ids in order.items():
                for i, k in enumerate(ids):
                    pos[k] = i
        reindex()
        for _ in range(5):
            for l in sorted(order):
                def bary(k):
                    ns = [pos[n] for n in adj[k] if n in pos and lv[n] != l]
                    return sum(ns) / len(ns) if ns else pos[k]
                order[l] = sorted(order[l], key=bary)
                reindex()
        return order

    def _render(self, nodes, edges, start):
        self.scene.clear()
        self._fcache = {}
        self._logic = self.chk_logic.isChecked()
        by_id = {n["id"]: n for n in nodes}
        self._nodes = by_id
        if start not in by_id:
            return
        lv = self._levels(start, edges, by_id)
        self._role = {}
        lanes = {(n.get("cpu"), n.get("sheet")) for n in nodes}
        if getattr(self, "_lane_mode", False) and len(lanes) > 1:
            self._render_lanes(by_id, edges, start, lv)
        else:
            self._render_flat(by_id, edges, start, lv)
        r = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        self.scene.setSceneRect(r)
        QTimer.singleShot(0, lambda: self.view.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio))

    def _render_flat(self, by_id, edges, start, lv):
        by_lv = defaultdict(list)
        for k, l in lv.items():
            by_lv[l].append(k)
        order = self._order(by_lv, lv, edges, by_id)
        BW, BH, XG, YG = 220, (86 if getattr(self, "_logic", False) else 64), 150, 30
        mnl = min(by_lv)
        center = {}
        for l in sorted(order):
            x = 40 + (l - mnl) * (BW + XG)
            for row, k in enumerate(order[l]):
                y = 40 + row * (BH + YG)
                self._box(by_id[k], x, y, BW, BH, is_root=(k == start))
                center[k] = QPointF(x + BW / 2, y + BH / 2)
        self._draw_edges(edges, center)

    def _render_lanes(self, by_id, edges, start, lv):
        """Moi SHEET = 1 vung, ben trong chia 3 cot con nhu trang logic that:
        VÀO (trái) · nội bộ (giữa) · RA (phải). Cac sheet xep TRAI->PHAI theo dong chay."""
        BW, BH, YG = 196, (86 if getattr(self, "_logic", False) else 60), 22
        SUBGAP, COLGAP, titleh, topy, pad = 40, 96, 30, 34, 14
        lanes = defaultdict(list)
        for k, n in by_id.items():
            lanes[(n.get("cpu"), n.get("sheet"))].append(k)
        lane_of = {k: (by_id[k].get("cpu"), by_id[k].get("sheet")) for k in by_id}
        role = defaultdict(set)
        for e in edges:
            s, d = e["src"], e["dst"]
            if s in lane_of and d in lane_of and lane_of[s] != lane_of[d]:
                role[d].add("in"); role[s].add("out")
        self._role = role
        lane_key = {L: (sum(lv[k] for k in ids) / len(ids), min(lv[k] for k in ids), str(L))
                    for L, ids in lanes.items()}
        ordered = sorted(lanes, key=lambda L: lane_key[L])

        def slot(k):
            rl = role.get(k, set())
            if "in" in rl:
                return 0
            if "out" in rl:
                return 2
            return 1
        center = {}
        maxrows = 1
        for ids in lanes.values():
            g = defaultdict(int)
            for k in ids:
                g[slot(k)] += 1
            maxrows = max(maxrows, max(g.values()))
        col_h = titleh + maxrows * (BH + YG) + pad
        x = 40
        for L in ordered:
            ids = lanes[L]
            groups = {0: [], 1: [], 2: []}
            for k in ids:
                groups[slot(k)].append(k)
            used = [g for g in (0, 1, 2) if groups[g]]
            lane_w = pad * 2 + max(1, len(used)) * BW + (max(1, len(used)) - 1) * SUBGAP
            # ve nen + tieu de
            bg = self.scene.addRect(x, topy, lane_w, col_h,
                                    QPen(QColor(LANE_BD), 1), QBrush(QColor(LANE_BG)))
            bg.setZValue(-20)
            slbl = next((by_id[k].get("sheetlbl") for k in ids if by_id[k].get("sheetlbl")), L[1])
            db0 = next((by_id[k].get("db") for k in ids if by_id[k].get("db")), None)
            sysn = SG.sys_name(db0, L[1]) if db0 else ("CPU%s" % L[0])
            ti = self.scene.addText("%s · %s" % (sysn, slbl),
                                    QFont("Segoe UI", 9, QFont.Weight.Bold))
            ti.setDefaultTextColor(QColor("#475569")); ti.setPos(x + pad, topy + 5); ti.setZValue(-19)
            for slot_i, g in enumerate(used):
                sx = x + pad + slot_i * (BW + SUBGAP)
                ks = sorted(groups[g], key=lambda i: (lv[i], by_id[i]["label"]))
                for r, k in enumerate(ks):
                    ny = topy + titleh + r * (BH + YG)
                    self._box(by_id[k], sx, ny, BW, BH, is_root=(k == start))
                    center[k] = QPointF(sx + BW / 2, ny + BH / 2)
            x += lane_w + COLGAP
        self._draw_edges(edges, center)

    def _draw_edges(self, edges, center):
        show_lbl = self.chk_lbl.isChecked()
        logic = getattr(self, "_logic", False)
        for kp in ("blk", "xsheet", "cnet"):
            for e in edges:
                if e.get("kind", "blk") != kp:
                    continue
                if e["src"] in center and e["dst"] in center:
                    lbl = e.get("block", "")
                    force = show_lbl
                    if logic:
                        dstn = self._nodes.get(e["dst"])
                        op = self._formula(dstn)[1] if dstn else ""
                        if op:
                            lbl = op; force = True
                    self._edge(center[e["src"]], center[e["dst"]], lbl, kp, force)

    def _badge(self, txt, x, y, bg, right=False, w=0):
        t = self.scene.addText(txt, QFont("Segoe UI", 7, QFont.Weight.Bold))
        tw = t.boundingRect().width()
        px = (x + w - tw - 4) if right else (x + 2)
        r = self.scene.addRect(px - 1, y, tw + 2, 13, QPen(Qt.PenStyle.NoPen), QBrush(QColor(bg)))
        r.setZValue(2.4)
        t.setDefaultTextColor(QColor("#FFFFFF")); t.setPos(px, y - 2); t.setZValue(2.5)

    def _box(self, n, x, y, w, h, is_root):
        col = ROOT if is_root else (BLOCK if n.get("named") else TERM)
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 11, 11)
        it = self.scene.addPath(path, QPen(QColor("#1B2A44"), 1.3), QBrush(QColor(col)))
        it.setPos(x, y); it.setData(0, n["id"]); it.setZValue(1)
        # nhan VAO/RA (chi o che do swimlane theo sheet)
        rl = getattr(self, "_role", {}).get(n["id"], set()) if getattr(self, "_lane_mode", False) else set()
        if "in" in rl:
            self._badge("◀ IN", x, y - 8, "#2563EB")
        if "out" in rl:
            self._badge("RA ▶", x, y - 8, "#15803D", right=True, w=w)
        t1 = self.scene.addText(str(n["label"])[:30], QFont("Segoe UI", 10, QFont.Weight.Bold))
        t1.setDefaultTextColor(QColor(TXT)); t1.setPos(x + 8, y + 7); t1.setData(0, n["id"])
        t1.setZValue(2)
        cpu = n.get("cpu"); shs = n.get("sheets")
        if shs and len(shs) > 1:
            stxt = ",".join(str(z) for z in shs[:4]) + ("..." if len(shs) > 4 else "")
        else:
            stxt = "%s" % (n.get("sheetlbl") or n.get("sheet", ""))
        sysn = SG.sys_name(n["db"], n["sheet"]) if (n.get("db") and n.get("sheet") is not None) else None
        if sysn:
            sub = "%s  ·  %s" % (sysn, stxt)
        elif cpu is not None:
            sub = "CPU%s  ·  %s" % (cpu, stxt)
        else:
            sub = stxt
        t2 = self.scene.addText(sub, QFont("Segoe UI", 8))
        t2.setDefaultTextColor(QColor("#EAF0FB")); t2.setPos(x + 8, y + 34); t2.setData(0, n["id"])
        t2.setZValue(2)
        # dong CONG THUC logic (khi bat "Show logic relations")
        if getattr(self, "_logic", False) and n.get("named"):
            txt = self._formula(n)[0]
            if txt:
                t3 = self.scene.addText("= " + txt[:48], QFont("Segoe UI", 8, QFont.Weight.Bold))
                t3.setDefaultTextColor(QColor("#FFE9C7")); t3.setPos(x + 8, y + h - 21)
                t3.setData(0, n["id"]); t3.setZValue(2)

    def _compact(self, s):
        parts = str(s).split(" -> ")
        if len(parts) <= 2:
            return " -> ".join(parts)
        return "%s … %s" % (parts[0], parts[-1])

    def _edge(self, a, b, signal, kind, show_lbl):
        cnet = (kind == "cnet"); xsh = (kind == "xsheet")
        ltr = b.x() >= a.x()
        a2 = QPointF(a.x() + (110 if ltr else -110), a.y())
        b2 = QPointF(b.x() - (110 if ltr else -110), b.y())
        midx = (a2.x() + b2.x()) / 2
        if cnet:
            col = QColor(CNET); wdt = 2.0
        elif xsh:
            col = QColor(XSHEET); wdt = 1.7
        else:
            col = QColor(EDGE); wdt = 1.2
        pen = QPen(col, wdt)
        if cnet or xsh:
            pen.setStyle(Qt.PenStyle.DashLine)
        path = QPainterPath(a2)
        path.lineTo(midx, a2.y()); path.lineTo(midx, b2.y()); path.lineTo(b2)
        z = 3 if (cnet or xsh) else -5
        self.scene.addPath(path, pen).setZValue(z)
        d = 1 if b2.x() >= midx else -1
        tri = QPainterPath(); tri.moveTo(b2)
        tri.lineTo(b2.x() - d * 8, b2.y() - 4); tri.lineTo(b2.x() - d * 8, b2.y() + 4); tri.closeSubpath()
        self.scene.addPath(tri, QPen(col, 1), QBrush(col)).setZValue(z + 1)
        c1 = QPointF(midx, a2.y()); c2 = QPointF(midx, b2.y())

        def _dot(pt, rr):
            self.scene.addEllipse(pt.x() - rr, pt.y() - rr, 2 * rr, 2 * rr,
                                  QPen(QColor("#FFFFFF"), 1.0), QBrush(col)).setZValue(z + 1)
        for pt in (a2, b2):
            _dot(pt, 3.6)
        for pt in (c1, c2):
            _dot(pt, 2.8)
        if signal and (show_lbl or cnet):
            txt = str(signal) if (cnet or xsh) else self._compact(signal)
            fnt = QFont("Segoe UI", 7, QFont.Weight.Bold if (cnet or xsh) else QFont.Weight.Normal)
            t = self.scene.addText(txt[:34], fnt)
            tw = t.boundingRect().width(); th = t.boundingRect().height()
            cx = midx - tw / 2; cy = (a2.y() + b2.y()) / 2 - th / 2
            if cnet:
                bgc = "#FFF2E8"; fg = "#9A3412"
            elif xsh:
                bgc = "#EAF1FE"; fg = "#1E40AF"
            else:
                bgc = "#FFFFFF"; fg = "#64748B"
            bg = self.scene.addRect(cx - 2, cy + 1, tw + 4, th - 2, QPen(Qt.PenStyle.NoPen), QBrush(QColor(bgc)))
            bg.setZValue(z + 1.4 if (cnet or xsh) else 0)
            t.setDefaultTextColor(QColor(fg)); t.setPos(cx, cy); t.setZValue(z + 1.5 if (cnet or xsh) else 0.1)