# -*- coding: utf-8 -*-
"""NGUYEN NHAN THEO LOP (drill-down) cho 1 tin hieu dich trong Ma tran nhan qua.

Ma tran phang tra ve nguyen nhan GOC - dung de lam tai lieu / xuat Excel, nhung cay
that co the vai tram khoi, doc bang mat khong noi. Cua so nay doc tung buoc:

    Lop 1:  MFT  <- nhung gi TRUC TIEP gay ra no
    Lop 2:  bam 1 nguyen nhan  -> nhung gi gay ra CAI DO
    Lop 3:  ...

Moi lop dung lai o TIN HIEU CO TEN (core/ce_matrix.layer_dnf), tu nhay qua net trung
gian va khoi vo boc - nen 1 lan bam luon ra 1 nguyen nhan doc duoc, khong phai bam
xuyen qua 3-4 khoi vo nghia.

Nhom AND LUON hien (khong giau sau cu bam): voi tai lieu trip circuit, hien "A, B, C
gay ra MFT" trong khi that ra phai du CA BA la hieu sai co tinh an toan.

Chi doc DB, khong sua gi.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QComboBox, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core import ce_matrix as CE
from core import io_point as IOP

COL_TARGET = QColor("#1D4ED8")
COL_AND = QColor("#B45309")
COL_CROSS = QColor("#7C3AED")
COL_CMP = QColor("#B45309")
COL_MUTED = QColor("#94A3B8")

ROLE_NODE = Qt.ItemDataRole.UserRole
ROLE_PRODS = Qt.ItemDataRole.UserRole + 1
ROLE_CHAIN = Qt.ItemDataRole.UserRole + 2
ROLE_LOADED = Qt.ItemDataRole.UserRole + 3

MAX_LOOKAHEAD = 60      # so dong toi da con tinh truoc "co mo duoc nua khong"


class CauseLayersDialog(QDialog):
    def __init__(self, target_disp, cands, cpu_paths, main_window=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint)
        self.setWindowTitle("Nguyen nhan theo lop: %s" % target_disp)
        self.resize(1020, 720)
        self.mw = main_window
        self.disp = target_disp
        self.cands = cands or []
        self.cpu_paths = cpu_paths or {}
        self._cpu_names = {}

        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Nguon:"))
        self.cb_cand = QComboBox()
        for c in self.cands:
            self.cb_cand.addItem("%s / sheet %s  (%s)"
                                 % (c.get("cpuname") or "?", c.get("sheetlbl") or "?",
                                    c.get("net") or ""), c)
        self.cb_cand.currentIndexChanged.connect(lambda _i: self._reload())
        top.addWidget(self.cb_cand, 1)
        b_all = QPushButton("Mo them 1 lop")
        b_all.setToolTip("Mo dong loat tat ca dong dang hien - xem nhanh 1 lop sau nua")
        b_all.clicked.connect(self._expand_one_more)
        top.addWidget(b_all)
        b_col = QPushButton("Thu gon")
        b_col.clicked.connect(self._collapse_all)
        top.addWidget(b_col)
        b_diag = QPushButton("So do logic...")
        b_diag.setToolTip("Mo so do AND/OR day du - xem CAU TRUC chinh xac (chot SR, "
                          "phu dinh, cong dac biet)")
        b_diag.clicked.connect(self._open_diagram)
        top.addWidget(b_diag)
        lay.addLayout(top)

        self.info = QLabel("")
        self.info.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(self.info)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Nguyen nhan", "CPU / sheet", "Sau hon", "KKS"])
        self.tree.setAlternatingRowColors(True)
        self.tree.itemExpanded.connect(self._on_expanded)
        self.tree.itemDoubleClicked.connect(self._on_jump)
        lay.addWidget(self.tree, 1)

        legend = QLabel(
            "Moi dong la 1 nguyen nhan; cac dong CUNG MUC quan he OR (chi can 1 cai la du).   "
            "Khung 'AND' = phai du TAT CA dieu kien ben trong moi gay ra tin hieu cha.   "
            "Cot 'Sau hon': 'N nguyen nhan' = con mo duoc, 'goc' = da toi nguyen nhan goc.   "
            "Tim = tin hieu tu CPU/sheet khac,  cam = so sanh nguong.   "
            "Cot 'KKS': ma diem do hien truong doc tu khoi dau cuoi I/O (di chuot "
            "vao de xem dai do, kieu tin hieu, he thong dau kia).   "
            "Bam DUP 1 dong de nhay toi sheet.   "
            "Cau truc chinh xac cua chot SR va cong dac biet: xem 'So do logic'.")
        legend.setWordWrap(True)
        legend.setStyleSheet("color:#64748B; font-size:11px;")
        lay.addWidget(legend)

        self._auto_pick()
        self._reload()

    # ------------------------------------------------------------------ tien ich
    def _cpu_name(self, node):
        """Ten CPU doc duoc (node chi luu SO cpu)."""
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

    def _src_txt(self, node):
        return ("%s / %s" % (self._cpu_name(node), node.get("sheetlbl") or "")).strip(" /")

    def _drill(self, node):
        try:
            return CE.drill(node, self.cpu_paths)
        except Exception:
            return []

    def _auto_pick(self, max_try=8):
        """Cung 1 ten tin hieu dich thuong duoc san xuat o NHIEU noi (MFT: 19 cho), phan
        lon chi la diem phat lai khong co logic. Nho CE.pick_source() chon nguon that."""
        n = min(max_try, self.cb_cand.count())
        cands = [self.cb_cand.itemData(i) for i in range(n)]
        try:
            best, _ = CE.pick_source(cands, self.cpu_paths, max_try=n)
        except Exception:
            best = None
        best_i = 0
        for i, c in enumerate(cands):
            k = len(CE.first_layer(c, self.cpu_paths))
            if k:
                self.cb_cand.setItemText(i, self.cb_cand.itemText(i) + "  - %d nguyen nhan" % k)
            if c is best:
                best_i = i
        self.cb_cand.blockSignals(True)
        self.cb_cand.setCurrentIndex(best_i)
        self.cb_cand.blockSignals(False)

    # ------------------------------------------------------------------ dung cay
    def _reload(self):
        self.tree.clear()
        cand = self.cb_cand.currentData()
        if not cand:
            self.info.setText("Khong xac dinh duoc noi san xuat tin hieu nay.")
            return
        prods = CE.first_layer(cand, self.cpu_paths)
        root = QTreeWidgetItem(self.tree)
        root.setText(0, self.disp)
        root.setText(1, "%s / %s" % (cand.get("cpuname") or "?", cand.get("sheetlbl") or "?"))
        root.setForeground(0, COL_TARGET)
        f = root.font(0); f.setBold(True); root.setFont(0, f)
        root.setToolTip(0, "Tin hieu DICH - moi thu ben duoi la nguyen nhan gay ra no")
        root.setData(0, ROLE_LOADED, True)
        chain = {(self.disp or "").strip().upper()}
        self._add_products(root, prods, chain)
        root.setExpanded(True)
        n_or = sum(1 for p in prods if len(p) == 1)
        n_and = len(prods) - n_or
        if not prods:
            self.info.setText("Khong tim thay nguyen nhan nao o nguon nay - thu doi 'Nguon' o tren.")
        else:
            self.info.setText(
                "Lop 1 cua '%s': %d nguyen nhan doc lap (OR), %d nhom phai du dieu kien (AND). "
                "Bam mui ten o dong nao de mo lop tiep theo cua rieng dong do."
                % (self.disp, n_or, n_and))

    def _add_products(self, parent, products, chain):
        """1 lop: moi 'san pham' la 1 nhom AND (1 phan tu = nguyen nhan doc lap).
        Cac san pham quan he OR - de ngang hang nhau duoi `parent`.
        `left` = so dong con duoc TINH TRUOC "co mo them duoc khong" (moi lan tinh la
        1 lan doc DB) - lop qua rong thi cac dong sau chi hien '...' cho toi khi bam."""
        left = [MAX_LOOKAHEAD]
        for prod in products:
            if len(prod) == 1:
                self._add_term(parent, prod[0], chain, left)
                continue
            g = QTreeWidgetItem(parent)
            g.setText(0, "AND - can du %d dieu kien" % len(prod))
            g.setForeground(0, COL_AND)
            f = g.font(0); f.setBold(True); g.setFont(0, f)
            g.setToolTip(0, "Chi gay ra tin hieu o dong tren khi CO DU tat ca dieu kien ben duoi")
            g.setData(0, ROLE_LOADED, True)
            for n in prod:
                self._add_term(g, n, chain, left)
            g.setExpanded(True)      # nhom AND luon mo - giau di la hieu sai nguy hiem

    def _add_curve(self, parent, note):
        """Nguong cua nhieu mach bao ve khong phai 1 con so ma la 1 DUONG CONG F(x)
        (vd MFT: nhiet do cho phep chay theo ap suat). Treo luon cum diem gay khuc
        ngay duoi dieu kien do - mo san - de doc tai cho, khoi mo sheet tra bang."""
        dong = [d.strip() for d in (note or "").splitlines()[1:] if d.strip()]
        if not dong:
            return
        g = QTreeWidgetItem(parent)
        g.setText(0, dong[0])
        g.setForeground(0, COL_MUTED)
        g.setToolTip(0, note)
        g.setData(0, ROLE_LOADED, True)
        for d in dong[1:]:
            c = QTreeWidgetItem(g)
            c.setText(0, d)
            c.setForeground(0, COL_MUTED)
            c.setData(0, ROLE_LOADED, True)
        g.setExpanded(True)
        parent.setData(0, ROLE_LOADED, True)    # _on_expanded co takeChildren() - phai chan
        parent.setExpanded(True)

    def _io_dbs(self):
        """DB dung de tra diem I/O hien truong: moi CPU cua du an + db cac ung vien."""
        ds = [d for d in self.cpu_paths.values() if d]
        ds += [c.get("db") for c in self.cands if c.get("db")]
        return list(dict.fromkeys(ds))

    def _add_term(self, parent, node, chain, left):
        it = QTreeWidgetItem(parent)
        it.setText(0, CE.term_label(node))
        it.setText(1, self._src_txt(node))
        it.setData(0, ROLE_NODE, node)
        it.setData(0, ROLE_CHAIN, chain)
        note = CE.cmp_note(node) if (node.get("type") == "cmp"
                                     or node.get("kind") == "cmp") else ""
        # diem VAO/RA hien truong cua chinh nguyen nhan nay: ma KKS + dai do, de doc
        # xong biet luon ra hien truong phai tim o dau, khong phai mo lai ban ve
        pts = IOP.find(node.get("label") or node.get("net"), self._io_dbs(),
                       uu_tien_db=node.get("db"))
        if pts:
            it.setText(3, IOP.ma_kks(pts))
            it.setToolTip(3, IOP.chu_thich(pts))
        it.setToolTip(0, "\n\n".join(x for x in [note or CE.term_label(node),
                                                 IOP.chu_thich(pts)] if x))
        if node.get("kind") == "cross":
            it.setForeground(0, COL_CROSS)
        elif node.get("type") == "cmp" or node.get("kind") == "cmp":
            it.setForeground(0, COL_CMP)

        raw = (node.get("label") or node.get("net") or "").strip().upper()
        if raw and raw in chain:
            # tin hieu quay lai chinh no (mach chot/hoi tiep) - dung lai, neu khong
            # nguoi dung se bam mai khong het
            it.setText(2, "vong lap")
            it.setForeground(2, COL_MUTED)
            it.setToolTip(2, "Ten nay da xuat hien o lop tren (mach hoi tiep) - dung lai o day")
            return it
        left[0] -= 1
        if left[0] < 0:
            it.setText(2, "...")     # lop qua rong - de bam roi tinh, cho nhe
            it.setToolTip(2, "Bam de xem con nguyen nhan nao sau nua khong")
            it.setData(0, ROLE_PRODS, None)
            QTreeWidgetItem(it).setText(0, "...")
            return it
        prods = self._drill(node)
        if prods:
            it.setText(2, "%d nguyen nhan" % len(prods))
            it.setData(0, ROLE_PRODS, prods)
            QTreeWidgetItem(it).setText(0, "...")     # cho hien mui ten mo rong
        else:
            it.setText(2, "goc")
            it.setForeground(2, COL_MUTED)
            it.setToolTip(2, "Da toi nguyen nhan goc: tin hieu tu ben ngoai, so sanh nguong, "
                             "hoac khong bung them duoc")
            self._add_curve(it, note)
        return it

    def _count_items(self):
        n = [0]

        def walk(it):
            n[0] += 1
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return n[0]

    # ------------------------------------------------------------------ mo lop
    def _on_expanded(self, item):
        if item.data(0, ROLE_LOADED):
            return
        item.setData(0, ROLE_LOADED, True)
        node = item.data(0, ROLE_NODE)
        if not node:
            return
        prods = item.data(0, ROLE_PRODS)
        if prods is None:                 # chua tinh truoc (cay lon) - tinh bay gio
            prods = self._drill(node)
        item.takeChildren()
        if not prods:
            item.setText(2, "goc")
            item.setForeground(2, COL_MUTED)
            return
        item.setText(2, "%d nguyen nhan" % len(prods))
        chain = set(item.data(0, ROLE_CHAIN) or set())
        raw = (node.get("label") or node.get("net") or "").strip().upper()
        if raw:
            chain = chain | {raw}
        self._add_products(item, prods, chain)

    def _expand_one_more(self):
        """Mo dong loat moi dong dang hien them 1 lop - xem nhanh do rong cua mach."""
        todo = []

        def walk(it):
            if it.data(0, ROLE_NODE) is not None and not it.data(0, ROLE_LOADED):
                todo.append(it)
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        for it in todo:
            it.setExpanded(True)
        self.info.setText("Da mo them 1 lop cho %d dong. Tong %d dong."
                          % (len(todo), self._count_items()))

    def _collapse_all(self):
        self.tree.collapseAll()
        if self.tree.topLevelItemCount():
            self.tree.topLevelItem(0).setExpanded(True)

    # ------------------------------------------------------------------ dieu huong
    def _on_jump(self, item, _col):
        node = item.data(0, ROLE_NODE)
        if not node or self.mw is None:
            return
        db, sheet = node.get("db"), node.get("sheet")
        if not db or sheet is None:
            self.info.setText("Nguyen nhan nay chua ro sheet nguon (tin hieu ben ngoai).")
            return
        try:
            self.mw._open_cross(db, sheet)
        except Exception:
            return
        self.raise_()

    def _open_diagram(self):
        cand = self.cb_cand.currentData()
        it = self.tree.currentItem()
        hl = it.text(0) if (it and it.data(0, ROLE_NODE) is not None) else None
        from ui.cause_tree_dialog import CauseTreeDialog
        self._diag = CauseTreeDialog(self.disp, [cand] if cand else self.cands,
                                     self.cpu_paths, main_window=self.mw,
                                     highlight=hl, parent=self)
        self._diag.show()
