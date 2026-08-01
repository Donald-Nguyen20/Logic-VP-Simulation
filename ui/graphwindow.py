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
    QPushButton, QCheckBox, QGraphicsScene, QGraphicsView, QMenu,
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPainterPath, QCursor
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, QTimer, Signal

from core import signal_graph as SG
from core import cond_tree as CT

BG = "#FBFCFE"
# --- The node: NEN SANG + VIEN DAM + CHU DEN -> de doc, in ra giay cung ro ---
ROOT = "#FFF4E5"          # tin hieu dang xem (cam nhat)
ROOT_BD = "#C2410C"
ROOT_TXT = "#7C2D12"
BLOCK = "#EAF1FE"         # tin hieu CO TEN (do khoi tao ra)
BLOCK_BD = "#2563EB"
BLOCK_TXT = "#12284B"
TERM = "#F1F5F9"          # net trung gian (khong ten)
TERM_BD = "#94A3B8"
TERM_TXT = "#334155"
SUB_TXT = "#64748B"       # dong phu (CPU / sheet)
FORM_TXT = "#B45309"      # dong cong thuc logic
EDGE = "#94A3B8"          # day trong cung sheet
XSHEET = "#2563EB"        # day xuyen sheet
CNET = "#EA580C"          # day C-NET (xuyen CPU)
FEEDBACK = "#9333EA"      # day HOI TIEP (di NGUOC chieu doc) - vong rieng phia duoi
LANE_BG = "#F5F8FC"
LANE_BD = "#DCE3EE"
TXT = "#FFFFFF"


class _GView(QGraphicsView):
    # Phat toa do SCENE (khong phai id) - panel tu tra node qua bang khung o
    # (_box_id_of), vi mot so lop phu (nhan IN/RA, nhan tren day, tieu de lane...)
    # KHONG gan data(0) nen dung itemAt().data(0) se bi "mu" ngay tren nhung o
    # do -> chinh la ly do "co node bam duoc, co node khong" ma nguoi dung gap.
    node_dbl = Signal(QPointF)
    node_click = Signal(QPointF, QPoint)   # (scene_pos, global_pos cho menu)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._zoom = 1.0
        self._press_pos = None

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f); self._zoom *= f

    def mousePressEvent(self, ev):
        self._press_pos = ev.position().toPoint()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if ev.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            rel = ev.position().toPoint()
            dx = rel.x() - self._press_pos.x(); dy = rel.y() - self._press_pos.y()
            if dx * dx + dy * dy <= 16:   # coi la CLICK (khong phai keo/pan)
                self.node_click.emit(self.mapToScene(rel), ev.globalPosition().toPoint())
        self._press_pos = None

    def mouseDoubleClickEvent(self, ev):
        self.node_dbl.emit(self.mapToScene(ev.position().toPoint()))


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
            '<span style="color:#EA580C">┄</span> C-NET (xuyen CPU) &nbsp;'
            '<span style="color:#9333EA">┄</span> hoi tiep (di nguoc, vong duoi)')
        leg.setStyleSheet("font-size:11px;")
        lay.addLayout(bar)
        lay.addWidget(leg)

        self.scene = QGraphicsScene(); self.scene.setBackgroundBrush(QBrush(QColor(BG)))
        self.view = _GView(self.scene)
        self.view.node_dbl.connect(self._reroot_at)
        self.view.node_click.connect(self._on_click_highlight)
        lay.addWidget(self.view, 1)

        hint = QLabel(
            "Click 1 tin hieu = chon LAM NOI BAT to tien / hau due / ca hai "
            "(bam vao cho trong = bo noi bat).  Double-click = doi lam goc.  "
            "Scroll = zoom, keo = pan.")
        hint.setStyleSheet("color:#94A3B8; font-size:11px;")
        lay.addWidget(hint)
        self._focus_id = None
        self._focus_mode = None
        self._node_items = defaultdict(list)
        self._edge_items = []
        self._cur_edges = []
        self._full_edges = []

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

    def _node_at_scene_pos(self, pt):
        """Tra node theo TOA DO SCENE bang khung o that (_box_id_of), khong
        dua vao data(0) cua item tren cung - vi mot so lop phu (nhan IN/RA,
        nhan tren day, tieu de lane) khong gan data nen se "mu" neu dung
        itemAt().  Day la cach tra ON DINH cho MOI node, khong sot."""
        for nid, r in getattr(self, "_box_id_of", {}).items():
            if r.contains(pt):
                return nid
        return None

    def _reroot_at(self, scene_pt):
        nid = self._node_at_scene_pos(scene_pt)
        if nid:
            self._reroot(nid)

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
        # luu lai TOAN BO canh TRUOC khi loc theo goc - de khi bam 1 node BAT KY
        # (khong chi node goc) van tinh dung to tien/hau due THAT cua no, khong
        # bi cat cut boi bo loc "Related nodes only" tinh rieng cho node goc.
        self._full_edges = list(edges)
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
        self._reset_boxes()          # danh sach o node cho bo dinh tuyen day
        self._fcache = {}
        self._logic = self.chk_logic.isChecked()
        self._focus_id = None        # ve lai -> bo trang thai lam noi bat cu
        self._focus_mode = None
        self._node_items = defaultdict(list)
        self._edge_items = []
        self._cur_edges = edges
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
        self._node_lane = lane_of        # node_id -> lane key (cho bo dinh tuyen "bus")
        self._lane_order = ordered       # thu tu lane TRAI->PHAI
        self._lane_bounds = {}           # lane key -> (x_trai, x_phai)

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
            self._lane_bounds[L] = (x, x + lane_w)
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

    def _lane_gap_trunks(self, edges, center):
        """Voi MOI cap lane KE NHAU: chia deu nhieu truc doc song song trong khoang
        trong giua 2 lane, MOI CAP NODE (tin hieu) khac nhau duoc 1 truc RIENG -
        tranh tinh trang nhieu tin hieu KHONG lien quan lai bi ep di chung 1 duong
        (nhin nham la cung 1 day / cung nhom)."""
        lo = getattr(self, "_node_lane", None)
        order = getattr(self, "_lane_order", None)
        bounds = getattr(self, "_lane_bounds", None)
        trunk_of = {}
        if not (lo and order and bounds):
            return trunk_of
        groups = defaultdict(list)
        for e in edges:
            s, d = e["src"], e["dst"]
            if s not in lo or d not in lo or s not in center or d not in center:
                continue
            Ls, Ld = lo[s], lo[d]
            if Ls == Ld or Ls not in bounds or Ld not in bounds:
                continue
            try:
                i_s, i_d = order.index(Ls), order.index(Ld)
            except ValueError:
                continue
            if abs(i_d - i_s) != 1:
                continue
            key = (Ls, Ld) if i_d > i_s else (Ld, Ls)   # (lane_trai, lane_phai)
            pair = (s, d)
            if pair not in groups[key]:
                groups[key].append(pair)
        for (Lleft, Lright), pairs in groups.items():
            gap_l, gap_r = bounds[Lleft][1], bounds[Lright][0]
            if gap_r <= gap_l:
                continue
            n = len(pairs)
            avail = max(gap_r - gap_l - 20, 0)
            spacing = min(16.0, avail / (n - 1)) if n > 1 else 0.0
            # sap theo Y trung binh de giam giao cheo giua cac truc song song
            pairs = sorted(pairs, key=lambda sd: (center[sd[0]].y() + center[sd[1]].y()))
            mid = (gap_l + gap_r) / 2
            for idx, sd in enumerate(pairs):
                off = (idx - (n - 1) / 2) * spacing
                trunk_of[sd] = mid + off
        return trunk_of

    def _draw_edges(self, edges, center):
        show_lbl = self.chk_lbl.isChecked()
        logic = getattr(self, "_logic", False)
        trunk_of = self._lane_gap_trunks(edges, center)
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
                    self._edge(center[e["src"]], center[e["dst"]], lbl, kp, force,
                               e["src"], e["dst"], trunk_of.get((e["src"], e["dst"])))

    # ---- CLICK 1 NODE = chon LAM NOI BAT to tien / hau due / ca hai, mo cai con lai ----
    def _related_set(self, node_id, mode="both"):
        """mode='up' -> to tien (nguoc len); 'down' -> hau due (xuoi xuong);
        'both' -> ca hai.  Luon gom chinh node_id.  DUNG TOAN BO canh THAT (truoc
        khi loc 'Related nodes only' theo node goc) - de bam NODE BAT KY (khong
        chi node goc dang xem) van ra dung to tien/hau due that cua NO, khong
        bi cat cut theo lineage cua node goc.  Ket qua chi gioi han trong pham
        vi dang VE tren man hinh (co box) vi khong the sang node chua duoc dung."""
        edges = getattr(self, "_full_edges", None) or getattr(self, "_cur_edges", ())
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
        if mode == "up":
            res = bfs(bwd, node_id)
        elif mode == "down":
            res = bfs(fwd, node_id)
        else:
            res = bfs(fwd, node_id) | bfs(bwd, node_id)
        shown = set(getattr(self, "_node_items", {}).keys())
        return (res & shown) if shown else res

    def _on_click_highlight(self, scene_pt, global_pos=None):
        node_id = self._node_at_scene_pos(scene_pt)
        if not node_id or node_id not in self._nodes:
            self._clear_highlight(); return
        self._show_relation_menu(node_id, global_pos)

    def _show_relation_menu(self, node_id, global_pos):
        m = QMenu(self)
        a_up = m.addAction("↑  To tien (nguoc len)")
        a_down = m.addAction("↓  Hau due (xuoi xuong)")
        a_both = m.addAction("↕  Ca hai")
        m.addSeparator()
        a_clear = m.addAction("Bo lam noi bat")
        a_clear.setEnabled(self._focus_id is not None)
        pos = global_pos if global_pos else QCursor.pos()
        act = m.exec(pos)
        if act is a_up:
            self._focus_id, self._focus_mode = node_id, "up"
            self._apply_highlight(node_id, "up")
        elif act is a_down:
            self._focus_id, self._focus_mode = node_id, "down"
            self._apply_highlight(node_id, "down")
        elif act is a_both:
            self._focus_id, self._focus_mode = node_id, "both"
            self._apply_highlight(node_id, "both")
        elif act is a_clear:
            self._clear_highlight()
        # act is None (bam ra ngoai de dong menu) -> giu nguyen trang thai cu

    def _apply_highlight(self, node_id, mode="both"):
        related = self._related_set(node_id, mode)
        DIM = 0.15
        for nid, items in getattr(self, "_node_items", {}).items():
            op = 1.0 if nid in related else DIM
            for it in items:
                it.setOpacity(op)
        for ed in getattr(self, "_edge_items", ()):
            # canh chi sang khi CA HAI dau nam trong tap lien quan VA dung chieu
            # dang xet (vd che do 'to tien' thi chi to canh di VAO tap lien quan)
            op = 1.0 if (ed["src"] in related and ed["dst"] in related) else DIM
            for it in ed["items"]:
                it.setOpacity(op)

    def _clear_highlight(self):
        self._focus_id = None
        self._focus_mode = None
        for items in getattr(self, "_node_items", {}).values():
            for it in items:
                it.setOpacity(1.0)
        for ed in getattr(self, "_edge_items", ()):
            for it in ed["items"]:
                it.setOpacity(1.0)

    def _badge(self, txt, x, y, bg, right=False, w=0):
        t = self.scene.addText(txt, QFont("Segoe UI", 7, QFont.Weight.Bold))
        tw = t.boundingRect().width()
        px = (x + w - tw - 4) if right else (x + 2)
        r = self.scene.addRect(px - 1, y, tw + 2, 13, QPen(Qt.PenStyle.NoPen), QBrush(QColor(bg)))
        r.setZValue(2.4)
        t.setDefaultTextColor(QColor("#FFFFFF")); t.setPos(px, y - 2); t.setZValue(2.5)
        return [r, t]

    # ---- tranh ve day XUYEN QUA node ----
    def _reset_boxes(self):
        self._boxes = []
        self._box_id_of = {}      # node_id -> QRectF (tra node theo toa do scene, on dinh)
        self._lbl_rects = []      # khung cac nhan da dat (de tranh chong len nhau)
        self._lbl_seen = set()    # nhan da ghi (tranh lap cung 1 chu tren cung hanh lang)
        self._node_lane = {}      # node_id -> lane key (chi co gia tri o che do swimlane)
        self._lane_order = []
        self._lane_bounds = {}
        self._used_trunks = []     # [(x, y0, y1), ...] truc doc DA dung boi 1 CANH
                                    # KHAC - tranh 2 tin hieu KHONG lien quan nhau lai
                                    # vo tinh trung duong (nhin nhu di chung 1 day)

    def _seg_hits_box(self, x1, y1, x2, y2, skip=(), margin=6.0):
        """True neu doan thang (ngang hoac doc) cat qua o node nao (tru cac o bo qua)."""
        lo_x, hi_x = (x1, x2) if x1 <= x2 else (x2, x1)
        lo_y, hi_y = (y1, y2) if y1 <= y2 else (y2, y1)
        for r in getattr(self, "_boxes", ()):
            if r in skip:
                continue
            if (lo_x <= r.right() + margin and hi_x >= r.left() - margin
                    and lo_y <= r.bottom() + margin and hi_y >= r.top() - margin):
                return True
        return False

    def _box_at(self, pt):
        for r in getattr(self, "_boxes", ()):
            if r.adjusted(-2, -2, 2, 2).contains(pt):
                return r
        return None

    def _trunk_free(self, mx, y0, y1, tol=7.0):
        """True neu truc doc x=mx, doan [y0,y1] CHUA bi 1 canh KHAC chiem - tranh 2
        tin hieu khong lien quan lai vo tinh di trung 1 duong nhin nhu la 1 day."""
        y0, y1 = (y0, y1) if y0 <= y1 else (y1, y0)
        for ux, uy0, uy1 in getattr(self, "_used_trunks", ()):
            if abs(ux - mx) < tol and uy0 <= y1 and y0 <= uy1:
                return False
        return True

    def _mark_trunk(self, mx, y0, y1):
        self._used_trunks = getattr(self, "_used_trunks", [])
        self._used_trunks.append((mx, min(y0, y1), max(y0, y1)))

    def _route(self, a2, b2, force_midx=None, force_loop=False, prefer=None):
        """Duong day vuong goc KHONG di xuyen qua node: thu nhieu vi tri cho doan doc
        (midx), neu van vuong thi vong len tren / xuong duoi qua mot 'hanh lang' trong.
        force_midx: ep doan doc di dung 1 truc x co dinh (dung cho "bus" giua 2 lane
        ke nhau - moi day cung cap lane deu chay chung 1 truc, nhin thanh 1 "duong
        gom" thay vi nhieu net cheo rieng le).
        force_loop=True: BO QUA buoc 1 (do 3 doan truc tiep), luon di theo kieu vong
        qua tren/duoi TOAN BO cac node - dung cho day HOI TIEP (di nguoc chieu) de
        no luon tach thanh 1 vong rieng biet, khong len xen giua cac node khac.
        prefer='below'/'above': uu tien vong PHIA DUOI (hoac TREN) thay vi chon lane
        gan nhat - de moi day hoi tiep deu di qua CUNG 1 hanh lang duoi cung, gom
        thanh 1 "bus hoi tiep" thay vi moi day 1 kieu."""
        skip = tuple(r for r in (self._box_at(a2), self._box_at(b2)) if r is not None)
        ya, yb = a2.y(), b2.y()
        base = (a2.x() + b2.x()) / 2

        def ok(pts):
            for i in range(len(pts) - 1):
                if self._seg_hits_box(pts[i].x(), pts[i].y(), pts[i + 1].x(), pts[i + 1].y(), skip):
                    return False
            return True

        if force_midx is not None and not force_loop:
            mx = force_midx
            pts = [a2, QPointF(mx, ya), QPointF(mx, yb), b2]
            if ok(pts):
                self._mark_trunk(mx, ya, yb)
                return pts, mx
            # hiem khi bi chan (vd lane qua hep) -> roi xuong tim binh thuong o duoi

        if not force_loop:
            # 1) duong 3 doan quen thuoc, thu dich doan doc sang trai/phai cho thoang.
            # UU TIEN truc CHUA ai dung (_trunk_free) de 2 tin hieu KHONG lien quan
            # khong bi trung duong nhin nham la 1 day; neu het cho rieng thi danh
            # chiu dung chung (con hon de day xuyen qua node).
            fallback = None
            for d in (0, 18, -18, 36, -36, 54, -54, 72, -72, 90, -90, 110, -110):
                mx = base + d
                pts = [a2, QPointF(mx, ya), QPointF(mx, yb), b2]
                if ok(pts):
                    if fallback is None:
                        fallback = (pts, mx)
                    if self._trunk_free(mx, ya, yb):
                        self._mark_trunk(mx, ya, yb)
                        return pts, mx
            if fallback is not None:
                pts, mx = fallback
                self._mark_trunk(mx, ya, yb)
                return pts, mx
        # 2) vong qua tren hoac duoi toan bo cac node nam giua
        tops = [r.top() for r in getattr(self, "_boxes", ())]
        bots = [r.bottom() for r in getattr(self, "_boxes", ())]
        lanes = []
        if tops:
            lanes.append(("above", min(tops) - 34))
        if bots:
            lanes.append(("below", max(bots) + 34))
        if prefer:
            lanes.sort(key=lambda t: (0 if t[0] == prefer else 1))
        else:
            lanes.sort(key=lambda t: abs(t[1] - (ya + yb) / 2))
        gap = 26
        ax = a2.x() + (gap if b2.x() >= a2.x() else -gap)
        bx = b2.x() - (gap if b2.x() >= a2.x() else -gap)
        for _side, ly in lanes:
            pts = [a2, QPointF(ax, ya), QPointF(ax, ly), QPointF(bx, ly), QPointF(bx, yb), b2]
            if ok(pts) or force_loop:
                return pts, (ax + bx) / 2
        return [a2, QPointF(base, ya), QPointF(base, yb), b2], base

    def _elide(self, txt, fnt, maxw):
        """Cat bot chu cho VUA khung (them '…') - tranh chu tran ra ngoai o."""
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(fnt)
        s = str(txt)
        if fm.horizontalAdvance(s) <= maxw:
            return s
        while s and fm.horizontalAdvance(s + "…") > maxw:
            s = s[:-1]
        return (s + "…") if s else ""

    def _box(self, n, x, y, w, h, is_root):
        self._boxes = getattr(self, "_boxes", [])
        self._boxes.append(QRectF(x, y, w, h))
        self._box_id_of = getattr(self, "_box_id_of", {})
        # mo rong nhe khung tra id (bao ca vung nhan IN/RA nho phia tren o, y-8)
        self._box_id_of[n["id"]] = QRectF(x, y - 10, w, h + 10)
        if is_root:
            col, bd, fg = ROOT, ROOT_BD, ROOT_TXT
        elif n.get("named"):
            col, bd, fg = BLOCK, BLOCK_BD, BLOCK_TXT
        else:
            col, bd, fg = TERM, TERM_BD, TERM_TXT
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 9, 9)
        it = self.scene.addPath(path, QPen(QColor(bd), 2.0 if is_root else 1.4),
                                QBrush(QColor(col)))
        it.setPos(x, y); it.setData(0, n["id"]); it.setZValue(1)
        items = [it]
        # vach mau ben trai lam DAU NHAN loai node (nhin luot la biet)
        bar = QPainterPath(); bar.addRoundedRect(QRectF(0, 0, 5, h), 2.5, 2.5)
        bi = self.scene.addPath(bar, QPen(Qt.PenStyle.NoPen), QBrush(QColor(bd)))
        bi.setPos(x, y); bi.setData(0, n["id"]); bi.setZValue(1.1)
        items.append(bi)
        # nhan VAO/RA (chi o che do swimlane theo sheet)
        rl = getattr(self, "_role", {}).get(n["id"], set()) if getattr(self, "_lane_mode", False) else set()
        if "in" in rl:
            items += self._badge("◀ IN", x, y - 8, "#2563EB")
        if "out" in rl:
            items += self._badge("RA ▶", x, y - 8, "#15803D", right=True, w=w)
        f1 = QFont("Segoe UI", 10, QFont.Weight.Bold)
        t1 = self.scene.addText(self._elide(n["label"], f1, w - 26), f1)
        t1.setDefaultTextColor(QColor(fg)); t1.setPos(x + 12, y + 6); t1.setData(0, n["id"])
        t1.setZValue(2)
        t1.setToolTip(str(n["label"]))
        items.append(t1)
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
        f2 = QFont("Segoe UI", 8)
        t2 = self.scene.addText(self._elide(sub, f2, w - 26), f2)
        t2.setDefaultTextColor(QColor(SUB_TXT)); t2.setPos(x + 12, y + 28); t2.setData(0, n["id"])
        t2.setZValue(2)
        items.append(t2)
        # dong CONG THUC logic (khi bat "Show logic relations")
        if getattr(self, "_logic", False) and n.get("named"):
            txt = self._formula(n)[0]
            if txt:
                f3 = QFont("Segoe UI", 8, QFont.Weight.Bold)
                t3 = self.scene.addText(self._elide("= " + txt, f3, w - 26), f3)
                t3.setDefaultTextColor(QColor(FORM_TXT)); t3.setPos(x + 12, y + h - 24)
                t3.setData(0, n["id"]); t3.setZValue(2)
                t3.setToolTip(txt)
                items.append(t3)
        self._node_items = getattr(self, "_node_items", defaultdict(list))
        self._node_items[n["id"]] += items

    def _compact(self, s):
        parts = str(s).split(" -> ")
        if len(parts) <= 2:
            return " -> ".join(parts)
        return "%s … %s" % (parts[0], parts[-1])

    def _edge(self, a, b, signal, kind, show_lbl, src_id=None, dst_id=None, trunk_x=None):
        cnet = (kind == "cnet"); xsh = (kind == "xsheet")
        ltr = b.x() >= a.x()
        # CHI coi la "hoi tiep" that su voi canh FEED trong logic (kind=blk) - noi co
        # chieu "nguon -> dich" ro rang.  C-NET/xuyen-sheet la lien ket GUONG giua
        # cac CPU/sheet (cung 1 ten tin hieu xuat hien nhieu noi), KHONG co chieu
        # "nguoc" thuc su - neu ap dung kieu vong hoi tiep se ra hang loat vong tim
        # gia (nhu test thuc te cho thay), nen giu kieu ve xsheet/cnet binh thuong.
        backward = (not ltr) and not (cnet or xsh)
        # DIEM NOI bam dung VIEN o node (khong con cham lung lo giua khoang trong)
        ra, rb = self._box_at(a), self._box_at(b)
        ax = (ra.right() if ltr else ra.left()) if ra else a.x() + (110 if ltr else -110)
        bx = (rb.left() if ltr else rb.right()) if rb else b.x() - (110 if ltr else -110)
        a2 = QPointF(ax, a.y())
        b2 = QPointF(bx, b.y())
        midx = (a2.x() + b2.x()) / 2
        if backward:
            col = QColor(FEEDBACK); wdt = 1.8
        elif cnet:
            col = QColor(CNET); wdt = 2.0
        elif xsh:
            col = QColor(XSHEET); wdt = 1.7
        else:
            col = QColor(EDGE); wdt = 1.5
        pen = QPen(col, wdt)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if backward:
            pen.setStyle(Qt.PenStyle.DashDotLine)
        elif cnet or xsh:
            pen.setStyle(Qt.PenStyle.DashLine)
        if backward:
            # luon di vong PHIA DUOI toan bo so do - gom moi day hoi tiep vao
            # CUNG 1 hanh lang duoi cung, tach han khoi luong day thuan chieu.
            pts, midx = self._route(a2, b2, force_loop=True, prefer="below")
        else:
            # trunk_x (neu co) da duoc tinh SAN theo tung cap node RIENG BIET o
            # _lane_gap_trunks - moi tin hieu khac nhau di 1 truc khac nhau, khong
            # con bi ep chung 1 duong nhu truoc.
            pts, midx = self._route(a2, b2, force_midx=trunk_x)
        # bo goc VUONG thanh goc BO TRON -> nhin do roi mat
        path = QPainterPath(pts[0])
        R = 9.0
        for i in range(1, len(pts) - 1):
            p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
            v0 = QPointF(p1.x() - p0.x(), p1.y() - p0.y())
            v1 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            l0 = (v0.x() ** 2 + v0.y() ** 2) ** 0.5 or 1.0
            l1 = (v1.x() ** 2 + v1.y() ** 2) ** 0.5 or 1.0
            r = min(R, l0 / 2, l1 / 2)
            path.lineTo(p1.x() - v0.x() / l0 * r, p1.y() - v0.y() / l0 * r)
            path.quadTo(p1, QPointF(p1.x() + v1.x() / l1 * r, p1.y() + v1.y() / l1 * r))
        path.lineTo(pts[-1])
        z = 3 if (cnet or xsh or backward) else -5
        eitems = []
        ln = self.scene.addPath(path, pen); ln.setZValue(z); eitems.append(ln)
        # mui ten o DAU DEN, nam sat vien node
        prev = pts[-2] if len(pts) >= 2 else a2
        d = 1 if b2.x() >= prev.x() else -1
        tri = QPainterPath(); tri.moveTo(b2)
        tri.lineTo(b2.x() - d * 9, b2.y() - 4.5); tri.lineTo(b2.x() - d * 9, b2.y() + 4.5)
        tri.closeSubpath()
        ta = self.scene.addPath(tri, QPen(col, 1), QBrush(col)); ta.setZValue(z + 1)
        eitems.append(ta)
        # cham nho o DAU DI (dinh chac vao vien node), bo cac cham giua duong
        dot = self.scene.addEllipse(a2.x() - 3, a2.y() - 3, 6, 6,
                                    QPen(QColor("#FFFFFF"), 1.0), QBrush(col))
        dot.setZValue(z + 1)
        eitems.append(dot)
        self._edge_items = getattr(self, "_edge_items", [])
        self._edge_items.append({"src": src_id, "dst": dst_id, "items": eitems})
        if signal and (show_lbl or cnet):
            txt = str(signal) if (cnet or xsh) else self._compact(signal)
            # nhieu day cung 1 nhan chay chung 1 hanh lang -> chi ghi 1 lan cho do roi
            self._lbl_seen = getattr(self, "_lbl_seen", set())
            key = (txt, round(pts[1].x() / 40), round(((pts[1].y() + pts[-2].y()) / 2) / 220))
            if key in self._lbl_seen:
                return
            self._lbl_seen.add(key)
            fnt = QFont("Segoe UI", 7, QFont.Weight.Bold)
            t = self.scene.addText(self._elide(txt, fnt, 150), fnt)
            tw = t.boundingRect().width(); th = t.boundingRect().height()
            # neo nhan gan DAU RA (doan ngang dau tien roi khoi node nguon) khi du
            # cho - doc theo huong di cua day se thay nhan NGAY khi roi node, thay
            # vi phai do tim o giua duong nhu truoc.
            seg0 = abs(pts[1].x() - pts[0].x())
            if seg0 >= tw + 16:
                cx = (pts[0].x() + pts[1].x()) / 2 - tw / 2
                cy = pts[0].y() - th - 6
            else:
                cx = pts[1].x() - tw / 2
                cy = (pts[1].y() + pts[-2].y()) / 2 - th / 2
            cy = self._free_label_y(cx, cy, tw, th)
            if backward:
                bgc = "#F3E8FF"; fg = "#6B21A8"; bd = "#D8B4FE"
            elif cnet:
                bgc = "#FFEDD5"; fg = "#9A3412"; bd = "#FDBA74"
            elif xsh:
                bgc = "#DBEAFE"; fg = "#1E40AF"; bd = "#93C5FD"
            else:
                bgc = "#FFFFFF"; fg = "#475569"; bd = "#E2E8F0"
            bg = self.scene.addRect(cx - 4, cy + 2, tw + 8, th - 4,
                                    QPen(QColor(bd), 0.8), QBrush(QColor(bgc)))
            bg.setZValue(z + 1.4)
            t.setDefaultTextColor(QColor(fg)); t.setPos(cx, cy); t.setZValue(z + 1.5)
            self._lbl_rects.append(QRectF(cx - 4, cy + 2, tw + 8, th - 4))
            eitems.append(bg); eitems.append(t)

    def _free_label_y(self, cx, cy, tw, th):
        """Doi cho nhan xuong duoi cho toi khi khong DE LEN nhan khac (tranh chong chu)."""
        self._lbl_rects = getattr(self, "_lbl_rects", [])
        r = QRectF(cx - 4, cy + 2, tw + 8, th - 4)
        for _ in range(14):
            if not any(r.intersects(o) for o in self._lbl_rects):
                return r.y() - 2
            r.moveTop(r.y() + th - 2)
        return r.y() - 2