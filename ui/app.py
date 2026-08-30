# -*- coding: utf-8 -*-
"""Cua so chinh cua T-Designer Lite."""
from __future__ import annotations
import os
import json
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QDockWidget, QTreeWidget, QTreeWidgetItem, QLineEdit,
    QGraphicsView, QPlainTextEdit, QVBoxLayout, QLabel, QDialog, QListWidget,
    QListWidgetItem, QDialogButtonBox,
    QInputDialog, QFileDialog, QMessageBox, QToolBar, QTextEdit, QGraphicsScene,
    QHBoxLayout, QCheckBox, QGroupBox, QComboBox, QScrollArea,
    QDoubleSpinBox, QSpinBox, QPushButton, QFormLayout, QMenu, QTabWidget,
)
from PySide6.QtGui import QPainter, QAction, QPixmap, QShortcut, QKeySequence
from PySide6.QtCore import Qt

from core.model import (Circuit, BLOCK_SPECS,
                        PRIMITIVE_ORDER, CATALOG_BY_CAT, CATALOG_COUNT)
from core import dbreader
from ui.canvas import LogicScene
from ui.graphwindow import SignalGraphPanel
from core.logic_sim import LogicSim, has_behavior
from core.analog_sim import AnalogSim, has_analog


class ZoomView(QGraphicsView):
    """Zoom bang lan chuot. Keo man hinh bang CHUOT TRAI (giu keo).
    Bam trai khong keo = chon/dieu huong khoi/terminal."""
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom = 1.0
        self._pan_start = None
        self._pan_last = None
        self._panning = False
        self.on_context = None        # callback(code, name, bid, global_pos) khi chuot phai KHOI
        self.on_context_signal = None # callback(net, linename, global_pos) khi chuot phai TIN HIEU

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        nz = self._zoom * f
        if 0.05 <= nz <= 25:
            self._zoom = nz
            self.scale(f, f)

    def mousePressEvent(self, ev):
        # Chuot TRAI: giu keo = di chuyen man hinh; bam khong keo = chon/dieu huong.
        if ev.button() == Qt.MouseButton.LeftButton and hasattr(self.scene(), "click_at"):
            self._pan_start = ev.position()
            self._pan_last = ev.position()
            self._panning = False
            ev.accept(); return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._pan_start is not None:
            d = ev.position() - self._pan_last
            self._pan_last = ev.position()
            tot = ev.position() - self._pan_start
            if not self._panning and (abs(tot.x()) + abs(tot.y()) > 4):
                self._panning = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._panning:
                self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x()))
                self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y()))
            ev.accept(); return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._pan_start is not None and ev.button() == Qt.MouseButton.LeftButton:
            panned = self._panning
            self._pan_start = None
            self._panning = False
            self.unsetCursor()
            if not panned:                     # bam ma khong keo -> coi la click
                sc = self.scene()
                if hasattr(sc, "click_at"):
                    sc.click_at(self.mapToScene(ev.position().toPoint()))
            ev.accept(); return
        super().mouseReleaseEvent(ev)

    def contextMenuEvent(self, ev):
        sc = self.scene()
        sp = self.mapToScene(ev.pos())
        hit = sc.block_at(sp) if hasattr(sc, "block_at") else None
        if hit and self.on_context:
            self.on_context(hit[0], hit[1], hit[2], ev.globalPos())
            return
        thit = sc.term_at(sp) if hasattr(sc, "term_at") else None
        if thit and self.on_context_signal:
            self.on_context_signal(thit[0], thit[1], ev.globalPos())
            return
        super().contextMenuEvent(ev)

    def zoom_in(self):
        self._zoom *= 1.25; self.scale(1.25, 1.25)

    def zoom_out(self):
        self._zoom /= 1.25; self.scale(1 / 1.25, 1 / 1.25)

    def zoom_fit(self, min_scale=None):
        r = self.scene().itemsBoundingRect()
        if not r.isEmpty():
            self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()
            if min_scale and self._zoom < min_scale:
                fac = min_scale / self._zoom
                self.scale(fac, fac); self._zoom = min_scale
                self.centerOn(r.topLeft())   # sheet lon: xem tu goc tren-trai cho ro chu

    def zoom_reset(self):
        self.resetTransform(); self._zoom = 1.0


class Palette(QWidget):
    """Cay phan nhom + o tim kiem cho TOAN BO thu vien khoi."""
    def __init__(self, on_add):
        super().__init__()
        self.on_add = on_add
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        n = CATALOG_COUNT + len(PRIMITIVE_ORDER)
        lay.addWidget(QLabel("Library: %d blocks. Double-click to add." % n))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search blocks (name / description / hex code)...")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._dbl)
        lay.addWidget(self.tree)
        self._build("")

    def _groups(self):
        g = [("Basic (Primitive)", list(PRIMITIVE_ORDER))]
        for cat in sorted(CATALOG_BY_CAT):
            g.append((cat, sorted(CATALOG_BY_CAT[cat], key=lambda t: BLOCK_SPECS[t]["label"])))
        return g

    def _match(self, btype, q):
        if not q:
            return True
        sp = BLOCK_SPECS[btype]
        hay = ("%s %s %s %s" % (btype, sp.get("label", ""), sp.get("desc", ""), sp.get("code", ""))).lower()
        return q in hay

    def _build(self, q):
        q = q.strip().lower()
        self.tree.clear()
        for cat, items in self._groups():
            shown = [t for t in items if self._match(t, q)]
            if not shown:
                continue
            top = QTreeWidgetItem(["%s  (%d)" % (cat, len(shown))])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(top)
            for t in shown:
                sp = BLOCK_SPECS[t]
                code = ("[%s] " % sp["code"]) if sp.get("code") else ""
                obs = "  (obs)" if sp.get("obs") else ""
                ch = QTreeWidgetItem(["%s%s - %s%s" % (code, sp["label"], sp.get("desc", ""), obs)])
                ch.setData(0, Qt.ItemDataRole.UserRole, t)
                top.addChild(ch)
            if q:
                top.setExpanded(True)

    def _filter(self, txt):
        self._build(txt)

    def _dbl(self, item, _col):
        t = item.data(0, Qt.ItemDataRole.UserRole)
        if t:
            self.on_add(t)


class SheetPicker(QDialog):
    """Hop thoai chon Sheet tu file DB (co tim kiem)."""
    def __init__(self, project, sheets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select sheet from DB")
        self.resize(560, 520)
        self.sheets = sheets
        self.result_id = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Project: %s" % (project or "?")))
        lay.addWidget(QLabel("%d sheets with blocks. Type to filter:" % len(sheets)))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by PA / name / sheet no / ID...")
        self.search.textChanged.connect(self._fill)
        lay.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._ok())
        lay.addWidget(self.list)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill("")

    def _label(self, s):
        pa = ("[%s] " % s["pa"]) if s["pa"] else ""
        no = ("%s " % s["sheetno"]) if s["sheetno"] else ""
        nm = (" - %s" % s["name"]) if s["name"] else ""
        return "%s%sSheet#%s  (%d blocks)%s" % (pa, no, s["id"], s["nblocks"], nm)

    def _fill(self, q):
        q = (q or "").strip().lower()
        self.list.clear()
        for s in self.sheets:
            txt = self._label(s)
            if q and q not in txt.lower():
                continue
            it = QListWidgetItem(txt)
            it.setData(Qt.ItemDataRole.UserRole, s["id"])
            self.list.addItem(it)

    def _ok(self):
        it = self.list.currentItem()
        if it:
            self.result_id = it.data(Qt.ItemDataRole.UserRole)
            self.accept()


class ImageViewer(QDialog):
    """View an image (internal logic diagram) - scroll to zoom, drag to pan."""
    def __init__(self, img_path, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1040, 780)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._scene = QGraphicsScene(self)
        self._scene.addPixmap(QPixmap(img_path))
        self.view = QGraphicsView(self._scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        lay.addWidget(self.view)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._fit)

    def _fit(self):
        r = self._scene.itemsBoundingRect()
        if not r.isEmpty():
            self.view.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, ev):
        f = 1.2 if ev.angleDelta().y() > 0 else 1 / 1.2
        self.view.scale(f, f)


class BlockSimDialog(QDialog):
    """Mo phong boolean 1 khoi: tich dau vao = 1, dau ra cap nhat ngay."""
    def __init__(self, code, name, parent=None):
        super().__init__(parent)
        self.sim = LogicSim(code)
        self.setWindowTitle("Block simulation: %s (%s)" % (name or self.sim.spec.get("name", ""), code))
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Check = 1 (on). Outputs update instantly. SR latch holds state "
                             "(vd bat Auto roi tat van giu che do Auto den khi bat Manual)."))
        body = QHBoxLayout(); lay.addLayout(body)

        gin = QGroupBox("Inputs"); gv = QVBoxLayout(gin)
        self.checks = {}
        for nm in self.sim.all_input_names():
            cb = QCheckBox(nm); cb.stateChanged.connect(self._update)
            self.checks[nm] = cb; gv.addWidget(cb)
        self._pcombo = None
        for pname, pinfo in self.sim.spec.get("params", {}).items():
            gv.addWidget(QLabel(pinfo.get("desc", pname)))
            cbo = QComboBox(); cbo.addItem("0", 0); cbo.addItem("1", 1)
            cbo.currentIndexChanged.connect(self._update)
            self._pcombo = (pname, cbo); gv.addWidget(cbo)
        gv.addStretch(1)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(gin)
        body.addWidget(sa, 1)

        gout = QGroupBox("Outputs"); go = QVBoxLayout(gout)
        self.outlbls = {}
        for o in self.sim.spec.get("outputs", []):
            l = QLabel(o + " = 0")
            l.setStyleSheet("padding:6px;font-size:14px;font-weight:bold;color:#888;")
            self.outlbls[o] = l; go.addWidget(l)
        go.addStretch(1)
        body.addWidget(gout, 1)
        self._update()

    def _update(self, *a):
        for nm, cb in self.checks.items():
            self.sim.set_input(nm, cb.isChecked())
        if self._pcombo:
            self.sim.set_param(self._pcombo[0], self._pcombo[1].currentData())
        out = self.sim.evaluate()
        for o, l in self.outlbls.items():
            v = out.get(o, 0)
            l.setText("%s = %d" % (o, v))
            l.setStyleSheet("padding:6px;font-size:14px;font-weight:bold;color:%s;"
                            % ("#0a7a0a" if v else "#888"))


class AnalogSimDialog(QDialog):
    """Mo phong ANALOG co buoc thoi gian: chinh dau vao/tham so, bam Buoc de chay."""
    def __init__(self, code, name, parent=None):
        super().__init__(parent)
        self.sim = AnalogSim(code)
        self.setWindowTitle("Analog simulation: %s (%s)" % (name or self.sim.spec.get("name", ""), code))
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Adjust inputs/params, click 'Step' to run one cycle (dt=%.2fs). "
                             "Integrator / rate-limit accumulate over time." % self.sim.dt))
        bar = QHBoxLayout()
        for txt, fn in [("Step", lambda: self._run(1)), ("Run 20 steps", lambda: self._run(20)),
                        ("Reset", self._reset)]:
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch(1); lay.addLayout(bar)

        body = QHBoxLayout(); lay.addLayout(body, 1)
        # cot trai: dau vao + tham so
        left = QWidget(); lv = QVBoxLayout(left)
        gin = QGroupBox("Inputs"); fin = QFormLayout(gin)
        self.widgets = {}
        for nm, meta in self.sim.input_meta().items():
            if meta.get("bool"):
                w = QCheckBox(); w.setChecked(bool(self.sim.inputs.get(nm)))
                w.stateChanged.connect(lambda _s, n=nm, ww=None: None)
                w.stateChanged.connect(self._apply)
            else:
                w = QDoubleSpinBox(); w.setRange(-1e6, 1e6); w.setDecimals(1)
                w.setValue(self.sim.inputs.get(nm, 0.0)); w.valueChanged.connect(self._apply)
            self.widgets[("in", nm)] = w
            fin.addRow(QLabel(nm + ("" if not meta.get("desc") else "  (%s)" % meta["desc"])[:40]), w)
        lv.addWidget(gin)
        gp = QGroupBox("Parameters"); fp = QFormLayout(gp)
        for pn, pv in self.sim.spec.get("params", {}).items():
            w = QDoubleSpinBox(); w.setRange(-1e6, 1e6); w.setDecimals(2)
            w.setValue(self.sim.params.get(pn, 0.0)); w.valueChanged.connect(self._apply)
            self.widgets[("p", pn)] = w
            fp.addRow(QLabel("%s (%s)" % (pn, pv.get("desc", ""))), w)
        lv.addWidget(gp); lv.addStretch(1)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(left)
        body.addWidget(sa, 1)

        # cot phai: dau ra + lich su
        right = QWidget(); rv = QVBoxLayout(right)
        gout = QGroupBox("Outputs"); go = QVBoxLayout(gout)
        self.outlbls = {}
        for o in self.sim.spec.get("outputs", []):
            l = QLabel("%s = 0.0" % o)
            l.setStyleSheet("font-size:16px;font-weight:bold;color:#12305a;padding:4px;")
            self.outlbls[o] = l; go.addWidget(l)
        rv.addWidget(gout)
        rv.addWidget(QLabel("History (each row = 1 step):"))
        self.hist = QPlainTextEdit(); self.hist.setReadOnly(True)
        self.hist.setStyleSheet("font-family:Consolas,monospace;font-size:11px;")
        rv.addWidget(self.hist, 1)
        body.addWidget(right, 1)

        self._nstep = 0
        self._apply(); self._show(self.sim.step()); self.sim.reset(); self._nstep = 0
        self.hist.clear()

    def _apply(self, *a):
        for (kind, nm), w in self.widgets.items():
            v = (1.0 if w.isChecked() else 0.0) if isinstance(w, QCheckBox) else w.value()
            if kind == "in":
                self.sim.set_input(nm, v)
            else:
                self.sim.set_param(nm, v)

    def _run(self, n):
        self._apply()
        out = {}
        for _ in range(n):
            out = self.sim.step(); self._nstep += 1
            self.hist.appendPlainText("b%03d  " % self._nstep +
                                      "  ".join("%s=%.1f" % (k, v) for k, v in out.items()))
        if out:
            self._show(out)

    def _reset(self):
        self.sim.reset(); self._nstep = 0; self.hist.clear()
        self._apply(); self._show(self.sim.step()); self.sim.reset(); self._nstep = 0; self.hist.clear()

    def _show(self, out):
        for o, l in self.outlbls.items():
            l.setText("%s = %.1f" % (o, out.get(o, 0.0)))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logic Demo - T-Designer Lite")
        self.resize(1280, 800)
        self.circuit = Circuit("SHEET1")
        self.db_path = None
        self.sim_global = {}      # {(db_path, TEN_TIN_HIEU.upper()): gia_tri} - mo phong XUYEN SHEET,
                                   # song suot phien lam viec (khong xoa khi doi sheet)
        self.sim_osc = {}         # {(db_path, sheet_id, net): {"mode","lo","hi","period","rate",
                                   #  "value","_next","_t"}} - diem ANALOG dang DAO DONG (bat qua
                                   # chuot phai "Dat dao dong..."), chay NGAM cho moi sheet dang bat,
                                   # ke ca sheet khong hien thi (xem _osc_tick / _recompute_sheet_bg)
        self.station_sims = {}    # {(db_path, sheet_id): {bid: sim_object}} - GIU SONG object mo
                                   # phong khoi TRAM (MV/SV...) xuyen cac lan _apply_sheet_sim lien
                                   # tiep, de MV (bo tich phan noi) THUC SU tich luy theo thoi gian
                                   # thay vi luon dung yen (xem core/sheet_dyn._dyn_blocks). Reset khi
                                   # mo sheet / bat-tat simulate / nguoi dung sua Block parameters.
        self.sim_dyn_state = {}   # {(db_path, sheet_id): {bid: {"s","xprev"}}} - trang thai khoi
                                   # TICH PHAN / dao ham / loc tre / gioi han toc do. Cung vai tro
                                   # nhu station_sims nhung cho khoi I/D/L/R: giu de lan tinh sau
                                   # TIEP TUC tu day (diem dao dong tien 1 buoc moi tick) thay vi
                                   # nhay ve 0. Reset cung luc voi station_sims.
        from PySide6.QtCore import QTimer
        self._osc_timer = QTimer(self)
        self._osc_timer.timeout.connect(self._osc_tick)
        self._osc_timer.start(100)   # tick nen 0.1s; tung diem tu quyet dinh luc nao THUC SU cap nhat
        self._run_timer = QTimer(self)          # dong ho "Run time" (nut tren thanh cong cu)
        self._run_timer.timeout.connect(self._run_tick)
        self._sim_time = 0.0                    # thoi gian mo phong da troi (giay)
        self.nav_history = []
        self.manual = self._load_manual()
        self.internal_map = self._load_internal()
        self._last_block_code = None

        self.scene = LogicScene(self.circuit)
        self.scene.on_status = self.status
        self.view = ZoomView(self.scene)
        self.view.on_context = self.block_context_menu
        self.view.on_context_signal = self.signal_context_menu
        # Trung tam = tab: [Sheet logic] + [So do node]
        self.center_tabs = QTabWidget()
        self.center_tabs.addTab(self.view, "Sheet logic")
        self.graph_tab = SignalGraphPanel(cpu_paths=getattr(self, "cpu_paths", {}))
        self.center_tabs.addTab(self.graph_tab, "Signal node diagram")
        self.setCentralWidget(self.center_tabs)
        self._build_palette()
        self._build_dbtree()
        self._build_output_dock()
        self._build_toolbar()
        self.statusBar().showMessage("Ready. Click 'FB Library' on the toolbar to open the block library.")
        self._load_recent()

    def _build_palette(self):
        dock = QDockWidget("Function Block Library", self)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.palette = Palette(self.add_block)
        lay.addWidget(self.palette)
        tip = QLabel("Wire: click OUTPUT (right) then INPUT (left).\n"
                     "DI/DO/TON: double-click on canvas to edit.  Delete: select then press Delete.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#556;font-size:11px;padding:4px;")
        lay.addWidget(tip)
        dock.setWidget(w)
        dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.palette_dock = dock
        dock.setFloating(True)      # hien duoi dang CUA SO rieng
        dock.hide()                 # chi hien khi bam nut "FB Library"

    def toggle_palette(self):
        """Click the toolbar button -> open/close the Function Block library window."""
        d = self.palette_dock
        if d.isVisible():
            d.hide()
            return
        if not d.isFloating():
            d.setFloating(True)
        g = self.geometry()
        d.resize(360, 600)
        d.move(g.x() + 70, g.y() + 100)
        d.show()
        d.raise_()
        d.activateWindow()

    # ---------- Panel trai: cac file DB da import ----------
    def _build_dbtree(self):
        dock = QDockWidget("Imported DB files", self)
        self.db_dock = dock
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(3)
        self.db_search = QLineEdit()
        self.db_search.setPlaceholderText("Filter sheets by name / PA / no / ID...")
        self.db_search.textChanged.connect(self._filter_dbtree)
        lay.addWidget(self.db_search)
        # Gom sheet theo LOOP (CPU -> Loop 184 'M-BFP MIN FLW CTRL' -> cac sheet trong loop)
        # thay vi do phang ca nghin sheet. Tat di = ve danh sach phang nhu truoc.
        self.group_loop_chk = QCheckBox("Gom theo Loop")
        self.group_loop_chk.setChecked(True)
        self.group_loop_chk.setToolTip(
            "Gom cac sheet cung 1 mach dieu khien vao 1 nhanh, mang ten that cua Loop "
            "(CAD_LOOP). Bo chon de xem danh sach sheet phang nhu truoc.")
        self.group_loop_chk.toggled.connect(self._rebuild_dbtree)
        lay.addWidget(self.group_loop_chk)
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.itemDoubleClicked.connect(self._dbtree_open)
        self.db_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.db_tree.customContextMenuRequested.connect(self._dbtree_menu)
        lay.addWidget(self.db_tree)
        hint = QLabel("Click 'Import DB' to add files.\nDouble-click a sheet to open.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#556;font-size:11px;padding:2px;")
        lay.addWidget(hint)
        dock.setWidget(w)
        dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.proj_nodes = {}   # projno -> project item
        self.db_nodes = {}     # path -> cpu/db item
        self.cpu_paths = {}    # cpuno -> path (de nhay lien-CPU)
        self.meta_by_path = {} # path -> meta (proj/cpu)
        self.sheets_by_path = {}  # path -> danh sach sheet (de dung lai cay khi doi che do)

    def _recent_file(self):
        """Danh sach DB da import, de mo lai app la co ngay. Nam canh app chu khong o
        thu muc nha: chep ca thu muc app sang may khac la giu nguyen phien lam viec."""
        from core import duong_dan as DD
        return DD.duong_json("recent.json", ".tdesigner_lite_recent.json")

    def _save_recent(self):
        try:
            json.dump(list(self.db_nodes.keys()), open(self._recent_file(), "w", encoding="utf-8"))
        except Exception:
            pass

    def _load_recent(self):
        try:
            paths = json.load(open(self._recent_file(), encoding="utf-8"))
        except Exception:
            return
        n = 0
        for p in paths:
            if not os.path.exists(p) or p in self.db_nodes:
                continue
            try:
                meta = dbreader.db_meta(p)
                sheets = dbreader.list_sheets(p)
            except Exception:
                continue
            if not sheets:
                continue
            self.db_path = p
            self._add_db_to_tree(p, meta, sheets)
            n += 1
        if n:
            self.status("Reopened %d previously imported DB files (no re-import needed)." % n)

    def _fmt_sheet(self, s):
        # Nhan sheet = COMMENT1 + LOOPNO + SHEETNO + SHEETNAME (theo CAD_DATA)
        def _s(v):
            return "" if v is None else str(v).strip()
        loop = _s(s.get("loopno"))
        sno = _s(s.get("sheetno_num"))
        parts = [_s(s.get("comment1")),
                 ("Loop %s" % loop) if loop else "",
                 ("Sheet %s" % sno) if sno else "",
                 _s(s.get("name"))]
        label = " ".join(p for p in parts if p)
        return label or ("Sheet#%s" % s["id"])

    def _clear_imported(self):
        """Xoa het cac DB da import truoc do (cay + meta) - dung khi Import DB/Import
        folder duoc bam MOI: lan import moi se DE HOAN TOAN len bo cu, duong dan cu
        khong con lien quan nua (khong gop chung voi lan truoc)."""
        self.db_tree.clear()
        self.db_nodes = {}
        self.meta_by_path = {}
        self.cpu_paths = {}
        self.sheets_by_path = {}
        dbreader.set_project_paths([])

    def _fmt_sheet_in_loop(self, s):
        """Nhan sheet khi DA nam trong nhanh Loop: bo phan 'Loop x' cho do lap lai."""
        def _s(v):
            return "" if v is None else str(v).strip()
        sno = _s(s.get("sheetno_num"))
        parts = [_s(s.get("comment1")),
                 ("Sheet %s" % sno) if sno else "",
                 _s(s.get("name"))]
        return " ".join(p for p in parts if p) or ("Sheet#%s" % s["id"])

    def _rebuild_dbtree(self):
        """Ve lai toan bo cay theo che do hien tai (gom theo Loop / danh sach phang).
        Dung lai danh sach sheet da doc (self.sheets_by_path) - khong doc lai DB."""
        paths = list(self.db_nodes.keys())
        metas = dict(self.meta_by_path)
        sheets = dict(self.sheets_by_path)
        self.db_tree.clear()
        self.db_nodes = {}
        for p in paths:
            if p in sheets:
                self._add_db_to_tree(p, metas.get(p, {}), sheets[p])
        self._filter_dbtree(self.db_search.text())

    def _add_db_to_tree(self, path, meta, sheets):
        # Moi file DB (CPU) la 1 muc top-level. Ben trong: gom theo LOOP (mac dinh) hoac
        # do phang danh sach sheet nhu truoc, tuy o "Gom theo Loop".
        cpu_item = self.db_nodes.get(path)
        if cpu_item is None:
            cpu_item = QTreeWidgetItem([""])
            cpu_item.setData(0, Qt.ItemDataRole.UserRole, ("db", path))
            self.db_tree.addTopLevelItem(cpu_item)
            self.db_nodes[path] = cpu_item
        else:
            cpu_item.takeChildren()
        self.meta_by_path[path] = meta
        self.sheets_by_path[path] = sheets
        # cho phep tra ten tin hieu tro sang DB khac (vd BNB640-04 tren sheet cua BSM_A
        # nhung PANO 'BNB' lai nam ben BSM_B) - xem dbreader.xref_name
        dbreader.set_project_paths(list(self.meta_by_path.keys()))
        if meta.get("cpuno") is not None:
            self.cpu_paths[meta.get("cpuno")] = path
        cpu_item.setText(0, "CPU%s  %s   (%s, %d sheet)"
                         % (meta.get("cpuno"), meta.get("cpuname") or "",
                            os.path.basename(path), len(sheets)))
        by_loop = getattr(self, "group_loop_chk", None) is not None and self.group_loop_chk.isChecked()
        if by_loop:
            groups = {}          # loopno -> [sheet,...]  (giu nguyen thu tu sheet da sort)
            for sh in sheets:
                groups.setdefault(sh.get("loopno"), []).append(sh)
            def _lkey(ln):
                try:
                    return (0, int(ln))
                except (TypeError, ValueError):
                    return (1, 0)
            for ln in sorted(groups, key=_lkey):
                grp = groups[ln]
                lname = ""
                for s in grp:
                    if s.get("loopname"):
                        lname = s["loopname"]; break
                if ln is None:
                    label = "(khong thuoc Loop nao)   (%d sheet)" % len(grp)
                else:
                    label = "Loop %s  %s   (%d sheet)" % (ln, lname, len(grp))
                lit = QTreeWidgetItem([label])
                lit.setData(0, Qt.ItemDataRole.UserRole, ("loop", path, ln))
                cpu_item.addChild(lit)
                for sh in grp:
                    it = QTreeWidgetItem([self._fmt_sheet_in_loop(sh)])
                    it.setData(0, Qt.ItemDataRole.UserRole, ("sheet", path, sh["id"]))
                    lit.addChild(it)
                lit.setExpanded(False)
        else:
            for sh in sheets:
                it = QTreeWidgetItem([self._fmt_sheet(sh)])
                it.setData(0, Qt.ItemDataRole.UserRole, ("sheet", path, sh["id"]))
                cpu_item.addChild(it)
        cpu_item.setExpanded(False)
        self._save_recent()

    def _dbtree_menu(self, pos):
        """Chuot phai trong cay DB. Tren nhanh LOOP -> giai thich nguyen ly ca mach
        bang AI (gom ngu canh moi sheet trong loop, khong chi 1 tin hieu)."""
        item = self.db_tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole) or ()
        if not data or data[0] != "loop" or data[2] is None:
            return
        _kind, path, loopno = data
        m = QMenu(self)
        a_ai = m.addAction("Giai thich loop nay (AI)")
        if m.exec(self.db_tree.viewport().mapToGlobal(pos)) != a_ai:
            return
        try:
            from core import project_index as PI
            PI.ensure(list(getattr(self, "meta_by_path", {}).keys()))
        except Exception:
            pass
        from ui.ai_dialog import AIExplainDialog
        self._ai_dlg = AIExplainDialog(path, None, None,
                                       cpu_paths=getattr(self, "cpu_paths", None),
                                       parent=self, loopno=loopno)
        self._ai_dlg.show()

    def _dbtree_open(self, item, _col=0):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "sheet":
            _, path, sid = data
            self.db_path = path
            self.nav_history = []
            self._open_sheet(sid)
        else:
            item.setExpanded(not item.isExpanded())

    def _filter_dbtree(self, txt):
        """Loc cay. Lam viec voi CA 2 kieu: phang (CPU -> sheet) va gom theo Loop
        (CPU -> Loop -> sheet). Nhanh Loop hien neu ten Loop khop, HOAC co sheet con
        khop (khi do chi hien dung cac sheet khop va tu bung nhanh ra)."""
        q = (txt or "").strip().lower()
        for i in range(self.db_tree.topLevelItemCount()):
            cpu = self.db_tree.topLevelItem(i)
            cpu_any = False
            for j in range(cpu.childCount()):
                ch = cpu.child(j)
                data = ch.data(0, Qt.ItemDataRole.UserRole) or ()
                if data and data[0] == "loop":
                    loop_match = (q in ch.text(0).lower()) if q else True
                    kid_any = False
                    for k in range(ch.childCount()):
                        sub = ch.child(k)
                        # ten Loop khop -> hien het sheet trong loop do
                        hit = True if (not q or loop_match) else (q in sub.text(0).lower())
                        sub.setHidden(not hit)
                        kid_any = kid_any or hit
                    show = loop_match or kid_any
                    ch.setHidden(not show)
                    if q and kid_any and not loop_match:
                        ch.setExpanded(True)
                    cpu_any = cpu_any or show
                else:
                    hit = (q in ch.text(0).lower()) if q else True
                    ch.setHidden(not hit)
                    cpu_any = cpu_any or hit
            # giu CPU hien neu ten CPU khop du khong sheet nao khop
            cpu_match = (q in cpu.text(0).lower()) if q else True
            cpu.setHidden(not (cpu_any or cpu_match))
            if q and cpu_any:
                cpu.setExpanded(True)

    def _build_output_dock(self):
        # Cua so "ket qua doc logic" da bo; giu widget an de cac loi goi setPlainText khong loi.
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.hide()

    def _build_toolbar(self):
        tb = QToolBar("Chinh")
        tb.setMovable(False)
        # Khong dat stylesheet rieng o day: mau toolbar do APP_QSS trong main.py quyet
        # dinh (stylesheet cuc bo se DE MAT toan bo bo mau chung, ke ca mau theo nhom).
        self.addToolBar(tb)

        def mark(a, grp):
            """Gan nhom mau cho nut cua 1 action. APP_QSS bat theo thuoc tinh dong nay
            (QToolBar QToolButton[grp="view"] ...) - xem chu thich bang mau o main.py."""
            if grp:
                btn = tb.widgetForAction(a)
                if btn is not None:
                    btn.setProperty("grp", grp)
            return a

        def act(text, fn, tip="", grp=None):
            a = QAction(text, self)
            a.triggered.connect(fn)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return mark(a, grp)

        self.palette_act = act("FB Library", self.toggle_palette,
                               "Open the Function Block library window", grp="panel")
        self.db_dock_act = self.db_dock.toggleViewAction()
        self.db_dock_act.setText("DB Files")
        self.db_dock_act.setToolTip("Show/hide the imported DB files panel")
        tb.addAction(self.db_dock_act)
        mark(self.db_dock_act, "panel")
        tb.addSeparator()
        act("Import DB", self.import_db, "Read project .db file and rebuild sheets",
            grp="import")
        act("Import folder", self.import_folder,
            "Import all .db in a folder (grouped by Project/CPU)", grp="import")
        act("< Back", self.nav_back, "Go back to previous sheet", grp="nav")
        tb.addSeparator()
        act("Zoom +", self.view.zoom_in, "Zoom in (or scroll up)", grp="view")
        act("Zoom -", self.view.zoom_out, "Zoom out (or scroll down)", grp="view")
        act("Fit", self.view.zoom_fit, "Fit to screen", grp="view")
        act("100%", self.view.zoom_reset, "Reset to 1:1", grp="view")
        tb.addSeparator()
        # Tim tin hieu: phim tat Ctrl+F
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.find_signal)
        self.sim_sheet_act = QAction("Simulate on sheet", self)
        self.sim_sheet_act.setCheckable(True)
        self.sim_sheet_act.setToolTip("Toggle: color 0/1 on the logic sheet; click inputs to change 0/1")
        self.sim_sheet_act.toggled.connect(self.toggle_sheet_sim)
        tb.addAction(self.sim_sheet_act)
        mark(self.sim_sheet_act, "sim")
        # Dong ho: cho THOI GIAN troi de khoi tich phan / loc tre / timer thuc su chay dan,
        # thay vi chi thay ket qua cuoi cung moi lan bam. Chi co nghia khi sheet co khoi dong.
        self.sim_run_act = QAction("▶ Run time", self)
        self.sim_run_act.setCheckable(True)
        self.sim_run_act.setEnabled(False)
        self.sim_run_act.setToolTip("Cho thoi gian troi: moi nhip tien 1 dt. Doi dau vao la "
                                    "thay dau ra bo dan theo, khong nhay thang toi ket qua.")
        self.sim_run_act.toggled.connect(self.toggle_sim_run)
        tb.addAction(self.sim_run_act)
        mark(self.sim_run_act, "sim")
        tb.addSeparator()
        act("Cause && Effect Matrix", self.open_ce_matrix,
            "Tim nguyen nhan goc cho nhieu tin hieu dich (vd MFT, ETS...) va gom thanh 1 bang")
        act("Cai dat AI", self.open_ai_settings,
            "Chon nha cung cap AI cho Explain: 6 nha (Claude, Groq, Gemini, "
            "Ollama, NVIDIA...) - TAT CA deu dung duoc mien phi. "
            "Co nut lay API key va chon model ngay trong hop thoai")
        # Den bao ket noi Claude: TOI = chua ket noi, SANG NHE = da san sang.
        # Tu kiem tra dinh ky nen dang nhap xong o cua so ngoai la tu sang, khong can mo lai app.
        try:
            from PySide6.QtWidgets import QWidget as _QW, QSizePolicy as _SP
            from ui.status_orb import ClaudeStatusBar
            spacer = _QW(); spacer.setSizePolicy(_SP.Policy.Expanding, _SP.Policy.Preferred)
            tb.addWidget(spacer)
            self.claude_status = ClaudeStatusBar()
            self.claude_status.setToolTip("Trang thai ket noi Claude (AI). "
                                          "Bam 'Explain (AI)' de dang nhap neu con toi.")
            tb.addWidget(self.claude_status)
        except Exception:
            pass
        # dt & so buoc & nut Chay nam trong hop cai dat cua tung khoi tich phan
        # (bam vao khoi cam). Gia tri chung luu o day:
        self._dyn_dt = 0.5
        self._dyn_steps = 300

    def open_ai_settings(self):
        """Cai dat AI cho tinh nang Explain: nha cung cap, API key, ten model.

        De o thanh cong cu chinh chu khong chi trong hop thoai Explain: nguoi dung di
        TIM cho lay API key truoc khi biet Explain nam o dau."""
        from ui.llm_settings_dialog import LLMSettingsDialog
        d = LLMSettingsDialog(self)
        d.exec()
        # Hop thoai Explain dang mo phai doi theo NGAY, khong bat dong ra mo lai
        dlg = getattr(self, "_ai_dlg", None)
        if dlg is not None:
            try:
                dlg.reload_provider()
            except Exception:
                pass        # cua so da dong roi - khong sao

    def open_ce_matrix(self):
        """Mo cua so Ma tran nhan qua (chon nhieu tin hieu dich, gom nguyen nhan goc)."""
        from ui.ce_matrix_dialog import CEMatrixDialog
        if not getattr(self, "meta_by_path", None):
            self.status("Import at least one DB first.")
            return
        dlg = getattr(self, "_ce_matrix_dlg", None)
        if dlg is None or not dlg.isVisible():
            dlg = CEMatrixDialog(self, self)
            self._ce_matrix_dlg = dlg
        dlg.show(); dlg.raise_(); dlg.activateWindow()

    def add_block(self, btype):
        k = len(self.circuit.blocks)
        b = self.circuit.add_block(btype, x=140 + 26 * (k % 6), y=90 + 26 * (k % 6))
        if btype in ("DI", "DO"):
            tag, ok = QInputDialog.getText(self, "Tag", "Tag name for %s:" % btype)
            if ok and tag:
                b.tag = tag
        elif btype == "TON":
            v, ok = QInputDialog.getInt(self, "Preset", "Scan delay (PT):", 3, 1, 9999)
            if ok:
                b.param["preset"] = v
        self.scene.rebuild()
        self.status("Added %s." % BLOCK_SPECS.get(btype, {}).get("label", btype))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            for it in list(self.scene.selectedItems()):
                if hasattr(it, "b"):
                    self.circuit.remove_block(it.b.id)
            self.scene.rebuild()
            self.status("Deleted.")
        else:
            super().keyPressEvent(ev)


    def _reset_scene(self):
        svg = self.scene.svg_dir
        self.scene = LogicScene(self.circuit)
        self.scene.svg_dir = svg
        self.scene.on_status = self.status
        self.view.setScene(self.scene)


    def import_db(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select one or more project DB files (Ctrl/Shift for multiple)",
            "", "SQLite DB (*.db);;All (*.*)")
        if not paths:
            return
        self._clear_imported()   # import moi = DE HOAN TOAN len bo cu, khong gop chung
        n = 0; errs = []
        for p in paths:
            try:
                sheets = dbreader.list_sheets(p)
                meta = dbreader.db_meta(p)
            except Exception as e:
                errs.append("%s: %s" % (os.path.basename(p), e)); continue
            if not sheets:
                errs.append("%s: no sheets with blocks" % os.path.basename(p)); continue
            self.db_path = p
            self._add_db_to_tree(p, meta, sheets)
            n += 1
        if errs:
            QMessageBox.warning(self, "Mot so file khong doc duoc", "\n".join(errs[:15]))
        if n:
            self.status("Imported %d DB files (grouped by Project/CPU on the left). Double-click a sheet to open." % n)

    def import_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select a folder containing .db files")
        if not d:
            return
        import glob
        files = sorted(glob.glob(os.path.join(d, "*.db")))
        if not files:
            self.status("Khong tim thay file .db nao trong thu muc da chon.")
            return
        self._clear_imported()   # import moi = DE HOAN TOAN len bo cu, khong gop chung
        n = 0
        for p in files:
            try:
                meta = dbreader.db_meta(p)
                sheets = dbreader.list_sheets(p)
            except Exception:
                continue
            if not sheets:
                continue
            self.db_path = p
            self._add_db_to_tree(p, meta, sheets)
            n += 1
        self.status("Imported %d DB files from folder (grouped by Project/CPU on the left)." % n)

    def _open_sheet(self, sheet_id, proj="", pas="", push_prev=None):
        from core.sheet_render import build_sheet
        from ui.sheetview import SheetScene
        try:
            sheet = build_sheet(self.db_path, sheet_id)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Sheet build error", str(e))
            return
        if push_prev is not None:
            self.nav_history.append(push_prev)
        self.cur_sheet = sheet_id
        self.cur_sheet_name = sheet.title
        self.sheet_scene = SheetScene(sheet)
        self.sheet_scene.on_navigate = self.navigate_from_term
        self.sheet_scene.on_block_click = self.on_sheet_block
        from core import sheet_sim as _SS
        self.sheet_scene.func_codes = {c for c, v in _SS._analog_sem().items()
                                       if v.get("op") == "FUNC"}
        self.sheet_scene.on_func_view = self._show_func_table
        # neu dang bat mo phong tren trang -> ap dung cho sheet moi
        if getattr(self, "sim_sheet_act", None) is not None and self.sim_sheet_act.isChecked():
            self.sim_env = self._default_sim_digital(self.db_path, sheet_id)
            self.sim_analog = self._default_sim_analog(self.db_path, sheet_id)
            self._seed_sim_global(self.db_path, sheet_id, self.sim_env, self.sim_analog)
            self.sim_dyn_over = {}
            self.station_sims.pop((self.db_path, sheet_id), None)   # mo sheet -> khoi tram bat dau lai
            self.sim_dyn_state.pop((self.db_path, sheet_id), None)
            self._stop_sim_run()                 # dong ho khong chay tiep sang sheet khac
            from core import sheet_dyn as _DYN
            self.sim_run_act.setEnabled(_DYN.has_dynamic(self.db_path, sheet_id))
            self.sheet_scene.on_sim_toggle = self._sim_toggle
            self.sheet_scene.on_sim_set_analog = self._sim_set_analog
            self.sheet_scene.on_sim_dyn_config = self._sim_dyn_config
            try:
                self._apply_sheet_sim()
            except Exception:
                pass
        self.view.setScene(self.sheet_scene)
        self.view.resetTransform()
        self.view._zoom = 1.0
        self.view.zoom_fit(min_scale=0.75)
        self.output.setPlainText(
            "# Sheet %s: %s-%s  %s  [%s]\n# %d blocks, %d terminals, %d wires"
            % (sheet_id, sheet.pa, sheet.sheetno, sheet.title, sheet.drawno,
               len(sheet.blocks), len(sheet.terms), len(sheet.wires)))
        self.status("Sheet #%s (%s). Click a terminal (blue text) to jump to the linked sheet."
                    % (sheet_id, sheet.title))

    def _pick_target(self, title, prompt, items):
        """Hop chon 1 muc trong DANH SACH DAI (cuon duoc), thay cho QInputDialog.getItem
        (o do la combobox xo xuong - rat kho dung khi tin hieu he thong dan toi hang chuc
        sheet). Tra ve chi so da chon, hoac None neu huy. Bam dup 1 dong = chon luon."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        lay = QVBoxLayout(dlg)
        lb = QLabel(prompt); lb.setWordWrap(True)
        lay.addWidget(lb)
        lst = QListWidget()
        lst.addItems(items)
        lst.setCurrentRow(0)
        lst.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay.addWidget(lst, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        lst.itemDoubleClicked.connect(lambda _it: dlg.accept())
        dlg.resize(620, min(560, 140 + 22 * max(4, min(len(items), 18))))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        row = lst.currentRow()
        return row if row >= 0 else None

    def navigate_from_term(self, term):
        tgs = term.targets
        if not tgs:
            xdb = getattr(term, "xdb", None)      # ten tin hieu nam o DB cua CPU khac
            if xdb and xdb[1] is not None:
                self._open_cross(xdb[0], xdb[1])
                return
            self._navigate_cross_cpu(term)
            return
        if len(tgs) == 1:
            self._open_sheet(tgs[0][0], push_prev=(self.db_path, self.cur_sheet))
        else:
            items = ["%s  (sheet %s)" % (lbl, sid) for sid, lbl in tgs]
            idx = self._pick_target(
                "Multiple targets",
                "Tin hieu '%s' dan toi %d sheet:" % (term.lid or term.linename, len(tgs)),
                items)
            if idx is not None:
                self._open_sheet(tgs[idx][0], push_prev=(self.db_path, self.cur_sheet))

    def _navigate_cross_cpu(self, term):
        """Nhay sang DB cua CPU doi tac cho tin hieu lien-CPU (C-NET)."""
        if not getattr(term, "xcpu", None) or not getattr(self, "cpu_paths", None):
            return
        cur_cpu = (self.meta_by_path.get(self.db_path) or {}).get("cpuno")
        cands = dbreader.resolve_cross_cpu(
            self.db_path, getattr(self, "cur_sheet_name", ""),
            term.lid, term.linename, self.cpu_paths, cur_cpu)
        if not cands:
            self.status("No cross-CPU sheet found for signal '%s'." % (term.linename or term.lid))
            return
        if len(cands) == 1:
            self._open_cross(cands[0][0], cands[0][1])
        else:
            items = ["%s" % c[2] for c in cands]
            idx = self._pick_target(
                "Multiple targets (cross-CPU)",
                "Tin hieu '%s' dan toi %d sheet o CPU khac:"
                % (term.linename or term.lid, len(cands)),
                items)
            if idx is not None:
                c = cands[idx]
                self._open_cross(c[0], c[1])

    def _open_cross(self, path, sheet_id):
        # cur_sheet chi ton tai SAU khi da mo it nhat 1 sheet (vd bam thang vao 1
        # hang trong Ma tran nhan qua truoc khi mo sheet nao) - dung getattr tranh
        # AttributeError, khong co gi de "quay lai" thi thoi.
        prev = (getattr(self, "db_path", None), getattr(self, "cur_sheet", None))
        self.db_path = path
        self._open_sheet(sheet_id, push_prev=prev if prev[1] is not None else None)

    def nav_back(self):
        if getattr(self, "nav_history", None):
            prev = self.nav_history.pop()
            if isinstance(prev, tuple):
                db, sid = prev
                self.db_path = db
                self._open_sheet(sid)
            else:
                self._open_sheet(prev)


    def _load_manual(self):
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "macro_manual.json")
        try:
            return json.load(open(p, encoding="utf-8")).get("by_code", {})
        except Exception:
            return {}

    def _load_internal(self):
        d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core")
        self.internal_dir = os.path.join(d, "internal_figs")
        try:
            return json.load(open(os.path.join(d, "macro_internal.json"), encoding="utf-8"))
        except Exception:
            return {}

    def on_sheet_block(self, code, name=""):
        # Click trai chi CHON khoi; xem chuc nang / mo phong qua menu chuot phai.
        self._last_block_code = (code or "").upper()
        self.status("Selected block %s (%s). Right-click for: View function / Simulate block."
                    % (name or "", self._last_block_code))

    def _show_func_table(self, bid, name=""):
        """Click khoi F(x): hien bang x-y + duong cong."""
        from core import sheet_sim as SS
        pts = SS.func_points(self.db_path, self.cur_sheet, bid)
        if not pts:
            self.status("Khoi F(x) nay khong doc duoc bang gay khuc.")
            return
        fname = SS.func_name(self.db_path, self.cur_sheet, bid) or name or "F(x)"
        from ui.plot_dialog import FuncViewDialog
        self._func_dlg = FuncViewDialog(pts, title=fname, parent=self)
        self._func_dlg.show()

    def show_internal_logic(self, code, name=""):
        code = (code or "").upper()
        info = self.internal_map.get(code)
        if not info:
            self.status("Block %s (%s): manual has no internal logic diagram (usually a primitive block)."
                        % (name or "", code))
            return
        path = os.path.join(self.internal_dir, info["img"])
        if not os.path.exists(path):
            self.status("Thieu file hinh: %s" % info["img"])
            return
        title = "Internal logic: %s (%s) - manual %s p.%s" % (
            name or "", code, info.get("manual", ""), info.get("page", ""))
        ImageViewer(path, title, self).exec()


    def open_block_sim(self):
        code = self._last_block_code
        if not code:
            self.status("Click a block on the sheet first, then click 'Simulate block'.")
            return
        if has_behavior(code):
            BlockSimDialog(code, "", self).exec()
        elif has_analog(code):
            AnalogSimDialog(code, "", self).exec()
        else:
            self.status("Block %s has no simulation model yet (available: MOV/SWGR family and MV/SV/PID)." % code)

    def block_context_menu(self, code, name, bid, global_pos):
        code = (code or "").upper()
        m = QMenu(self)
        a_graph = m.addAction("View signal node diagram")
        a_view = m.addAction("View function (internal logic)")
        a_live = m.addAction("Draw internal logic (design)")
        a_sim = m.addAction("Block parameters (edit for simulation)")
        a_view.setEnabled(code in self.internal_map)
        a_live.setEnabled(bool(code))
        has_db = (getattr(self, "db_path", None) is not None
                  and getattr(self, "cur_sheet", None) is not None)
        a_sim.setEnabled(has_db and bid is not None)
        a_graph.setEnabled(has_db)
        act = m.exec(global_pos)
        if act == a_graph:
            from core.signal_graph import block_output_net
            net = block_output_net(self.db_path, self.cur_sheet, bid)
            self._open_node_tab(net, name)
        elif act == a_view:
            self.show_internal_logic(code, name)
        elif act == a_live:
            from ui.internal_design_dialog import InternalDesignDialog
            InternalDesignDialog(code, name, self,
                                 db_path=getattr(self, "db_path", None),
                                 sheet_id=getattr(self, "cur_sheet", None),
                                 bid=bid,
                                 sim_values=getattr(self, "sim_values", None),
                                 dig_env=getattr(self, "sim_env", None),
                                 ana_env=getattr(self, "sim_analog", None)).exec()
        elif act == a_sim:
            self._last_block_code = code
            from ui.block_param_dialog import BlockParamDialog
            # sau khi ap dung tham so -> tinh lai sheet ngay (neu dang bat mo phong)
            def _after():
                sc = getattr(self, "sheet_scene", None)
                if sc is not None and getattr(sc, "sim_values", None) is not None:
                    self._apply_sheet_sim()      # dang bat mo phong -> tinh lai ngay
            BlockParamDialog(self.db_path, bid, code, name, self, on_applied=_after,
                             sim_values=getattr(self, "sim_values", None),
                             sheet_id=getattr(self, "cur_sheet", None),
                             dig_env=getattr(self, "sim_env", None),
                             ana_env=getattr(self, "sim_analog", None)).exec()

    def signal_context_menu(self, net, linename, global_pos):
        """Chuot phai len 1 TIN HIEU (terminal) -> xem so do node."""
        if getattr(self, "db_path", None) is None or getattr(self, "cur_sheet", None) is None:
            return
        m = QMenu(self)
        a_graph = m.addAction("View signal node diagram")
        sc = getattr(self, "sheet_scene", None)
        osc_ok = bool(sc is not None and sc._sim_on() and net in sc.sim_inputs
                      and sc.sim_kind.get(net) == "A")
        a_osc = m.addAction("⏲ Set oscillation...")
        a_osc.setEnabled(osc_ok)
        if not osc_ok:
            a_osc.setToolTip("Only for an ANALOG input point, while 'Simulate on sheet' is ON")
        a_ai = m.addAction("Explain (AI)")
        act = m.exec(global_pos)
        if act == a_graph:
            self._open_node_tab(net, linename or net)
        elif act == a_osc:
            self._open_osc_dialog(net, linename)
        elif act == a_ai:
            try:
                from core import project_index as PI
                PI.ensure(list(getattr(self, "meta_by_path", {}).keys()))
            except Exception:
                pass
            from ui.ai_dialog import AIExplainDialog
            self._ai_dlg = AIExplainDialog(self.db_path, self.cur_sheet, net,
                                           cpu_paths=getattr(self, "cpu_paths", None), parent=self)
            self._ai_dlg.show()

    def _open_node_tab(self, net, title):
        """Nap tin hieu vao TAB 'So do node' va chuyen sang tab do."""
        self.graph_tab.set_target(self.db_path, self.cur_sheet, net, title,
                                  cpu_paths=getattr(self, "cpu_paths", None))
        self.center_tabs.setCurrentWidget(self.graph_tab)

    def _default_sim_analog(self, db, sheet):
        """Cac net analog la dau vao that (chua co khoi nao mo hinh sinh ra) -> mac dinh = 0
        thay vi de trong (~), nguoi dung van bam vao de sua lai gia tri khac neu can."""
        from core import sheet_sim as SS
        try:
            kinds = SS._kind_map(db, sheet)
            return {n: 0.0 for n, _ in SS.input_nets(db, sheet) if kinds.get(n) == "A"}
        except Exception:
            return {}

    def _seed_sim_global(self, db, sheet, digital, analog, terms=None):
        """Ap gia tri da tung tinh o SHEET KHAC (luu trong self.sim_global, khoa theo
        (db, Line Name.upper())) vao cac terminal DAU VAO (ben trai, t.side=='L') cua
        sheet dang mo, GHI DE len mac dinh 0. Sua truc tiep 2 dict digital/analog truyen vao.
        terms=None -> lay tu sheet_scene dang hien thi (nhu truoc); truyen terms rieng (tu
        sheet_render.build_sheet) de dung cho sheet KHONG hien thi (dao dong nen)."""
        if terms is None:
            sc = getattr(self, "sheet_scene", None)
            if sc is None or not getattr(self, "sim_global", None):
                return
            terms = sc.sh.terms
        elif not getattr(self, "sim_global", None):
            return
        from core import sheet_sim as SS
        try:
            kinds = SS._kind_map(db, sheet)
        except Exception:
            kinds = {}
        # Net do CHINH sheet nay tinh ra (dau ra 1 khoi tren sheet) thi TUYET DOI khong
        # duoc gieo gia tri ngoai vao: gieo se GHI DE ket qua tinh, lam khoi sinh ra no
        # (vd ASW/SW) trong nhu "khong hoat dong" va tin hieu hoi tiep noi bo dung yen.
        # (net nao la dau vao THAT thi input_nets() liet ke; con lai = do sheet tu tinh)
        try:
            free_in = {n for n, _ in SS.input_nets(db, sheet)}
            local_prod = {t.lid for t in terms if t.lid and t.lid not in free_in}
        except Exception:
            local_prod = set()
        for t in terms:
            if t.side != "L" or not t.lid or not t.linename:
                continue
            if t.lid in local_prod:
                continue
            key = (db, t.linename.strip().upper())
            if key not in self.sim_global:
                continue
            v = self.sim_global[key]
            if kinds.get(t.lid) == "A":
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    analog[t.lid] = float(v)
            else:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    digital[t.lid] = 1 if v > 0.5 else 0

    def _export_sim_global(self, db, sheet, values, terms=None):
        """Sau khi tinh xong 1 sheet: ghi gia tri cac terminal DAU RA (ben phai, t.side=='R')
        co ten vao kho toan cuc self.sim_global, de sheet KHAC mo sau se lay duoc.
        terms=None -> lay tu sheet_scene dang hien thi; truyen rieng cho sheet nen (xem tren)."""
        if terms is None:
            sc = getattr(self, "sheet_scene", None)
            if sc is None:
                return
            terms = sc.sh.terms
        for t in terms:
            if t.side != "R" or not t.lid or not t.linename:
                continue
            v = values.get(t.lid)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.sim_global[(db, t.linename.strip().upper())] = v

    def _default_sim_digital(self, db, sheet):
        """Cac net DIGITAL la dau vao that (chua co khoi nao mo hinh sinh ra) -> mac dinh = 0,
        khop voi cach hien thi hien tai (net chua set van ve la '0', khong con trang thai '?').
        Neu khong lam vay, cac khoi doi hoi DU tat ca dau vao (WSUM, ADD...) se ra rong khi
        chi 1 trong so cac dau vao chua thuc su duoc bam set, du man hinh van hien '0' nhu binh
        thuong khien nguoi dung tuong da du du lieu. Nguoi dung van bam de doi lai gia tri khac."""
        from core import sheet_sim as SS
        try:
            kinds = SS._kind_map(db, sheet)
            return {n: 0 for n, _ in SS.input_nets(db, sheet) if kinds.get(n) != "A"}
        except Exception:
            return {}

    def _osc_tick(self):
        """Tick nen (0.1s) cho tat ca diem dang DAO DONG (self.sim_osc), bat ke sheet nao.
        Moi diem tu quyet dinh luc nao thuc su can gia tri moi (theo "rate" rieng). Sheet
        dang HIEN THI thi ve lai ngay (nhu click tay); sheet KHAC thi tinh ngam + xuat sang
        sim_global de van lan xuyen sheet duoc, khong ve UI (tiet kiem)."""
        osc = getattr(self, "sim_osc", None)
        if not osc:
            return
        import time, math, random
        now = time.monotonic()
        by_sheet = {}
        for key, cfg in list(osc.items()):
            db, sheet, net = key
            if now < cfg.get("_next", 0):
                continue
            lo, hi = cfg["lo"], cfg["hi"]
            if cfg["mode"] == "period":
                cfg["_t"] = cfg.get("_t", 0.0) + cfg["rate"]
                mid, amp = (lo + hi) / 2.0, (hi - lo) / 2.0
                cfg["value"] = mid + amp * math.sin(2 * math.pi * cfg["_t"] / max(cfg["period"], 0.1))
            else:
                step = (hi - lo) * 0.15
                v = cfg.get("value", (lo + hi) / 2.0) + random.uniform(-step, step)
                cfg["value"] = max(lo, min(hi, v))
            cfg["_next"] = now + cfg["rate"]
            by_sheet.setdefault((db, sheet), []).append(net)
        for (db, sheet), nets in by_sheet.items():
            if db == getattr(self, "db_path", None) and sheet == getattr(self, "cur_sheet", None):
                ana = getattr(self, "sim_analog", {})
                for net in nets:
                    ana[net] = osc[(db, sheet, net)]["value"]
                self.sim_analog = ana
                # thoi gian that dang troi -> tien 1 buoc dt, khong giai lai tu dau
                self._apply_sheet_sim(advance=1)
            else:
                self._recompute_sheet_bg(db, sheet, nets)

    def _recompute_sheet_bg(self, db, sheet, nets):
        """Tinh ngam 1 sheet dang KHONG hien thi nhung co diem dang dao dong, de gia tri
        van lan xuyen sheet qua sim_global (giong het co che sheet dang mo). Khong dung
        sheet_scene (chua bi mo) -> tu dung sheet_render.build_sheet lay terms rieng."""
        try:
            from core import sheet_render as SR
            from core import sheet_sim as SS
            sh = SR.build_sheet(db, sheet)
        except Exception:
            return
        digital = self._default_sim_digital(db, sheet)
        analog = self._default_sim_analog(db, sheet)
        self._seed_sim_global(db, sheet, digital, analog, terms=sh.terms)
        for net in nets:
            cfg = self.sim_osc.get((db, sheet, net))
            if cfg is not None:
                analog[net] = cfg["value"]
        try:
            values, _ = SS.simulate(db, sheet, digital, analog)
        except Exception:
            return
        self._export_sim_global(db, sheet, values, terms=sh.terms)

    def _open_osc_dialog(self, net, linename):
        """Chuot phai tren 1 tin hieu ANALOG dau vao (dang simulate) -> mo dialog cau hinh
        dao dong. Chi BAT/DUNG that su khi nguoi dung bam nut trong dialog (khong tu ap
        dung khi dang go so)."""
        from ui.osc_dialog import OscillationDialog
        key = (self.db_path, self.cur_sheet, net)
        cfg = self.sim_osc.get(key)
        dlg = OscillationDialog(net, linename, cfg, self)
        dlg.exec()
        if dlg.stop_requested:
            self.sim_osc.pop(key, None)
            self.status("Da dung dao dong: %s" % (linename or net))
        elif dlg.result_cfg is not None:
            import time
            c = dict(dlg.result_cfg)
            c["_next"] = time.monotonic()
            c["_t"] = 0.0
            c["value"] = getattr(self, "sim_analog", {}).get(net, (c["lo"] + c["hi"]) / 2.0)
            self.sim_osc[key] = c
            self.status("Da bat dao dong: %s" % (linename or net))
        else:
            return          # bam Dong / Cancel -> khong doi gi
        self._apply_sheet_sim()

    def toggle_sheet_sim(self, on):
        """Bat/tat lop phu mo phong ngay tren trang logic."""
        sc = getattr(self, "sheet_scene", None)
        if sc is None:
            return
        if on:
            if getattr(self, "cur_sheet", None) is None:
                self.status("Open a sheet first.")
                self.sim_sheet_act.setChecked(False)
                return
            self.sim_env = self._default_sim_digital(self.db_path, self.cur_sheet)
            self.sim_analog = self._default_sim_analog(self.db_path, self.cur_sheet)
            self._seed_sim_global(self.db_path, self.cur_sheet, self.sim_env, self.sim_analog)
            self.sim_dyn_over = {}
            self.station_sims.pop((self.db_path, self.cur_sheet), None)  # bat lai -> khoi tram tu 0
            self.sim_dyn_state.pop((self.db_path, self.cur_sheet), None)
            sc.on_sim_toggle = self._sim_toggle
            sc.on_sim_set_analog = self._sim_set_analog
            sc.on_sim_dyn_config = self._sim_dyn_config
            self._apply_sheet_sim()
            from core import sheet_dyn as _DYN
            self.sim_run_act.setEnabled(_DYN.has_dynamic(self.db_path, self.cur_sheet))
            self.status(self._sim_on_msg())
        else:
            sc.clear_sim()
            db, sh = getattr(self, "db_path", None), getattr(self, "cur_sheet", None)
            if getattr(self, "sim_osc", None):     # tat simulate -> dung luon dao dong cua sheet nay
                for k in [k for k in self.sim_osc if k[0] == db and k[1] == sh]:
                    self.sim_osc.pop(k, None)
            self.station_sims.pop((db, sh), None)  # tat -> huy state khoi tram dang tich luy
            self.sim_dyn_state.pop((db, sh), None)
            self._stop_sim_run()
            self.sim_run_act.setEnabled(False)
            self.status("Sheet simulation turned off.")

    def toggle_sim_run(self, on):
        """Nut "Run time": cho thoi gian mo phong troi deu, moi nhip tien 1 dt.

        Khac voi cach tinh binh thuong (doi dau vao -> nhay THANG toi trang thai on dinh),
        o day nguoi dung thay khoi tich phan bo dan len, loc tre duoi theo, timer dem nguoc.
        Nhip that = dt (kep trong 0,2s..2s) nen thoi gian mo phong chay xap xi thoi gian that."""
        if not on:
            self._run_timer.stop()
            if self._sim_time:
                self.status("Dung dong ho o t = %.1fs mo phong." % self._sim_time)
            return
        from core import sheet_dyn as DYN
        if not self.sim_sheet_act.isChecked() or getattr(self, "cur_sheet", None) is None:
            self.sim_run_act.setChecked(False)
            self.status("Bat 'Simulate on sheet' truoc da.")
            return
        if not DYN.has_dynamic(self.db_path, self.cur_sheet):
            self.sim_run_act.setChecked(False)
            self.status("Sheet nay khong co khoi dong nao - thoi gian troi cung khong lam "
                        "gia tri nao doi. Dau ra da dung san roi.")
            return
        self._sim_time = 0.0
        dt = float(getattr(self, "_dyn_dt", 0.5))
        self._run_timer.start(int(min(max(dt * 1000.0, 200.0), 2000.0)))
        self.status("Dong ho chay: moi nhip tien %.2fs mo phong. Doi dau vao bat ky luc nao, "
                    "dau ra se bo theo." % dt)

    def _stop_sim_run(self):
        """Dung dong ho (tat simulate / doi sheet) - khong de no chay tiep tren sheet khac."""
        if getattr(self, "sim_run_act", None) is not None and self.sim_run_act.isChecked():
            self.sim_run_act.setChecked(False)      # keo theo toggle_sim_run(False)
        elif getattr(self, "_run_timer", None) is not None:
            self._run_timer.stop()

    def _run_tick(self):
        """1 nhip dong ho: tien dung 1 dt tu trang thai dang co."""
        if not self.sim_sheet_act.isChecked() or getattr(self, "cur_sheet", None) is None:
            self._stop_sim_run()
            return
        dt = float(getattr(self, "_dyn_dt", 0.5))
        try:
            self._apply_sheet_sim(advance=1)
        except Exception as e:
            self._stop_sim_run()
            self.status("Dong ho dung vi loi: %s" % e)
            return
        self._sim_time += dt
        d = getattr(self, "_dyn_last", None)
        self.status("▶ t = %.1fs mo phong (dt %.2fs, %d khoi dong). Bam lai nut de dung."
                    % (self._sim_time, dt, d[2] if d else 0))

    def _dyn_info(self, db, sh, live_values=None):
        """{bid: {ti, out, code, label}} cac khoi dong (tich phan) de danh dau tren sheet.
        live_values: ket qua sheet_sim.simulate() vua tinh - bom vao chan vao khoi TRAM de
        badge phan anh dung tin hieu dang chay toi (xem ghi chu trong sheet_dyn._dyn_blocks).
        Dung self.station_sims[(db,sh)] lam sim_cache de MV khoi TRAM tich luy xuyen cac lan goi."""
        from core import sheet_dyn as DYN
        from core import ai_explain as AE
        info = {}
        cache = self.station_sims.setdefault((db, sh), {})
        try:
            for b in DYN._dyn_blocks(db, sh, getattr(self, "sim_dyn_over", {}),
                                     live_values=live_values, sim_cache=cache):
                if b["kind"] == "S":
                    info[b["bid"]] = {"kind": "S", "code": b["code"],
                                      "name": AE._catalog().get(b["code"], {}).get("short", b["code"]),
                                      "outs": dict(b.get("last_out") or {}),
                                      "in_nets": b["in_nets"], "out_nets": b["out_nets"],
                                      "real_params": dict(b["sim"].params)}
                elif b["kind"] == "T":
                    # Khoi timer KHONG co khoa "ti" nhu khoi tich phan - doc thang
                    # b["ti"] o day se nem KeyError va lam mat sach badge cua MOI khoi
                    # dong tren sheet do.
                    info[b["bid"]] = {"kind": "T", "out": b["out"], "code": b["code"],
                                      "tmr": b.get("tmr"), "T": b.get("Tef", b.get("T")),
                                      "toff": b.get("toff"), "left": DYN.timer_left(b)}
                else:
                    info[b["bid"]] = {"ti": b["ti"], "out": b["out"], "code": b["code"],
                                      "kind": b.get("kind", "I")}
                    if b.get("kind") == "R":
                        info[b["bid"]]["up"] = b.get("up")
                        info[b["bid"]]["dn"] = b.get("dn")
        except Exception:
            pass
        return info

    def _sim_timer_config(self, bid, cur, over):
        """Click khoi delay/xung: cai thoi gian (giay), dt, so buoc + nut Chay.

        Khoi tich phan co TI va "gia tri dau"; timer thi khong - no chi co DUY NHAT 1
        con so la thoi gian dat. Dung chung hop thoai cu se hien 2 o vo nghia va ghi
        nham khoa 'ti' vao overrides."""
        ten = {"DI": "Tre BAT (on-delay)", "DIL": "Tre BAT (on-delay, dat bang phut)",
               "DT": "Tre TAT (off-delay)", "PO": "Xung mot nhat SS1 (giu 1 khoang T)",
               "TDWO": "Xung mot nhat SS2 (dau vao tat la cat xung ngay)",
               "PG": "Mach dao dong co cong"}
        fam = cur.get("tmr") or "timer"
        dlg = QDialog(self)
        dlg.setWindowTitle("%s - %s" % (fam, ten.get(fam, "delay/xung")))
        form = QFormLayout(dlg)
        cur_t = over.get(bid, {}).get("tsec", cur.get("T"))
        sp_t = QDoubleSpinBox(); sp_t.setRange(0.0, 1e6); sp_t.setDecimals(3)
        sp_t.setValue(float(cur_t) if cur_t is not None else 0.0)
        # Quy HET ve giay (DIL dat bang phut tren ban ve da doi san) de so thang voi dt.
        form.addRow("T - thoi gian (giay):", sp_t)
        if fam == "PG":
            off = cur.get("toff")
            form.addRow("Nua chu ky TAT (giay):",
                        QLabel("%g" % off if isinstance(off, (int, float)) else "?"))
        sp_dt = QDoubleSpinBox(); sp_dt.setRange(0.01, 60.0); sp_dt.setDecimals(2)
        sp_dt.setSingleStep(0.1); sp_dt.setValue(float(getattr(self, "_dyn_dt", 0.5)))
        sp_steps = QSpinBox(); sp_steps.setRange(1, 100000)
        sp_steps.setValue(int(getattr(self, "_dyn_steps", 300)))
        form.addRow("dt - time step (seconds):", sp_dt)
        form.addRow("Steps:", sp_steps)
        lbl_t = QLabel(""); form.addRow("Total time:", lbl_t)

        def _upd():
            # Canh bao thang: dt qua tho thi timer khong bao gio dem toi noi.
            tong = sp_dt.value() * sp_steps.value()
            th = " - CHUA DU DAI cho T=%gs!" % sp_t.value() if tong < sp_t.value() else ""
            lbl_t.setText("%.1f s%s" % (tong, th))
        for w in (sp_dt, sp_steps, sp_t):
            w.valueChanged.connect(_upd)
        _upd()
        row = QHBoxLayout()
        b_run = QPushButton("\u25b6 Run dynamic"); b_close = QPushButton("Close")
        row.addStretch(1); row.addWidget(b_close); row.addWidget(b_run)
        form.addRow(row)

        def _apply_run():
            over[bid] = {"tsec": sp_t.value()}
            self.sim_dyn_over = over
            self._dyn_dt = sp_dt.value(); self._dyn_steps = sp_steps.value()
            dlg.accept()
            self.run_dynamic_sim()
        b_run.clicked.connect(_apply_run)
        b_close.clicked.connect(dlg.reject)
        dlg.exec()

    def _sim_dyn_config(self, bid):
        """Click khoi dong (cam): hop cai dat TI, gia tri dau, dt, so buoc + nut Chay."""
        over = getattr(self, "sim_dyn_over", {})
        cur = dict(self.sheet_scene.sim_dyn.get(bid, {}))
        if cur.get("kind") == "S":
            self._sim_station_config(bid, cur, over)
            return
        if cur.get("kind") == "T":
            self._sim_timer_config(bid, cur, over)
            return
        cur_ti = over.get(bid, {}).get("ti", cur.get("ti") or 1.0)
        cur_init = over.get(bid, {}).get("init", 0.0)

        kind = cur.get("kind")
        titles = {"D": "Derivative settings", "L": "F(t) lag filter settings", "R": "Rate limiter settings"}
        plabels = {"D": "G - gain:", "L": "T - time constant (seconds):"}
        dlg = QDialog(self)
        dlg.setWindowTitle(titles.get(kind, "Integrator settings"))
        form = QFormLayout(dlg)
        sp_up = sp_dn = None
        if kind == "R":
            cur_up = over.get(bid, {}).get("up", cur.get("up"))
            cur_dn = over.get(bid, {}).get("dn", cur.get("dn"))
            sp_up = QDoubleSpinBox(); sp_up.setRange(0.0, 1e9); sp_up.setDecimals(4)
            sp_up.setValue(float(cur_up) if cur_up is not None else 0.0)
            sp_dn = QDoubleSpinBox(); sp_dn.setRange(0.0, 1e9); sp_dn.setDecimals(4)
            sp_dn.setValue(float(cur_dn) if cur_dn is not None else 0.0)
            form.addRow("IR tang (up rate, don vi/giay):", sp_up)
            form.addRow("IR giam (down rate, don vi/giay):", sp_dn)
            sp_ti = None
        else:
            sp_ti = QDoubleSpinBox(); sp_ti.setRange(-1e6, 1e6); sp_ti.setDecimals(3); sp_ti.setValue(float(cur_ti))
            form.addRow(plabels.get(kind, "TI - time constant (seconds):"), sp_ti)
        sp_init = QDoubleSpinBox(); sp_init.setRange(-1e9, 1e9); sp_init.setDecimals(3); sp_init.setValue(float(cur_init))
        sp_dt = QDoubleSpinBox(); sp_dt.setRange(0.01, 60.0); sp_dt.setDecimals(2); sp_dt.setSingleStep(0.1); sp_dt.setValue(float(getattr(self, "_dyn_dt", 0.5)))
        sp_steps = QSpinBox(); sp_steps.setRange(1, 100000); sp_steps.setValue(int(getattr(self, "_dyn_steps", 300)))
        form.addRow("Initial output value:", sp_init)
        form.addRow("dt - time step (seconds):", sp_dt)
        form.addRow("Steps:", sp_steps)
        lbl_t = QLabel(""); form.addRow("Total time:", lbl_t)
        def _upd():
            lbl_t.setText("%.1f s" % (sp_dt.value() * sp_steps.value()))
        sp_dt.valueChanged.connect(_upd); sp_steps.valueChanged.connect(_upd); _upd()
        row = QHBoxLayout()
        b_run = QPushButton("▶ Run dynamic"); b_close = QPushButton("Close")
        row.addStretch(1); row.addWidget(b_close); row.addWidget(b_run)
        form.addRow(row)

        def _apply_run():
            if kind == "R":
                over[bid] = {"up": sp_up.value(), "dn": sp_dn.value(), "init": sp_init.value()}
            else:
                over[bid] = {"ti": sp_ti.value(), "init": sp_init.value()}
            self.sim_dyn_over = over
            self._dyn_dt = sp_dt.value(); self._dyn_steps = sp_steps.value()
            dlg.accept()
            self.run_dynamic_sim()
        b_run.clicked.connect(_apply_run)
        b_close.clicked.connect(dlg.reject)
        dlg.exec()

    def _sim_station_config(self, bid, cur, over):
        """Hop cai dat khoi TRAM (MV/SV/MV-POS/SV-MV...). Theo dung than lenh TAG_MCR.DEF goc:
        - Chan CO DAY (Manual/DLT MV/HL-MV/POS/...): CHI hien gia tri THAT tu day (bam vao
          day tren sheet de doi) - khong sua duoc o day, dung y that ngoai doi (day nao dut
          day day).
        - Chan KHONG noi day (FF/MV/OR-R-MV1/OR-MV1/OR-R-MV2/OR-MV2/Hold): sua duoc THANG
          o day, vi khong co day nao khac de "nhan tu ben ngoai" ca - day la cach duy nhat
          de dat gia tri cho chung khi mo phong.
        - RIENG "Auto": than lenh goc co 2 nguon DOC LAP, OR voi nhau, de dua che do Auto len
          1 - (1) chan vao "Auto" tu day ben ngoai, va (2) nut vat ly "AUT" tren mat tram
          (OPS_IN5) ma nguoi van hanh bam truc tiep, khong qua day nao. Cho phep dat CA HAI
          o day: 1 o ep gia tri chan "Auto" (tri-state, mac dinh theo dung day that), VA 1
          nut AUT rieng (nut vat ly, doc lap voi day)."""
        from core import analog_sim as AS
        from core import signal_graph as SG
        code = cur.get("code")
        spec = AS.load_analog().get(code, {})
        in_nets = cur.get("in_nets", {})
        ov = dict(over.get(bid, {}))
        ov_in = dict(ov.get("inputs") or {})
        ov_pm = dict(ov.get("params") or {})
        ov_ops = dict(ov.get("ops") or {})
        real_pm = cur.get("real_params") or {}   # gia tri THAT da cau hinh trong DB (CAD_BLOCK_PARAM)

        # ----- doc CAU HINH THAT tu DB cho chinh khoi nay -----
        # 1) Ttag (KKS) + ten thiet bi: PARAMNO 1 va 2 cua CAD_BLOCK_PARAM (vd
        #    '10LAB33AA502' / 'M-BFP MIN FCV') - hien len dau cho biet dang chinh khoi nao.
        # 2) THU TU CHAN THAT 1..18 tu CAD_BLOCK_PIN + macro pins - hop thoai truoc day
        #    liet ke theo thu tu file JSON va bi MAT TEN CHAN (nhu anh chup), gio moi dong
        #    deu co ten chan ro rang, dung thu tu nhu tren khoi ve.
        ttag = tdes = ""
        raw_pm = {}             # {PARAMNO(str): gia tri tho} - de hien ca tham so CHUA co ten
        pin_order = []          # [(ten_chan)] theo PINNO tang dan
        try:
            import sqlite3 as _sq
            _c = _sq.connect(self.db_path).cursor()
            for no, v in _c.execute("SELECT PARAMNO,PARAMVALUE FROM CAD_BLOCK_PARAM "
                                    "WHERE BLOCK_ID=?", (bid,)):
                raw_pm[str(no)] = v
                if str(no) == "1":
                    ttag = (v or "").strip()
                elif str(no) == "2":
                    tdes = (v or "").strip()
            r = _c.execute("SELECT SYMBOL FROM CAD_BLOCK WHERE BLOCK_ID=?", (bid,)).fetchone()
            if r:
                from core import sheet_render as _SR
                pdef = (_SR._macro_pins().get(r[0] or "") or {}).get("pins", {})
                for pn in sorted(pdef, key=lambda x: int(x)):
                    inf = pdef[pn]
                    if inf.get("side") == "in" and inf.get("name"):
                        pin_order.append(inf["name"])
        except Exception:
            pass
        spec_in = spec.get("inputs") or {}
        if not pin_order:                       # khong doc duoc macro -> theo spec nhu cu
            pin_order = list(spec_in.keys())

        dlg = QDialog(self)
        title = "%s (%s)" % (cur.get("name") or code, code)
        if ttag:
            title = "%s  -  %s %s" % (title, ttag, tdes)
        dlg.setWindowTitle(title)
        outer = QVBoxLayout(dlg)
        if ttag or tdes:
            hdr = QLabel("Tag: %s    %s" % (ttag or "?", tdes))
            hdr.setStyleSheet("font-weight:600; color:#0B3D91;")
            outer.addWidget(hdr)
        scroll_body = QWidget()
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(scroll_body)
        grid.setHorizontalSpacing(10); grid.setVerticalSpacing(4)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(scroll_body)
        outer.addWidget(scroll)

        note = QLabel("Chan CO DAY: hien tin hieu that dang noi (doi bang cach bam vao day "
                      "tren sheet). Chan KHONG noi day: sua thang o cot 'Dat gia tri'. "
                      "Rieng Auto/DLT MV/HL-MV/LL-MV co o Ep rieng.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748B; font-size:11px;")
        grid.addWidget(note, 0, 0, 1, 3)
        for ci, h in enumerate(("Chan", "Day (tin hieu that)", "Dat gia tri / Ep")):
            hh = QLabel(h); hh.setStyleSheet("font-weight:600; color:#334155;")
            grid.addWidget(hh, 1, ci)
        _row = [2]

        def _add(namelbl, wirelbl, ctrl=None):
            r = _row[0]; _row[0] += 1
            nl = QLabel(namelbl); nl.setStyleSheet("font-weight:600;")
            grid.addWidget(nl, r, 0)
            wl = QLabel(wirelbl)
            wl.setStyleSheet("color:%s;" % ("#334155" if wirelbl.startswith("(day") else "#94A3B8"))
            wl.setWordWrap(True)
            grid.addWidget(wl, r, 1)
            if ctrl is not None:
                grid.addWidget(ctrl, r, 2)
            return r

        widgets = {}   # name -> ("ops",opname,cb) nut AUT | ("tri",cb) ep chan Auto |
                       # ("bf",chk,"n",w) Ep so | ("b"/"n", w) chan khong noi day
        for name in pin_order:
            meta = spec_in.get(name, {})
            wired = name in in_nets
            if wired:
                net = in_nets[name]
                sig = SG._name_of(self.db_path, self.cur_sheet, net) or net
                wirelbl = "(day: %s)" % (sig or net)
            else:
                wirelbl = "khong noi day"
            if name == "Auto":
                had_ov = "Auto" in ov_in
                cb_ep = QCheckBox("Ep chan Auto")
                cb_ep.setTristate(True)
                cb_ep.setToolTip("Vuong = theo day that; Tick = ep 1; Trong = ep 0")
                if had_ov:
                    cb_ep.setCheckState(Qt.CheckState.Checked if ov_in.get("Auto")
                                        else Qt.CheckState.Unchecked)
                else:
                    cb_ep.setCheckState(Qt.CheckState.PartiallyChecked)
                _add("Auto", wirelbl, cb_ep)
                widgets["Auto_ep"] = ("tri", cb_ep)
                cb_aut = QCheckBox("Nut AUT vat ly (OPS_IN5) - doc lap voi day")
                cb_aut.setChecked(bool(ov_ops.get("OPS_IN5")))
                _add("", "", cb_aut)
                widgets["Auto_ops"] = ("ops", "OPS_IN5", cb_aut)
                continue
            if name in ("DLT MV", "HL-MV", "LL-MV"):
                # 3 chan nay thuong khong tinh duoc gia tri that qua day (DLT MV noi vao
                # hang so 0%, HL/LL-MV co the noi xuyen sheet khong resolve duoc) -> cho Ep.
                # HL-MV=LL-MV=0 se kep cung MV ve 0 - nguyen nhan pho bien khi "MV khong len".
                desc = {"DLT MV": "toc do tang/giam MV", "HL-MV": "gioi han TREN cho MV",
                        "LL-MV": "gioi han DUOI cho MV"}[name]
                had_ov = name in ov_in
                row_w = QWidget(); row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(0, 0, 0, 0)
                chk_ep = QCheckBox("Ep")
                row_l.addWidget(chk_ep)
                vw = QDoubleSpinBox(); vw.setRange(-1e9, 1e9); vw.setDecimals(3)
                vw.setValue(float(ov_in.get(name, 0.0)))
                vw.setEnabled(had_ov)
                chk_ep.setChecked(had_ov)
                chk_ep.toggled.connect(vw.setEnabled)
                row_l.addWidget(vw, 1)
                row_w.setToolTip(desc)
                _add(name, wirelbl, row_w)
                widgets[name] = ("bf", chk_ep, "n", vw)
                continue
            if wired:
                _add(name, wirelbl)
                continue
            # khong noi day gi ca -> sua truc tiep, khong co gi khac de "nhan" ca
            if meta.get("bool"):
                w = QCheckBox()
                w.setChecked(bool(ov_in.get(name, meta.get("init", 0))))
                widgets[name] = ("b", w)
            else:
                w = QDoubleSpinBox(); w.setRange(-1e9, 1e9); w.setDecimals(3)
                w.setValue(float(ov_in.get(name, meta.get("init", 0.0))))
                widgets[name] = ("n", w)
            _add(name, wirelbl, w)

        sep = QLabel("Tham so (gia tri THAT tu CAD_BLOCK_PARAM cua khoi nay):")
        sep.setStyleSheet("font-weight:600; color:#334155; padding-top:8px;")
        grid.addWidget(sep, _row[0], 0, 1, 3); _row[0] += 1

        form = QFormLayout()          # phan tham so + mo phong van dung form nhu cu
        form_holder = QWidget(); form_holder.setLayout(form)
        grid.addWidget(form_holder, _row[0], 0, 1, 3); _row[0] += 1
        pwidgets = {}
        for pname, pmeta in (spec.get("params") or {}).items():
            w = QDoubleSpinBox(); w.setRange(-1e9, 1e9); w.setDecimals(3)
            # uu tien: nguoi dung da chinh (ov_pm) > gia tri THAT trong DB (real_pm) > mac dinh JSON
            default_val = real_pm.get(pname, pmeta.get("val", 0.0))
            w.setValue(float(ov_pm.get(pname, default_val)))
            pwidgets[pname] = w
            form.addRow("%s%s:" % (pname, ("  (%s)" % pmeta["desc"]) if pmeta.get("desc") else ""), w)
        # Tham so SO trong DB ma spec CHUA dat ten (vd PARAMNO 17 = Category cua 820D/F,
        # PARAMNO 12-13 cua 820E): engine VAN dung gia tri that (set_params_by_no nap theo
        # so), nhung truoc day khong hien ra day - nguoi dung khong thay/khong sua duoc.
        # Hien them theo dang 'PARAMNO n'; sua duoc vi sim.set_param() chap nhan khoa so.
        try:
            from core.block_params import param_names as _pnames
            named_nos = {str(v) for v in _pnames(code).keys()}
        except Exception:
            named_nos = set()
        def _isnum(x):
            try:
                float(x); return True
            except (TypeError, ValueError):
                return False
        for no in sorted(raw_pm, key=lambda x: int(x) if x.isdigit() else 999):
            v = raw_pm[no]
            if not no.isdigit() or int(no) < 5 or no in named_nos or not _isnum(v):
                continue
            if no in pwidgets:
                continue
            w = QDoubleSpinBox(); w.setRange(-1e9, 1e9); w.setDecimals(3)
            w.setValue(float(ov_pm.get(no, float(v))))
            pwidgets[no] = w
            form.addRow("PARAMNO %s  (chua co ten trong tai lieu - gia tri that tu DB):" % no, w)
        # Diem xuat phat cua bo tich phan (VD MV dang la 200). KHOI THAT KHONG co chan
        # nao de dat gia tri nay - MV nam trong bo nho noi va duoc giu qua cac vong quet;
        # o day chi la dieu kien ban dau cho MO PHONG (de trong = khoi dong nguoi tu 0).
        sp_init = QDoubleSpinBox(); sp_init.setRange(-1e9, 1e9); sp_init.setDecimals(3)
        sp_init.setSpecialValueText("(khoi dong nguoi - tu 0)")
        sp_init.setValue(float(ov.get("init_out", sp_init.minimum())))
        form.addRow("Gia tri dau ra ban dau (MV hien tai - chi cho mo phong):", sp_init)

        # TI cho bo tich phan NOI cua tram. Logic goc dat TI = chu ky quet nen moi vong
        # cong THANG DLT MV (chay rat nhanh). Dat TI = so giay de moi vong chi cong
        # DLT MV * dt / TI  -> quan sat duoc qua trinh thay doi.
        sp_ti = QDoubleSpinBox(); sp_ti.setRange(0.0, 1e6); sp_ti.setDecimals(2)
        sp_ti.setSpecialValueText("(theo logic goc - TI = chu ky quet)")
        sp_ti.setValue(float(ov.get("ti", 0.0)))
        form.addRow("TI - hang so thoi gian tich phan noi (giay):", sp_ti)

        sp_dt = QDoubleSpinBox(); sp_dt.setRange(0.01, 60.0); sp_dt.setDecimals(2); sp_dt.setSingleStep(0.1)
        sp_dt.setValue(float(getattr(self, "_dyn_dt", 0.5)))
        sp_steps = QSpinBox(); sp_steps.setRange(1, 100000); sp_steps.setValue(int(getattr(self, "_dyn_steps", 300)))
        form.addRow("dt - time step (seconds):", sp_dt)
        form.addRow("Steps:", sp_steps)
        lbl_t = QLabel(""); form.addRow("Total time:", lbl_t)
        def _upd():
            lbl_t.setText("%.1f s" % (sp_dt.value() * sp_steps.value()))
        sp_dt.valueChanged.connect(_upd); sp_steps.valueChanged.connect(_upd); _upd()
        row = QHBoxLayout()
        b_run = QPushButton("▶ Run dynamic"); b_close = QPushButton("Close")
        row.addStretch(1); row.addWidget(b_close); row.addWidget(b_run)
        outer.addLayout(row)
        dlg.resize(760, 760)

        def _apply_run():
            new_in = {}
            new_ops = {}
            for name, tup in widgets.items():
                if tup[0] == "ops":
                    _kind, opname, cb = tup
                    if cb.isChecked():
                        new_ops[opname] = 1
                elif tup[0] == "tri":      # ep chan 'Auto' (day) - 3 trang thai
                    _kind, cb = tup
                    st = cb.checkState()
                    if st != Qt.CheckState.PartiallyChecked:
                        new_in["Auto"] = 1 if st == Qt.CheckState.Checked else 0
                elif tup[0] == "bf":       # ep chan 'DLT MV' (day, so) - chi khi tick Ep
                    _kind, chk_ep, k, w = tup
                    if chk_ep.isChecked():
                        new_in[name] = w.value()
                else:                       # chan khong noi day, sua truc tiep
                    k, w = tup
                    new_in[name] = (1 if w.isChecked() else 0) if k == "b" else w.value()
            new_pm = {pname: w.value() for pname, w in pwidgets.items()}
            over[bid] = {"inputs": new_in, "params": new_pm, "ops": new_ops}
            if sp_init.value() > sp_init.minimum():     # de trong = khoi dong nguoi tu 0
                over[bid]["init_out"] = sp_init.value()
            if sp_ti.value() > 0:                       # de trong = theo logic goc
                over[bid]["ti"] = sp_ti.value()
            self.sim_dyn_over = over
            # nguoi dung vua sua tham so/init_out -> bo sim DANG TICH LUY cua khoi nay de
            # lan _apply_sheet_sim() ke tiep dung lai tu dau voi cau hinh MOI (khong thi
            # cai cu se tiep tuc tich luy, bo qua thay doi nguoi dung vua nhap)
            self.station_sims.get((self.db_path, self.cur_sheet), {}).pop(bid, None)
            self._dyn_dt = sp_dt.value(); self._dyn_steps = sp_steps.value()
            dlg.accept()
            # Cap nhat badge NGAY (mach don-buoc, giong nhu bam 1 tin hieu tay) truoc,
            # de dau ra da EP hien ra dung ngay ca khi "Simulate on sheet" dang TAT hoac
            # nguoi dung khong bam "Run dynamic" - khong phai cho chay xong mo phong da
            # buoc (chi lam viec khi Simulate on sheet dang BAT) moi thay duoc gia tri ep.
            if getattr(self, "cur_sheet", None) is not None:
                try:
                    self._apply_sheet_sim()
                except Exception:
                    pass
            self.run_dynamic_sim()
        b_run.clicked.connect(_apply_run)
        b_close.clicked.connect(dlg.reject)
        dlg.exec()

    def _apply_sheet_sim(self, advance=None):
        """Tinh lai ca sheet va ve len.

        Sheet CO khoi dong (tich phan / loc tre / gioi han toc do / khoi TAG co than lenh)
        thi mac dinh CHAY DONG luon, khong bat nguoi dung phai di tim khoi mau cam roi bam
        "Run dynamic": de nguyen thi dau ra khoi tich phan dung im o 0 va moi gia tri phia
        sau no deu sai. Chay den khi ON DINH roi dung (do duoc: hau het sheet on dinh sau
        5 buoc, nen re hon chay du 300 buoc khoang 9-47 lan); nsteps chi con la tran an
        toan cho khoi tich phan bi lech thuong truc - loai nay ramp mai, khong bao gio
        on dinh.
        Sheet KHONG co khoi dong (68% so sheet) di duong tinh nhu cu, khong ton them gi.

        advance: None = chay den on dinh (bat simulate, doi dau vao...).
                 So nguyen = tien dung tung ay buoc tu trang thai dang co - dung cho tick
                 DAO DONG (10 lan/giay): thoi gian that dang troi qua nen chi tien 1 buoc,
                 va do la cach duy nhat khoi loc tre bam duoc theo song dao dong."""
        from core import sheet_sim as SS
        from core import sheet_dyn as DYN
        db, sh = self.db_path, self.cur_sheet
        if DYN.has_dynamic(db, sh):
            try:
                self._apply_sheet_dyn(db, sh, advance)
                return
            except Exception as e:
                # hong o duong dong thi ve duong tinh, con hon de trong sheet
                self.status("Dynamic step failed (%s) - showing steady-state values." % e)
        self._dyn_last = None
        kinds = SS._kind_map(db, sh)
        values, _ = SS.simulate(db, sh, getattr(self, "sim_env", {}),
                                getattr(self, "sim_analog", {}))
        dyn = self._dyn_info(db, sh, values)   # khoi tram da step 1 buoc (co cache)
        # DAU RA KHOI TRAM (Auto/MV/ABN...): bom nguoc vao mach roi tinh THEM 1 luot.
        # Cac net nay bi coi la "dau vao" luc mo sheet (khoi khong co mo hinh tinh) nen
        # da bi gieo mac dinh 0 vao sim_env - ma overrides(digital) THANG analog trong
        # simulate(), nen neu khong loai ra thi so 0 cu DE LEN ket qua khoi vua tinh:
        # badge ghi "Auto" nhung day '11' (M-BFP MIN FCV AUTO) van 0 mai (bug da gap).
        souts = {}
        for _bid, inf in dyn.items():
            if inf.get("kind") != "S":
                continue
            for nm, net in (inf.get("out_nets") or {}).items():
                v = (inf.get("outs") or {}).get(nm)
                if net and isinstance(v, (int, float)) and not isinstance(v, bool):
                    souts[net] = v
        if souts:
            dig = {k: v for k, v in getattr(self, "sim_env", {}).items() if k not in souts}
            ana = dict(getattr(self, "sim_analog", {}))
            for net, v in souts.items():
                if kinds.get(net) == "A":
                    ana[net] = v
                else:
                    dig[net] = 1 if v > 0.5 else 0
            values, _ = SS.simulate(db, sh, dig, ana)
        inputs = [n for n, _ in SS.input_nets(db, sh) if n not in souts]
        self.sim_values = values          # luu lai de tai su dung (VD trong trinh ve logic noi)
        self._export_sim_global(db, sh, values)     # cho sheet KHAC mo sau lay lai duoc
        osc_nets = {net for (d, s, net) in getattr(self, "sim_osc", {}) if d == db and s == sh}
        self.sheet_scene.set_sim(values, kinds, inputs, getattr(self, "sim_analog", {}),
                                 dyn=dyn, osc_nets=osc_nets)

    def _sim_on_msg(self):
        """Cau trang thai khi vua bat simulate. Neu sheet co khoi dong thi noi ro la da
        chay dong san roi - nguoi dung khong phai doan xem so tren man hinh la gia tri
        tuc thoi hay gia tri da on dinh."""
        base = ("Simulation: DIGITAL inputs (\u25b8) click to cycle ? -> 1 -> 0; "
                "ANALOG (\u270e) click to enter a number.")
        d = getattr(self, "_dyn_last", None)
        if not d:
            return base + " No dynamic blocks on this sheet."
        steps, settled, nblk, dt = d
        return base + (" Ran %d dynamic blocks %d steps (%.0fs simulated) - %s. "
                       "Click an orange block to change TI/dt/steps."
                       % (nblk, steps, steps * dt,
                          "settled" if settled else "still moving, hit the step limit"))

    def _apply_sheet_dyn(self, db, sh, advance=None):
        """Duong DONG cua _apply_sheet_sim (xem giai thich o do)."""
        from core import sheet_sim as SS
        from core import sheet_dyn as DYN
        dt = getattr(self, "_dyn_dt", 0.5)
        state = self.sim_dyn_state.setdefault((db, sh), {})
        cache = self.station_sims.setdefault((db, sh), {})
        if advance:
            # run() giai gia tri ROI MOI tich phan trong cung 1 vong, va vong lap la
            # range(nsteps+1) -> nsteps+1 buoc tich phan. Muon tien DUNG 'advance' buoc dt
            # (1 nhip dong ho = 1 dt) thi phai tru 1, khong thi moi nhip di 2 buoc.
            nsteps, settle = max(int(advance) - 1, 0), 0
        else:
            nsteps, settle = getattr(self, "_dyn_steps", 300), 4
        st = {}
        # advance=None nghia la "doi dau vao roi giai lai cho on dinh" - chay toi 300
        # buoc dt, tuc NHAY 150s thoi gian mo phong. Voi khoi tich phan/loc tre do dung la
        # cai ta muon (gia tri xac lap), nhung voi TIMER thi no an mat sach delay: bam dau
        # vao 1->0 la khoi DT dem het 15s ngay trong 1 lan ve lai, nguoi dung thay dau ra
        # rot ve 0 tuc thi (loi da gap that). Timer chi duoc tien khi THOI GIAN THAT troi:
        # nhip dong ho "Run time" hoac dao dong (advance=1).
        val, _hist, blocks = DYN.run(
            db, sh, getattr(self, "sim_env", {}), getattr(self, "sim_analog", {}),
            dt=dt, nsteps=nsteps, overrides=getattr(self, "sim_dyn_over", {}),
            settle=settle, state=state, sim_cache=cache, stats=st,
            freeze_tmr=not advance)
        kinds = SS._kind_map(db, sh)
        dynouts = self._dyn_outs(blocks)
        inputs = [n for n, _ in SS.input_nets(db, sh) if n not in dynouts]
        self.sim_values = val
        self._export_sim_global(db, sh, val)
        osc_nets = {net for (d, sx, net) in getattr(self, "sim_osc", {}) if d == db and sx == sh}
        self.sheet_scene.set_sim(val, kinds, inputs, getattr(self, "sim_analog", {}),
                                 dyn=self._dyninfo(blocks), osc_nets=osc_nets)
        self._dyn_last = (st.get("steps", 0), bool(st.get("settled")), len(blocks), dt)
        if not advance:
            self._tmr_hint(blocks)

    def _tmr_hint(self, blocks):
        """Nhac khi co timer dang dem: con bao lau, va bam nut nao cho thoi gian troi.

        Sau khi da dong bang timer thi doi dau vao xong man hinh dung im - phai noi ro
        la dang GIU delay, khong thi nguoi dung tuong mo phong bi treo."""
        from core import sheet_dyn as DYN
        dem = [(b, DYN.timer_left(b)) for b in blocks if b["kind"] == "T"]
        dem = [(b, v) for b, v in dem if v is not None]
        if not dem:
            return
        b, v = min(dem, key=lambda t: t[1])
        act = getattr(self, "sim_run_act", None)
        self.status("%d khoi timer dang dem - %s con %.1fs.%s"
                    % (len(dem), b.get("tmr") or "timer", v,
                       "" if (act is not None and act.isChecked())
                       else " Bam '\u25b6 Run time' de thoi gian troi."))

    def _dyninfo(self, blocks):
        """{bid: thong tin badge} tu danh sach khoi dong tra ve boi sheet_dyn."""
        from core import ai_explain as AE
        from core import sheet_dyn as DYN
        info = {}
        for b in blocks:
            if b["kind"] == "S":
                info[b["bid"]] = {"kind": "S", "code": b["code"],
                                  "name": AE._catalog().get(b["code"], {}).get("short", b["code"]),
                                  "outs": dict(b.get("last_out") or {}),
                                  "in_nets": b["in_nets"], "out_nets": b["out_nets"],
                                  "real_params": dict(b["sim"].params)}
            elif b["kind"] == "T":
                # Khoi timer KHONG co khoa "ti" nhu khoi tich phan - doc thang b["ti"] o day
                # se nem KeyError va lam mat sach badge cua moi khoi dong tren sheet do.
                info[b["bid"]] = {"kind": "T", "out": b["out"], "code": b["code"],
                                  "tmr": b.get("tmr"), "T": b.get("Tef", b.get("T")),
                                  "toff": b.get("toff"), "left": DYN.timer_left(b)}
            else:
                info[b["bid"]] = {"ti": b["ti"], "out": b["out"], "code": b["code"],
                                  "kind": b.get("kind", "I")}
                if b.get("kind") == "R":
                    info[b["bid"]]["up"] = b.get("up")
                    info[b["bid"]]["dn"] = b.get("dn")
        return info

    def _dyn_outs(self, blocks):
        """Net do chinh khoi dong sinh ra -> khong con la dau vao ✎ tren sheet."""
        out = set()
        for b in blocks:
            if b["kind"] == "S":
                out.update(v for v in b["out_nets"].values() if v)
            elif b["out"]:
                out.add(b["out"])
        return out

    def run_dynamic_sim(self):
        """Chay mo phong DONG: khoi tich phan/PID tu tien theo thoi gian toi on dinh."""
        if not getattr(self, "sim_sheet_act", None) or not self.sim_sheet_act.isChecked():
            self.status("Bat 'Simulate on sheet' truoc khi chay dong.")
            return
        if getattr(self, "cur_sheet", None) is None:
            return
        from core import sheet_dyn as DYN
        from core import sheet_sim as SS
        db, sh = self.db_path, self.cur_sheet
        dt = getattr(self, "_dyn_dt", 0.5); nsteps = getattr(self, "_dyn_steps", 300)
        # ghi lai chuoi thoi gian cho dau ra cac khoi dong
        try:
            dblocks = DYN._dyn_blocks(db, sh, getattr(self, "sim_dyn_over", {}))
        except Exception:
            dblocks = []
        record = [b["out"] for b in dblocks if b["kind"] != "S"]
        for b in dblocks:
            if b["kind"] == "S":
                record.extend(b["out_nets"].values())
        try:
            # chay TU DAU (dieu kien ban dau) - do la y nghia cua nut "Run dynamic";
            # nhung ghi lai trang thai cuoi de cac lan tinh sau TIEP TUC tu day
            self.station_sims.pop((db, sh), None)
            st = {}
            self.sim_dyn_state[(db, sh)] = st
            val, hist, blocks = DYN.run(db, sh, getattr(self, "sim_env", {}),
                                        getattr(self, "sim_analog", {}), dt=dt, nsteps=nsteps,
                                        record=record, overrides=getattr(self, "sim_dyn_over", {}),
                                        state=st,
                                        sim_cache=self.station_sims.setdefault((db, sh), {}))
        except Exception as e:
            self.status("Dynamic run error: %s" % e)
            return
        kinds = SS._kind_map(db, sh)
        dynouts = self._dyn_outs(blocks)   # dau ra khoi dong da tu tinh -> khong con la dau vao ✎
        inputs = [n for n, _ in SS.input_nets(db, sh) if n not in dynouts]
        dyninfo = self._dyninfo(blocks)
        self.sim_values = val             # luu lai (dung cho trinh ve logic noi)
        self._export_sim_global(db, sh, val)
        osc_nets = {net for (d, sx, net) in getattr(self, "sim_osc", {}) if d == db and sx == sh}
        self.sheet_scene.set_sim(val, kinds, inputs, getattr(self, "sim_analog", {}),
                                 dyn=dyninfo, osc_nets=osc_nets)
        self.status("Ran %d steps (dt=%.2fs, ~%.1fs). %d integral/dynamic blocks."
                    % (nsteps, dt, nsteps * dt, len(blocks)))
        # do thi theo thoi gian cho dau ra khoi dong
        from core import sheet_sim as SS2
        series = []
        for n in record:
            ys = hist.get(n) or []
            if any(isinstance(v, (int, float)) for v in ys):
                lbl = SS2.CT.SG._name_of(db, sh, n) or n
                series.append((lbl, ys))
        if series:
            from ui.plot_dialog import TimePlotDialog
            self._plot = TimePlotDialog(series, dt, title="Dynamic response over time", parent=self)
            self._plot.show()

    def _sim_toggle(self, net):
        """Click 1 dau vao digital: xoay ? -> 1 -> 0 -> ? roi tinh lai."""
        env = getattr(self, "sim_env", {})
        cur = env.get(net)
        if cur is None:
            env[net] = 1
        elif cur == 1:
            env[net] = 0
        else:
            env.pop(net, None)
        self.sim_env = env
        self._apply_sheet_sim()

    def _sim_set_analog(self, net):
        """Click 1 dau vao analog: nhap gia tri so (huy = xoa). Hien nguong lien quan."""
        from core import sheet_sim as SS
        ana = getattr(self, "sim_analog", {})
        cur = ana.get(net, 0.0)
        # nguong cua cac khoi so sanh dung tin hieu nay lam dau vao
        thr_lines = []
        try:
            for onet, innet, rel, t in SS.comparators(self.db_path, self.cur_sheet):
                if innet == net and t is not None:
                    nm = SS.CT.SG._name_of(self.db_path, self.cur_sheet, onet) or onet
                    thr_lines.append("  • %s %g  -> %s" % (rel, t, nm))
        except Exception:
            pass
        hint = ("\nThresholds (same scale):\n" + "\n".join(thr_lines)) if thr_lines else ""
        val, ok = QInputDialog.getDouble(
            self, "Analog value",
            "Enter value for '%s'\n(Cancel to clear the value):%s" % (net, hint),
            float(cur), -1e9, 1e9, 3)
        if ok:
            ana[net] = val
        else:
            ana.pop(net, None)
        self.sim_analog = ana
        # set gia tri TAY -> huy dao dong dang bat cho dung net nay (tranh timer ghi de lai)
        self.sim_osc.pop((self.db_path, self.cur_sheet, net), None)
        self._apply_sheet_sim()

    def find_signal(self):
        """Tim theo TEN TIN HIEU hoac theo CHUC NANG. Cau hoi go bang TIENG ANH.

        Hai nhom ket qua vi hai duong vao khac han nhau: biet ten tin hieu thi tra
        thang, con khi chi biet chuc nang ("ignitor pre-light sequence") thi phai di
        qua ten loop / ten trang / ten khoi F(x). Cau hoi duoc tu_dien mo rong sang
        dang viet tat ma ban ve thuc su dung (IGNITER -> IGNTR, MILL -> PULV...).

        Ba lop, lop sau chi chay khi lop truoc khong du:
          1. tu dien tinh   - offline, tuc thi, do san tren corpus that
          2. sua chinh ta   - doi chieu bang `tu` cua chi muc (presure -> PRESSURE)
          3. AI goi y tu    - chi khi khong thay gi; tu AI van phai co trong DB moi
                              duoc dung, va AI khong bao gio duoc noi CPU/loop/trang
        """
        from PySide6.QtWidgets import QApplication
        paths = list(getattr(self, "meta_by_path", {}).keys())
        if not paths:
            self.status("Import at least one DB first.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Tim tin hieu / chuc nang")
        dlg.resize(860, 560)
        lay = QVBoxLayout(dlg)
        row = QHBoxLayout()
        ed = QLineEdit()
        ed.setPlaceholderText("Go TIENG ANH: ten tin hieu, hoac chuc nang "
                              "(vd: ignitor pre-light sequence) roi Enter...")
        btn = QPushButton("Tim")
        btn_ai = QPushButton("Hoi AI")
        btn_ai.setToolTip("Nho AI doan them tu khoa cho cau nay. Tu nao ban ve khong "
                          "co se bi loai; AI khong duoc chi dinh CPU/loop/trang.")
        btn_rb = QPushButton("Dung lai chi muc")
        btn_rb.setToolTip("Quet lai toan bo DB (~40 giay) - dung khi da doi file DB")
        row.addWidget(ed, 1); row.addWidget(btn); row.addWidget(btn_ai)
        row.addWidget(btn_rb)
        lay.addLayout(row)
        cb_ai = QCheckBox("Tu dong hoi AI khi khong tim thay gi")
        cb_ai.setChecked(True)
        cb_ai.setToolTip("Chi goi khi tu dien tinh da that bai, va ket qua duoc luu "
                         "lai nen hoi lan hai la offline.")
        lay.addWidget(cb_ai)
        info = QLabel(""); info.setStyleSheet("color:#64748B;font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        res = QTreeWidget()
        res.setHeaderLabels(["CPU", "Trang", "Ten", "Thuoc ve"])
        res.setColumnWidth(0, 130); res.setColumnWidth(1, 80); res.setColumnWidth(2, 330)
        lay.addWidget(res, 1)

        from core import project_index as PI
        from core import tu_dien as TD

        def _nhom(nhan):
            g = QTreeWidgetItem([nhan, "", "", ""])
            g.setFirstColumnSpanned(True)
            res.addTopLevelItem(g)
            g.setExpanded(True)
            return g

        def _con(cha, cot, db, sheet):
            it = QTreeWidgetItem(cot)
            if sheet is not None:
                it.setData(0, Qt.ItemDataRole.UserRole, (db, sheet))
            cha.addChild(it)

        def run(force_rebuild=False, them=None, ghi_ai=""):
            q = ed.text().strip()
            res.clear()
            if len(q) < 2:
                info.setText("Go it nhat 2 ky tu.")
                return
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                # lan dau (hoac sau khi doi DB) phai quet lai ~40 giay: ngoai ten tin
                # hieu con phai duyet 4.290 khoi F(x) de lay ten duong cong
                if force_rebuild:
                    PI.build(paths)
                else:
                    PI.ensure(paths)
                # o_sua chu khong o_tra: phai co chi muc roi moi doi chieu chinh ta
                # duoc, nen goi SAU ensure()
                o, sua = TD.o_sua(q, them=them)
                if not o:
                    info.setText("Cau hoi khong con tu khoa nao dung duoc.")
                    return
                ct_m, ct_s = {}, {}
                chuc_nang = PI.find_muc(o, chi_tiet=ct_m)
                tin_hieu = PI.find_bo(o, chi_tiet=ct_s)
                hut = PI.o_hut(o, ct_m, ct_s)
            except Exception as e:
                info.setText("Khong tim duoc: %s" % e)
                return
            finally:
                QApplication.restoreOverrideCursor()

            if chuc_nang:
                g = _nhom("Chuc nang / trang  (%d)" % len(chuc_nang))
                for kind, txt, db, cpuno, cpuname, sheet, slbl, extra in chuc_nang:
                    ghi = {"loop": extra, "fx": "F(x) %s" % extra}.get(kind, extra)
                    _con(g, [cpuname or ("CPU%s" % cpuno), slbl, txt, ghi], db, sheet)
            if tin_hieu:
                g = _nhom("Tin hieu  (%d)" % len(tin_hieu))
                for name, cpuname, cpuno, slbl, db, sheet, sigid in tin_hieu:
                    _con(g, [cpuname or ("CPU%s" % cpuno), slbl, name, sigid or ""],
                         db, sheet)

            # Cho thay minh da tra bang nhung tu nao: nguoi dung hoc dan tu viet tat
            # cua ban ve, va biet ngay vi sao ket qua lech.
            # Danh dau ro o nao ca du an KHONG he co: hoi 'mill A overload' ma khong
            # ban ve nao noi den OVERLOAD thi ket qua chi con la 'mill A' - bao ra de
            # nguoi dung biet do la thuc te cua ban ve, khong phai tra sai.
            da_tra = "  +  ".join(("[khong co] " if i in hut else "")
                                  + " / ".join(x) for i, x in enumerate(o))
            dong = []
            if sua:
                dong.append("Da sua chinh ta theo ban ve: %s"
                            % ", ".join("%s -> %s" % x for x in sua))
            if ghi_ai:
                dong.append(ghi_ai)
            if not chuc_nang and not tin_hieu:
                dong.append("Khong thay gi voi tu khoa: %s" % da_tra)
                if them is None and cb_ai.isChecked():
                    dong.append("Dang hoi AI them tu khoa...")
                    info.setText("\n".join(dong))
                    hoi_ai(q)
                    return
                dong.append("Thu it tu hon, doi sang tu ban ve hay dung "
                            "(PULV, IGNTR, O/L), hoac bam 'Dung lai chi muc'.")
            else:
                dong.append("Tu khoa da tra: %s   -   bam doi de mo trang." % da_tra)
            info.setText("\n".join(dong))

        def hoi_ai(q):
            """Goi AI o luong nen. Khoa nut trong luc cho de khong ban hai lan."""
            if getattr(dlg, "_ai_worker", None) is not None:
                return
            from ui.tim_ai import GoiYWorker
            btn_ai.setEnabled(False)

            def xong(them, ghi):
                dlg._ai_worker = None
                btn_ai.setEnabled(True)
                # them rong van chay lai: de nguoi dung thay ghi chu vi sao that bai,
                # va de them={} chan vong lap hoi AI lan nua
                run(False, them=them or {}, ghi_ai=ghi)

            w = GoiYWorker(q, parent=dlg)
            w.xong.connect(xong)
            dlg._ai_worker = w
            w.start()

        def open_hit(item, _c=0):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                self._open_cross(data[0], data[1])
                dlg.raise_()

        btn.clicked.connect(lambda: run(False))
        btn_rb.clicked.connect(lambda: run(True))
        btn_ai.clicked.connect(lambda: hoi_ai(ed.text().strip()))
        ed.returnPressed.connect(lambda: run(False))
        res.itemDoubleClicked.connect(open_hit)
        ed.setFocus()
        dlg.show()
        self._find_dlg = dlg

    def status(self, msg):
        self.statusBar().showMessage(msg)
