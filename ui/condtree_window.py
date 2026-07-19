# -*- coding: utf-8 -*-
"""
Cua so CAY DIEU KIEN: chon 1 tin hieu -> "de X=1 can gi", nhap trang thai 0/1
cho cac la -> app danh gia va chi ra "con thieu gi".
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTreeWidget, QTreeWidgetItem, QListWidget, QSplitter, QWidget, QSpinBox, QTabWidget,
)
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtCore import Qt

from core import cond_tree as CT
from core import signal_graph as SG

GREEN = "#15803D"
RED = "#B91C1C"
GRAY = "#64748B"
AMBER = "#B45309"

OP_TXT = {"AND": "AND", "OR": "OR", "NOT": "NOT",
          "XOR": "XOR", "SR": "SR LATCH"}


class CondTreeWindow(QDialog):
    def __init__(self, db_path, sheet_id, net, title="", parent=None, cpu_paths=None):
        super().__init__(parent)
        self.db_path = db_path
        self.sheet_id = sheet_id
        self.net = net
        self.title = title
        self.cpu_paths = cpu_paths or {}
        self.env = {}
        self.root = None
        self.id2node = {}
        self.id2item = {}
        self.setWindowFlags(Qt.WindowType.Window
                            | Qt.WindowType.WindowMinimizeButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint
                            | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Conditions for signal = 1: %s" % (title or net))
        self.resize(1080, 760)
        lay = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Depth:"))
        self.sp = QSpinBox(); self.sp.setRange(1, 60); self.sp.setValue(40)
        bar.addWidget(self.sp)
        b1 = QPushButton("Rebuild"); b1.clicked.connect(self._reload)
        bar.addWidget(b1)
        b2 = QPushButton("Evaluate"); b2.clicked.connect(self._evaluate)
        bar.addWidget(b2)
        b3 = QPushButton("Set all = ?"); b3.clicked.connect(self._clear_states)
        bar.addWidget(b3)
        b4 = QPushButton("Expand all cross-sheet"); b4.clicked.connect(self._expand_all)
        bar.addWidget(b4)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.status = QLabel(""); self.status.setStyleSheet("font-size:15px; font-weight:bold;")
        lay.addWidget(self.status)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Condition", "State", "Result", "Note"])
        self.tree.setColumnWidth(0, 460)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 80)
        self.tree.itemDoubleClicked.connect(self._on_dbl)
        split.addWidget(self.tree)

        right = QTabWidget()
        # tab 1: con thieu
        w1 = QWidget(); l1 = QVBoxLayout(w1)
        l1.addWidget(QLabel("MISSING to reach 1:"))
        self.missing = QListWidget()
        l1.addWidget(self.missing)
        hint = QLabel("• Set 0/1 in the State column for leaves.\n"
                      "• Red = not satisfied, green = satisfied, gray = unknown.\n"
                      "• Double-click a leaf marked ＋ to expand further (cross-sheet/analog block).")
        hint.setStyleSheet("color:#64748B; font-size:11px;")
        l1.addWidget(hint)
        right.addTab(w1, "Missing")
        # tab 2: vao/ra theo sheet
        w2 = QWidget(); l2 = QVBoxLayout(w2)
        l2.addWidget(QLabel("INPUT / OUTPUT of each sheet in the tree:"))
        self.sheetio = QTreeWidget(); self.sheetio.setHeaderLabels(["Sheet", "Signal"])
        self.sheetio.setColumnWidth(0, 150)
        l2.addWidget(self.sheetio)
        right.addTab(w2, "In/Out by sheet")
        split.addWidget(right)
        split.setSizes([760, 320])
        lay.addWidget(split, 1)

        self._reload()

    # ---------- dung cay ----------
    def _reload(self):
        try:
            self.root = CT.build(self.db_path, self.sheet_id, self.net,
                                 depth=self.sp.value(), cpu_paths=self.cpu_paths)
        except Exception as e:
            self.status.setText("Error: %s" % e); return
        self.env = {}
        self._render()

    def _clear_states(self):
        self.env = {}
        self._render()

    def _render(self):
        self.tree.clear()
        self.id2node = {}
        self.id2item = {}
        root_item = QTreeWidgetItem(self.tree)
        self._fill(root_item, self.root)
        self.tree.expandAll()
        self._evaluate()

    def _node_caption(self, n):
        t = n["type"]
        neg = "NOT " if n.get("neg") else ""
        via = ("  «qua %s»" % ", ".join(n["via"])) if n.get("via") else ""
        if t == "gate":
            head = OP_TXT.get(n["op"], n["op"])
            if n.get("op") == "SR":
                head += " (priority %s)" % ("SET" if n.get("priority") == "set" else "RESET")
            lb = n.get("label", "")
            return "%s%s   → %s%s" % (neg, head, lb, via)
        mark = " ＋" if n.get("expandable") and not n.get("expanded") else ""
        if t == "const":
            return "%s%s" % (neg, n["label"])
        if t == "cmp":
            rel = {">=": "≥ threshold", "<=": "≤ threshold"}.get(n.get("rel"), "compare")
            return "%s[%s %s]%s%s" % (neg, n.get("block", "CMP"), rel, "  " + n["label"], mark)
        if t == "opaque":
            return "%s[? %s] %s%s%s" % (neg, n.get("block", ""), n["label"], via, mark)
        return "%s%s%s%s" % (neg, n["label"], via, mark)

    def _fill(self, item, n):
        self.id2node[n["id"]] = n
        self.id2item[n["id"]] = item
        item.setText(0, self._node_caption(n))
        item.setData(0, Qt.ItemDataRole.UserRole, n["id"])
        note = []
        if n["type"] == "leaf":
            note.append({"source": "source signal", "cross": "cross-sheet signal",
                         "opaque": n.get("note", "not expanded")}.get(n.get("kind"), n.get("kind", "")))
        elif n["type"] == "cmp":
            note.append("compare condition (analog)")
        elif n["type"] == "opaque":
            note.append("unmodeled block")
        elif n["type"] == "const":
            note.append("constant")
        if n.get("sheetlbl"):
            sysn = SG.sys_name(n["db"], n["sheet"]) if n.get("db") else ("CPU%s" % n.get("cpu"))
            note.append("%s · %s" % (sysn, n.get("sheetlbl")))
        item.setText(3, "  ".join(x for x in note if x))
        # o trang thai cho la co the nhap
        if n["type"] in ("leaf", "cmp", "opaque"):
            cb = QComboBox()
            cb.addItem("—", None); cb.addItem("0", 0); cb.addItem("1", 1)
            cur = self.env.get(n["id"])
            cb.setCurrentIndex({None: 0, 0: 1, 1: 2}[cur] if cur in (None, 0, 1) else 0)
            cb.currentIndexChanged.connect(lambda _i, nid=n["id"], c=cb: self._set_state(nid, c))
            self.tree.setItemWidget(item, 1, cb)
        for ch in n.get("children", []):
            self._fill(QTreeWidgetItem(item), ch)

    def _set_state(self, nid, cb):
        self.env[nid] = cb.currentData()
        self._evaluate()

    # ---------- danh gia ----------
    def _evaluate(self):
        if not self.root:
            return
        val = CT.evaluate(self.root, self.env)
        self._color(self.root)
        # trang thai tong
        name = self.title or self.net
        if val == 1:
            self.status.setText("✅  %s = 1  →  SATISFIED" % name)
            self.status.setStyleSheet("font-size:15px; font-weight:bold; color:%s;" % GREEN)
        elif val == 0:
            self.status.setText("❌  %s = 1  →  NOT SATISFIED" % name)
            self.status.setStyleSheet("font-size:15px; font-weight:bold; color:%s;" % RED)
        else:
            self.status.setText("⚠️  %s = 1  →  INSUFFICIENT DATA (leaves not set)" % name)
            self.status.setStyleSheet("font-size:15px; font-weight:bold; color:%s;" % AMBER)
        # con thieu
        self.missing.clear()
        seen = set()
        for node, want in CT.blockers(self.root, self.env, 1):
            if node["id"] in seen:
                continue
            seen.add(node["id"])
            cur = self.env.get(node["id"])
            curs = "?" if cur is None else str(cur)
            self.missing.addItem("• %s  (need = %d, now = %s)" % (node.get("label", node.get("net", "")), want, curs))
        if self.missing.count() == 0 and val == 1:
            self.missing.addItem("(conditions already met)")
        self._fill_sheetio()

    def _fill_sheetio(self):
        self.sheetio.clear()
        try:
            groups = CT.sheet_io(self.root)
        except Exception:
            groups = []
        for grp in groups:
            top = QTreeWidgetItem(self.sheetio)
            sysn = SG.sys_name(grp["db"], grp["sheet"]) if grp.get("db") else ("CPU%s" % grp.get("cpu"))
            top.setText(0, "%s · %s" % (sysn, grp.get("sheetlbl")))
            f = QFont(); f.setBold(True); top.setFont(0, f)
            if grp["out"]:
                ro = QTreeWidgetItem(top); ro.setText(0, "OUT →")
                ro.setText(1, ", ".join(grp["out"]))
                ro.setForeground(1, QBrush(QColor(GREEN)))
            if grp["in"]:
                ri = QTreeWidgetItem(top); ri.setText(0, "IN ←")
                ri.setText(1, ", ".join(grp["in"]))
                ri.setForeground(1, QBrush(QColor(GRAY)))
        self.sheetio.expandAll()

    def _color(self, n):
        it = self.id2item.get(n["id"])
        if not it:
            return
        v = CT.evaluate(n, self.env)
        col = GREEN if v == 1 else (RED if v == 0 else GRAY)
        it.setForeground(0, QBrush(QColor(col)))
        it.setText(2, "1" if v == 1 else ("0" if v == 0 else "?"))
        it.setForeground(2, QBrush(QColor(col)))
        f = QFont(); f.setBold(v != 1)
        it.setFont(2, f)
        for ch in n.get("children", []):
            self._color(ch)

    # ---------- bung ----------
    def _find_parent(self, node, target_id):
        for i, ch in enumerate(node.get("children", [])):
            if ch["id"] == target_id:
                return node, i
            r = self._find_parent(ch, target_id)
            if r:
                return r
        return None

    def _expand_node(self, nid):
        node = self.id2node.get(nid)
        if not node or not node.get("expandable") or node.get("expanded"):
            return False
        sub = CT.expand(node, self.cpu_paths, id_base=CT.max_id(self.root), depth=self.sp.value())
        if not sub:
            node["expanded"] = True  # danh dau da thu, khong bung duoc
            return False
        if node["id"] == self.root["id"]:
            self.root = sub
        else:
            pr = self._find_parent(self.root, nid)
            if not pr:
                return False
            parent, idx = pr
            parent["children"][idx] = sub
        return True

    def _on_dbl(self, item, _col):
        nid = item.data(0, Qt.ItemDataRole.UserRole)
        if nid is not None and self._expand_node(nid):
            self._render()

    def _expand_all(self):
        # bung lap cho toi khi khong con la bung duoc (gioi han vong)
        for _ in range(6):
            ids = [nid for nid, n in self.id2node.items()
                   if n.get("expandable") and not n.get("expanded")]
            if not ids:
                break
            changed = False
            for nid in ids:
                if self._expand_node(nid):
                    changed = True
            self._render()
            if not changed:
                break
