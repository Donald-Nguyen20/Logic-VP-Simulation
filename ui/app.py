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
    QDoubleSpinBox, QPushButton, QFormLayout, QMenu,
)
from PySide6.QtGui import QPainter, QAction, QPixmap
from PySide6.QtCore import Qt

from core.model import (Circuit, BLOCK_SPECS,
                        PRIMITIVE_ORDER, CATALOG_BY_CAT, CATALOG_COUNT)
from core.importer import def_to_circuit, read_pdf
from core import dbreader
from ui.canvas import LogicScene
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
        self.on_context = None   # callback(code, name, global_pos)

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
        hit = sc.block_at(self.mapToScene(ev.pos())) if hasattr(sc, "block_at") else None
        if hit and self.on_context:
            self.on_context(hit[0], hit[1], ev.globalPos())
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
        lay.addWidget(QLabel("Thu vien: %d khoi. Bam doi de them." % n))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tim khoi (ten / mo ta / ma hex)...")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._dbl)
        lay.addWidget(self.tree)
        self._build("")

    def _groups(self):
        g = [("Co ban (Primitive)", list(PRIMITIVE_ORDER))]
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
        self.setWindowTitle("Chon Sheet tu DB")
        self.resize(560, 520)
        self.sheets = sheets
        self.result_id = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Du an: %s" % (project or "?")))
        lay.addWidget(QLabel("Tong %d sheet co khoi. Go de loc:" % len(sheets)))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Loc theo PA / ten / so sheet / ID...")
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
        return "%s%sSheet#%s  (%d khoi)%s" % (pa, no, s["id"], s["nblocks"], nm)

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
    """Xem 1 hinh (so do logic noi bo) - lan chuot de zoom, keo de di chuyen."""
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
        self.setWindowTitle("Mo phong khoi: %s (%s)" % (name or self.sim.spec.get("name", ""), code))
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Tich = 1 (bat). Dau ra cap nhat ngay. Chot SR giu trang thai "
                             "(vd bat Auto roi tat van giu che do Auto den khi bat Manual)."))
        body = QHBoxLayout(); lay.addLayout(body)

        gin = QGroupBox("Dau vao"); gv = QVBoxLayout(gin)
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

        gout = QGroupBox("Dau ra"); go = QVBoxLayout(gout)
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
        self.setWindowTitle("Mo phong analog: %s (%s)" % (name or self.sim.spec.get("name", ""), code))
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chinh dau vao/tham so, bam 'Buoc' de chay tung chu ky (dt=%.2fs). "
                             "Tich phan/gioi han toc do cong don theo thoi gian." % self.sim.dt))
        bar = QHBoxLayout()
        for txt, fn in [("Buoc", lambda: self._run(1)), ("Chay 20 buoc", lambda: self._run(20)),
                        ("Reset", self._reset)]:
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch(1); lay.addLayout(bar)

        body = QHBoxLayout(); lay.addLayout(body, 1)
        # cot trai: dau vao + tham so
        left = QWidget(); lv = QVBoxLayout(left)
        gin = QGroupBox("Dau vao"); fin = QFormLayout(gin)
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
        gp = QGroupBox("Tham so"); fp = QFormLayout(gp)
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
        gout = QGroupBox("Dau ra"); go = QVBoxLayout(gout)
        self.outlbls = {}
        for o in self.sim.spec.get("outputs", []):
            l = QLabel("%s = 0.0" % o)
            l.setStyleSheet("font-size:16px;font-weight:bold;color:#12305a;padding:4px;")
            self.outlbls[o] = l; go.addWidget(l)
        rv.addWidget(gout)
        rv.addWidget(QLabel("Lich su (moi dong = 1 buoc):"))
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
        self.setWindowTitle("T-Designer Lite - FBD Logic Editor (prototype)")
        self.resize(1280, 800)
        self.circuit = Circuit("SHEET1")
        self.db_path = None
        self.nav_history = []
        self.manual = self._load_manual()
        self.internal_map = self._load_internal()
        self._last_block_code = None
        self._svg_mode = False

        self.scene = LogicScene(self.circuit)
        self.scene.on_status = self.status
        self.view = ZoomView(self.scene)
        self.view.on_context = self.block_context_menu
        self.setCentralWidget(self.view)

        self._build_palette()
        self._build_dbtree()
        self._build_output_dock()
        self._build_toolbar()
        self.statusBar().showMessage("San sang. Bam 'Thu vien FB' tren thanh cong cu de mo thu vien khoi.")

    def _build_palette(self):
        dock = QDockWidget("Thu vien Function Block", self)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.palette = Palette(self.add_block)
        lay.addWidget(self.palette)
        tip = QLabel("Noi day: bam CONG RA (phai) roi CONG VAO (trai).\n"
                     "DI/DO/TON: bam doi tren canvas de sua.  Xoa: chon roi nhan Delete.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#556;font-size:11px;padding:4px;")
        lay.addWidget(tip)
        dock.setWidget(w)
        dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.palette_dock = dock
        dock.setFloating(True)      # hien duoi dang CUA SO rieng
        dock.hide()                 # chi hien khi bam nut "Thu vien FB"

    def toggle_palette(self):
        """Bam nut tren thanh cong cu -> mo/dong cua so thu vien Function Block."""
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
        dock = QDockWidget("File DB da import", self)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(3)
        self.db_search = QLineEdit()
        self.db_search.setPlaceholderText("Loc sheet theo ten / PA / so / ID...")
        self.db_search.textChanged.connect(self._filter_dbtree)
        lay.addWidget(self.db_search)
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderHidden(True)
        self.db_tree.itemDoubleClicked.connect(self._dbtree_open)
        lay.addWidget(self.db_tree)
        hint = QLabel("Bam 'Import DB' de them file.\nBam doi 1 sheet de mo.")
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
        # Gom nhom: Project (PROJNO) -> CPU (moi file DB) -> cac sheet
        projno = meta.get("projno")
        proj_item = self.proj_nodes.get(projno)
        if proj_item is None:
            pname = meta.get("projdesc") or meta.get("projname") or "?"
            proj_item = QTreeWidgetItem(["Project %s - %s" % (projno, pname)])
            proj_item.setData(0, Qt.ItemDataRole.UserRole, ("proj", projno))
            self.db_tree.addTopLevelItem(proj_item)
            self.proj_nodes[projno] = proj_item
        cpu_item = self.db_nodes.get(path)
        if cpu_item is None:
            cpu_item = QTreeWidgetItem([""])
            cpu_item.setData(0, Qt.ItemDataRole.UserRole, ("db", path))
            proj_item.addChild(cpu_item)
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
        proj_item.setExpanded(True)
        cpu_item.setExpanded(False)

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
            proj = self.db_tree.topLevelItem(i)
            proj_any = False
            for k in range(proj.childCount()):
                cpu = proj.child(k)
                cpu_any = False
                for j in range(cpu.childCount()):
                    ch = cpu.child(j)
                    hit = (q in ch.text(0).lower()) if q else True
                    ch.setHidden(not hit)
                    cpu_any = cpu_any or hit
                cpu.setHidden(not cpu_any)
                if q and cpu_any:
                    cpu.setExpanded(True)
                proj_any = proj_any or cpu_any
            proj.setHidden(not proj_any)
            if q and proj_any:
                proj.setExpanded(True)

    def _build_output_dock(self):
        dock = QDockWidget("Ma .DEF / Ket qua doc logic", self)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("font-family:Consolas,monospace;font-size:12px;")
        dock.setWidget(self.output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def _build_toolbar(self):
        tb = QToolBar("Chinh")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, fn, tip=""):
            a = QAction(text, self)
            a.triggered.connect(fn)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a)
            return a

        self.palette_act = act("Thu vien FB", self.toggle_palette,
                               "Mo cua so thu vien Function Block")
        tb.addSeparator()
        act("Import DB", self.import_db, "Doc file .db du an va dung lai sheet")
        act("Import thu muc", self.import_folder, "Import tat ca .db trong 1 thu muc (nhom theo Project/CPU)")
        act("< Back", self.nav_back, "Quay lai sheet truoc (dieu huong)")
        act("Import PDF", self.import_pdf, "Doc logic tu PDF da xuat")
        self.svg_act = QAction("Ky hieu SVG", self)
        self.svg_act.setCheckable(True)
        self.svg_act.setToolTip("Ve khoi bang ky hieu SVG giong PDF (bat/tat)")
        self.svg_act.toggled.connect(self.toggle_svg_symbols)
        tb.addAction(self.svg_act)
        tb.addSeparator()
        act("Zoom +", self.view.zoom_in, "Phong to (hoac lan chuot len)")
        act("Zoom -", self.view.zoom_out, "Thu nho (hoac lan chuot xuong)")
        act("Fit", self.view.zoom_fit, "Vua man hinh")
        act("100%", self.view.zoom_reset, "Ve ti le 1:1")

    def add_block(self, btype):
        k = len(self.circuit.blocks)
        b = self.circuit.add_block(btype, x=140 + 26 * (k % 6), y=90 + 26 * (k % 6))
        if btype in ("DI", "DO"):
            tag, ok = QInputDialog.getText(self, "Tag", "Ten tag cho %s:" % btype)
            if ok and tag:
                b.tag = tag
        elif btype == "TON":
            v, ok = QInputDialog.getInt(self, "Preset", "So scan tre (PT):", 3, 1, 9999)
            if ok:
                b.param["preset"] = v
        self.scene.rebuild()
        self.status("Da them %s." % BLOCK_SPECS.get(btype, {}).get("label", btype))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete:
            for it in list(self.scene.selectedItems()):
                if hasattr(it, "b"):
                    self.circuit.remove_block(it.b.id)
            self.scene.rebuild()
            self.status("Da xoa.")
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
            self, "Chon 1 hoac nhieu file DB du an (Ctrl/Shift de chon nhieu)",
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
                errs.append("%s: khong co sheet co khoi" % os.path.basename(p)); continue
            self.db_path = p
            self._add_db_to_tree(p, meta, sheets)
            n += 1
        if errs:
            QMessageBox.warning(self, "Mot so file khong doc duoc", "\n".join(errs[:15]))
        if n:
            self.status("Da import %d file DB (nhom theo Project/CPU ben trai). Bam doi 1 sheet de mo." % n)

    def import_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Chon thu muc chua cac file .db")
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
        self.status("Da import %d file DB tu thu muc (nhom theo Project/CPU ben trai)." % n)

    def _open_sheet(self, sheet_id, proj="", pas="", push_prev=None):
        from core.sheet_render import build_sheet
        from ui.sheetview import SheetScene
        try:
            sheet = build_sheet(self.db_path, sheet_id)
        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Loi dung sheet", str(e))
            return
        if push_prev is not None:
            self.nav_history.append(push_prev)
        self.cur_sheet = sheet_id
        self.cur_sheet_name = sheet.title
        self.sheet_scene = SheetScene(sheet)
        if self._svg_mode:
            self.sheet_scene.set_svg_mode(True)
        self.sheet_scene.on_navigate = self.navigate_from_term
        self.sheet_scene.on_block_click = self.on_sheet_block
        self.view.setScene(self.sheet_scene)
        self.view.resetTransform()
        self.view._zoom = 1.0
        self.view.zoom_fit(min_scale=0.75)
        self.output.setPlainText(
            "# Sheet %s: %s-%s  %s  [%s]\n# %d khoi, %d terminal, %d day"
            % (sheet_id, sheet.pa, sheet.sheetno, sheet.title, sheet.drawno,
               len(sheet.blocks), len(sheet.terms), len(sheet.wires)))
        self.status("Sheet #%s (%s). Bam vao terminal (chu xanh) de nhay sang sheet lien ket."
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
            pick, ok = QInputDialog.getItem(self, "Nhieu diem den",
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
            self.status("Khong tim thay sheet lien-CPU cho tin hieu '%s'." % (term.linename or term.lid))
            return
        if len(cands) == 1:
            self._open_cross(cands[0][0], cands[0][1])
        else:
            items = ["%s" % c[2] for c in cands]
            pick, ok = QInputDialog.getItem(self, "Nhieu diem den (lien-CPU)",
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
            QMessageBox.warning(self, "Loi doc PDF", str(e))
            return
        if res["macros"]:
            self._show_macros(res["macros"], p)
        else:
            self.output.setPlainText("--- TEXT trich tu PDF ---\n\n" + res["text"])
            self.status("PDF khong chua IL. Da hien text trich duoc.")

    def _show_macros(self, macros, path):
        if not macros:
            self.output.setPlainText("Khong tim thay khoi .DEF trong file.")
            return
        lines = ["# Doc tu: %s" % os.path.basename(path), "# So macro: %d" % len(macros), ""]
        for m in macros[:200]:
            lines.append(".DEF %s   (%d lenh)" % (m["name"], len(m["stmts"])))
            for op, args in m["stmts"]:
                lines.append("    %-6s %s" % (op, args))
            lines.append(".DEFEND\n")
        self.output.setPlainText("\n".join(lines))
        names = [m["name"] for m in macros]
        pick, ok = QInputDialog.getItem(self, "Xem so do",
                                        "Chon macro de dung lai so do (muc khoi):", names, 0, False)
        if ok and pick:
            m = next(mm for mm in macros if mm["name"] == pick)
            self.circuit = def_to_circuit(m)
            self._reset_scene()
        self.status("Da doc %d macro tu %s" % (len(macros), os.path.basename(path)))


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
        self.status("Da chon khoi %s (%s). Chuot phai de: Xem chuc nang / Mo phong khoi."
                    % (name or "", self._last_block_code))

    def show_internal_logic(self, code, name=""):
        code = (code or "").upper()
        info = self.internal_map.get(code)
        if not info:
            self.status("Khoi %s (%s): manual khong co so do logic noi bo (thuong la khoi nguyen thuy)."
                        % (name or "", code))
            return
        path = os.path.join(self.internal_dir, info["img"])
        if not os.path.exists(path):
            self.status("Thieu file hinh: %s" % info["img"])
            return
        title = "Logic ben trong: %s (%s) - manual %s tr.%s" % (
            name or "", code, info.get("manual", ""), info.get("page", ""))
        ImageViewer(path, title, self).exec()


    def open_block_sim(self):
        code = self._last_block_code
        if not code:
            self.status("Bam vao 1 khoi tren sheet truoc, roi bam 'Mo phong khoi'.")
            return
        if has_behavior(code):
            BlockSimDialog(code, "", self).exec()
        elif has_analog(code):
            AnalogSimDialog(code, "", self).exec()
        else:
            self.status("Khoi %s chua co mo hinh de mo phong (hien co: ho MOV/SWGR va MV/SV/PID)." % code)

    def block_context_menu(self, code, name, global_pos):
        code = (code or "").upper()
        m = QMenu(self)
        a_view = m.addAction("Xem chuc nang (logic ben trong)")
        a_sim = m.addAction("Mo phong khoi")
        a_view.setEnabled(code in self.internal_map)
        a_sim.setEnabled(bool(has_behavior(code) or has_analog(code)))
        act = m.exec(global_pos)
        if act == a_view:
            self.show_internal_logic(code, name)
        elif act == a_sim:
            self._last_block_code = code
            self.open_block_sim()

    def toggle_svg_symbols(self, on):
        self._svg_mode = bool(on)
        sc = getattr(self, "sheet_scene", None)
        if sc is not None and hasattr(sc, "set_svg_mode"):
            sc.set_svg_mode(self._svg_mode)
        else:
            self.status("Mo 1 sheet (Import DB) truoc khi bat ky hieu SVG.")


    def status(self, msg):
        self.statusBar().showMessage(msg)
