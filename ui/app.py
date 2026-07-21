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
from core.importer import def_to_circuit, read_pdf
from core import dbreader
from ui.canvas import LogicScene
from ui.graphwindow import SignalGraphPanel
from ui.condtree_window import CondTreeWindow
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
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.itemDoubleClicked.connect(self._dbtree_open)
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

    def _recent_file(self):
        return os.path.join(os.path.expanduser("~"), ".tdesigner_lite_recent.json")

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

    def _add_db_to_tree(self, path, meta, sheets):
        # Moi file DB (CPU) la 1 muc top-level -> cac sheet ben trong (khong gom theo Project)
        cpu_item = self.db_nodes.get(path)
        if cpu_item is None:
            cpu_item = QTreeWidgetItem([""])
            cpu_item.setData(0, Qt.ItemDataRole.UserRole, ("db", path))
            self.db_tree.addTopLevelItem(cpu_item)
            self.db_nodes[path] = cpu_item
        else:
            cpu_item.takeChildren()
        self.meta_by_path[path] = meta
        if meta.get("cpuno") is not None:
            self.cpu_paths[meta.get("cpuno")] = path
        cpu_item.setText(0, "CPU%s  %s   (%s, %d sheet)"
                         % (meta.get("cpuno"), meta.get("cpuname") or "",
                            os.path.basename(path), len(sheets)))
        for sh in sheets:
            it = QTreeWidgetItem([self._fmt_sheet(sh)])
            it.setData(0, Qt.ItemDataRole.UserRole, ("sheet", path, sh["id"]))
            cpu_item.addChild(it)
        cpu_item.setExpanded(False)
        self._save_recent()

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
        q = (txt or "").strip().lower()
        for i in range(self.db_tree.topLevelItemCount()):
            cpu = self.db_tree.topLevelItem(i)
            cpu_any = False
            for j in range(cpu.childCount()):
                ch = cpu.child(j)
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
        tb.setStyleSheet("""
            QToolBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #eef5ff, stop:1 #dfeaf7);
                border: 1px solid #b8cce3;
                spacing: 4px;
                padding: 3px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 6px;
                color: #12305a;
            }
            QToolBar QToolButton:hover {
                background-color: #d7e7f7;
            }
        """)
        self.addToolBar(tb)

        def act(text, fn, tip=""):
            a = QAction(text, self)
            a.triggered.connect(fn)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a

        self.palette_act = act("FB Library", self.toggle_palette,
                               "Open the Function Block library window")
        self.db_dock_act = self.db_dock.toggleViewAction()
        self.db_dock_act.setText("DB Files")
        self.db_dock_act.setToolTip("Show/hide the imported DB files panel")
        tb.addAction(self.db_dock_act)
        tb.addSeparator()
        act("Import DB", self.import_db, "Read project .db file and rebuild sheets")
        act("Import folder", self.import_folder, "Import all .db in a folder (grouped by Project/CPU)")
        act("< Back", self.nav_back, "Go back to previous sheet")
        act("Import PDF", self.import_pdf, "Read logic from exported PDF")
        tb.addSeparator()
        act("Zoom +", self.view.zoom_in, "Zoom in (or scroll up)")
        act("Zoom -", self.view.zoom_out, "Zoom out (or scroll down)")
        act("Fit", self.view.zoom_fit, "Fit to screen")
        act("100%", self.view.zoom_reset, "Reset to 1:1")
        tb.addSeparator()
        # Tim tin hieu: phim tat Ctrl+F
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.find_signal)
        self.sim_sheet_act = QAction("Simulate on sheet", self)
        self.sim_sheet_act.setCheckable(True)
        self.sim_sheet_act.setToolTip("Toggle: color 0/1 on the logic sheet; click inputs to change 0/1")
        self.sim_sheet_act.toggled.connect(self.toggle_sheet_sim)
        tb.addAction(self.sim_sheet_act)
        # dt & so buoc & nut Chay nam trong hop cai dat cua tung khoi tich phan
        # (bam vao khoi cam). Gia tri chung luu o day:
        self._dyn_dt = 0.5
        self._dyn_steps = 300

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
            self.sim_env = {}
            self.sim_analog = {}
            self.sim_dyn_over = {}
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

    def navigate_from_term(self, term):
        tgs = term.targets
        if not tgs:
            self._navigate_cross_cpu(term)
            return
        if len(tgs) == 1:
            self._open_sheet(tgs[0][0], push_prev=(self.db_path, self.cur_sheet))
        else:
            items = ["%s  (sheet %s)" % (lbl, sid) for sid, lbl in tgs]
            pick, ok = QInputDialog.getItem(self, "Multiple targets",
                                            "Tin hieu '%s' dan toi:" % (term.lid or term.linename),
                                            items, 0, False)
            if ok and pick:
                idx = items.index(pick)
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
            pick, ok = QInputDialog.getItem(self, "Multiple targets (cross-CPU)",
                                            "Tin hieu '%s' dan toi:" % (term.linename or term.lid),
                                            items, 0, False)
            if ok and pick:
                c = cands[items.index(pick)]
                self._open_cross(c[0], c[1])

    def _open_cross(self, path, sheet_id):
        prev = (self.db_path, self.cur_sheet)
        self.db_path = path
        self._open_sheet(sheet_id, push_prev=prev)

    def nav_back(self):
        if getattr(self, "nav_history", None):
            prev = self.nav_history.pop()
            if isinstance(prev, tuple):
                db, sid = prev
                self.db_path = db
                self._open_sheet(sid)
            else:
                self._open_sheet(prev)


    def import_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import PDF", "", "PDF (*.pdf)")
        if not p:
            return
        try:
            res = read_pdf(p)
        except Exception as e:
            QMessageBox.warning(self, "PDF read error", str(e))
            return
        if res["macros"]:
            self._show_macros(res["macros"], p)
        else:
            self.output.setPlainText("--- TEXT trich tu PDF ---\n\n" + res["text"])
            self.status("PDF has no IL. Showing extracted text.")

    def _show_macros(self, macros, path):
        if not macros:
            self.output.setPlainText("No .DEF blocks found in file.")
            return
        lines = ["# Read from: %s" % os.path.basename(path), "# So macro: %d" % len(macros), ""]
        for m in macros[:200]:
            lines.append(".DEF %s   (%d lenh)" % (m["name"], len(m["stmts"])))
            for op, args in m["stmts"]:
                lines.append("    %-6s %s" % (op, args))
            lines.append(".DEFEND\n")
        self.output.setPlainText("\n".join(lines))
        names = [m["name"] for m in macros]
        pick, ok = QInputDialog.getItem(self, "View diagram",
                                        "Select a macro to rebuild the diagram (block level):", names, 0, False)
        if ok and pick:
            m = next(mm for mm in macros if mm["name"] == pick)
            self.circuit = def_to_circuit(m)
            self._reset_scene()
        self.status("Read %d macros from %s" % (len(macros), os.path.basename(path)))


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
        a_cond = m.addAction("View conditions (for signal = 1)")
        a_view = m.addAction("View function (internal logic)")
        a_sim = m.addAction("Simulate block")
        a_view.setEnabled(code in self.internal_map)
        a_sim.setEnabled(bool(has_behavior(code) or has_analog(code)))
        has_db = (getattr(self, "db_path", None) is not None
                  and getattr(self, "cur_sheet", None) is not None)
        a_graph.setEnabled(has_db)
        a_cond.setEnabled(has_db)
        act = m.exec(global_pos)
        if act == a_graph:
            from core.signal_graph import block_output_net
            net = block_output_net(self.db_path, self.cur_sheet, bid)
            self._open_node_tab(net, name)
        elif act == a_cond:
            from core.signal_graph import block_output_net
            net = block_output_net(self.db_path, self.cur_sheet, bid)
            CondTreeWindow(self.db_path, self.cur_sheet, net, name, self,
                           cpu_paths=getattr(self, "cpu_paths", None)).show()
        elif act == a_view:
            self.show_internal_logic(code, name)
        elif act == a_sim:
            self._last_block_code = code
            self.open_block_sim()

    def signal_context_menu(self, net, linename, global_pos):
        """Chuot phai len 1 TIN HIEU (terminal) -> xem so do node."""
        if getattr(self, "db_path", None) is None or getattr(self, "cur_sheet", None) is None:
            return
        m = QMenu(self)
        a_graph = m.addAction("View signal node diagram")
        a_cond = m.addAction("View conditions (for signal = 1)")
        a_ai = m.addAction("Explain (AI)")
        act = m.exec(global_pos)
        if act == a_graph:
            self._open_node_tab(net, linename or net)
        elif act == a_cond:
            CondTreeWindow(self.db_path, self.cur_sheet, net,
                           linename or net, self,
                           cpu_paths=getattr(self, "cpu_paths", None)).show()
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
            self.sim_env = {}
            self.sim_analog = {}
            self.sim_dyn_over = {}
            sc.on_sim_toggle = self._sim_toggle
            sc.on_sim_set_analog = self._sim_set_analog
            sc.on_sim_dyn_config = self._sim_dyn_config
            self._apply_sheet_sim()
            self.status("Simulation: DIGITAL inputs (▸) click to cycle ? -> 1 -> 0; ANALOG (✎) click to enter a number. Integrator blocks (orange) click to set TI/dt/steps and Run dynamic.")
        else:
            sc.clear_sim()
            self.status("Sheet simulation turned off.")

    def _dyn_info(self, db, sh):
        """{bid: {ti, out, code, label}} cac khoi dong (tich phan) de danh dau tren sheet."""
        from core import sheet_dyn as DYN
        info = {}
        try:
            for b in DYN._dyn_blocks(db, sh, getattr(self, "sim_dyn_over", {})):
                info[b["bid"]] = {"ti": b["ti"], "out": b["out"], "code": b["code"],
                                  "kind": b.get("kind", "I")}
        except Exception:
            pass
        return info

    def _sim_dyn_config(self, bid):
        """Click khoi dong (cam): hop cai dat TI, gia tri dau, dt, so buoc + nut Chay."""
        over = getattr(self, "sim_dyn_over", {})
        cur = dict(self.sheet_scene.sim_dyn.get(bid, {}))
        cur_ti = over.get(bid, {}).get("ti", cur.get("ti") or 1.0)
        cur_init = over.get(bid, {}).get("init", 0.0)

        kind = cur.get("kind")
        titles = {"D": "Derivative settings", "L": "F(t) lag filter settings"}
        plabels = {"D": "G - gain:", "L": "T - time constant (seconds):"}
        dlg = QDialog(self)
        dlg.setWindowTitle(titles.get(kind, "Integrator settings"))
        form = QFormLayout(dlg)
        sp_ti = QDoubleSpinBox(); sp_ti.setRange(-1e6, 1e6); sp_ti.setDecimals(3); sp_ti.setValue(float(cur_ti))
        sp_init = QDoubleSpinBox(); sp_init.setRange(-1e9, 1e9); sp_init.setDecimals(3); sp_init.setValue(float(cur_init))
        sp_dt = QDoubleSpinBox(); sp_dt.setRange(0.01, 60.0); sp_dt.setDecimals(2); sp_dt.setSingleStep(0.1); sp_dt.setValue(float(getattr(self, "_dyn_dt", 0.5)))
        sp_steps = QSpinBox(); sp_steps.setRange(1, 100000); sp_steps.setValue(int(getattr(self, "_dyn_steps", 300)))
        form.addRow(plabels.get(kind, "TI - time constant (seconds):"), sp_ti)
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
            over[bid] = {"ti": sp_ti.value(), "init": sp_init.value()}
            self.sim_dyn_over = over
            self._dyn_dt = sp_dt.value(); self._dyn_steps = sp_steps.value()
            dlg.accept()
            self.run_dynamic_sim()
        b_run.clicked.connect(_apply_run)
        b_close.clicked.connect(dlg.reject)
        dlg.exec()

    def _apply_sheet_sim(self):
        from core import sheet_sim as SS
        db, sh = self.db_path, self.cur_sheet
        inputs = [n for n, _ in SS.input_nets(db, sh)]
        kinds = SS._kind_map(db, sh)
        values, _ = SS.simulate(db, sh, getattr(self, "sim_env", {}),
                                getattr(self, "sim_analog", {}))
        self.sheet_scene.set_sim(values, kinds, inputs, getattr(self, "sim_analog", {}),
                                 dyn=self._dyn_info(db, sh))

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
        record = [b["out"] for b in dblocks]
        try:
            val, hist, blocks = DYN.run(db, sh, getattr(self, "sim_env", {}),
                                        getattr(self, "sim_analog", {}), dt=dt, nsteps=nsteps,
                                        record=record, overrides=getattr(self, "sim_dyn_over", {}))
        except Exception as e:
            self.status("Dynamic run error: %s" % e)
            return
        kinds = SS._kind_map(db, sh)
        # dau ra khoi dong da tu tinh -> khong con la dau vao ✎
        dynouts = set(b["out"] for b in blocks)
        inputs = [n for n, _ in SS.input_nets(db, sh) if n not in dynouts]
        dyninfo = {b["bid"]: {"ti": b["ti"], "out": b["out"], "code": b["code"],
                              "kind": b.get("kind", "I")} for b in blocks}
        self.sheet_scene.set_sim(val, kinds, inputs, getattr(self, "sim_analog", {}), dyn=dyninfo)
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
        self._apply_sheet_sim()

    def find_signal(self):
        """Tim ten tin hieu nam o sheet nao (tra khap cac DB da import)."""
        import sqlite3
        from core import signal_graph as SG
        paths = list(getattr(self, "meta_by_path", {}).keys())
        if not paths:
            self.status("Import at least one DB first.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Find signal")
        dlg.resize(640, 460)
        lay = QVBoxLayout(dlg)
        row = QHBoxLayout()
        ed = QLineEdit(); ed.setPlaceholderText("Type signal name (e.g. O2 MSTR AUTO CTRL CMD) then Enter...")
        btn = QPushButton("Search")
        row.addWidget(ed, 1); row.addWidget(btn)
        lay.addLayout(row)
        info = QLabel(""); info.setStyleSheet("color:#64748B;font-size:11px;")
        lay.addWidget(info)
        res = QTreeWidget(); res.setHeaderLabels(["CPU", "Sheet", "Signal name"])
        res.setColumnWidth(0, 150); res.setColumnWidth(1, 90)
        lay.addWidget(res, 1)

        from core import project_index as PI

        def run():
            q = ed.text().strip()
            res.clear()
            if len(q) < 2:
                info.setText("Enter at least 2 characters.")
                return
            try:
                PI.ensure(paths)     # dung/ cap nhat index neu can (nhanh, cache)
                rows = PI.find(q)    # tra tuc thi tu index
            except Exception:
                rows = []
            for (name, cpuname, cpuno, slbl, db, sheet, sigid) in rows:
                it = QTreeWidgetItem([cpuname or ("CPU%s" % cpuno), slbl, name])
                it.setData(0, Qt.ItemDataRole.UserRole, (db, sheet))
                res.addTopLevelItem(it)
            info.setText("Found %d result(s). Double-click to open the sheet." % len(rows))

        def open_hit(item, _c=0):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                self._open_cross(data[0], data[1])
                dlg.raise_()

        btn.clicked.connect(run)
        ed.returnPressed.connect(run)
        res.itemDoubleClicked.connect(open_hit)
        ed.setFocus()
        dlg.show()
        self._find_dlg = dlg

    def status(self, msg):
        self.statusBar().showMessage(msg)
