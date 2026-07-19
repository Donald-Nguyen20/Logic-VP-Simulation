# -*- coding: utf-8 -*-
"""Cua so do thi theo thoi gian cho mo phong dong. Ve bang QPainter (khong can thu vien ngoai).
Chay dan tung diem nhu dang phat de thay dap ung theo thoi gian."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel)
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF

_COLORS = ["#2a78d6", "#008300", "#eda100", "#d55181", "#199e70",
           "#d95926", "#9085e9", "#e34948"]


class _PlotArea(QWidget):
    def __init__(self, series, dt, parent=None):
        super().__init__(parent)
        self.series = series        # [(label, [values...])]
        self.dt = dt
        self.k = 0                  # so diem dang hien (de chay dan)
        self.setMinimumHeight(360)
        # pham vi
        allv = [v for _, ys in series for v in ys if isinstance(v, (int, float))]
        self.ymin = min(allv) if allv else 0.0
        self.ymax = max(allv) if allv else 1.0
        if self.ymax - self.ymin < 1e-9:
            self.ymax += 1.0; self.ymin -= 1.0
        pad = (self.ymax - self.ymin) * 0.08
        self.ymin -= pad; self.ymax += pad
        self.n = max((len(ys) for _, ys in series), default=1)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width(); H = self.height()
        L, R, T, B = 64, 20, 16, 40
        x0, y0, x1, y1 = L, T, W - R, H - B
        gw, gh = max(1, x1 - x0), max(1, y1 - y0)
        # nen + khung
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#C3C2B7"), 1))
        p.drawLine(x0, y0, x0, y1); p.drawLine(x0, y1, x1, y1)
        # luoi + nhan truc Y (5 muc)
        p.setFont(QFont("Segoe UI", 9))
        for i in range(6):
            yy = y0 + gh * i / 5
            val = self.ymax - (self.ymax - self.ymin) * i / 5
            p.setPen(QPen(QColor("#E1E0D9"), 1)); p.drawLine(int(x0), int(yy), int(x1), int(yy))
            p.setPen(QColor("#898781"))
            p.drawText(QRectF(0, yy - 8, L - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "%.3g" % val)
        # nhan truc X (thoi gian)
        Ttot = (self.n - 1) * self.dt if self.n > 1 else self.dt
        for i in range(6):
            xx = x0 + gw * i / 5
            tv = Ttot * i / 5
            p.setPen(QColor("#898781"))
            p.drawText(QRectF(xx - 30, y1 + 4, 60, 16), Qt.AlignmentFlag.AlignHCenter, "%.0fs" % tv)
        p.drawText(QRectF(x0, y1 + 20, gw, 16), Qt.AlignmentFlag.AlignHCenter, "Time (seconds)")

        def X(idx):
            return x0 + gw * (idx / (self.n - 1)) if self.n > 1 else x0
        def Y(v):
            return y1 - gh * ((v - self.ymin) / (self.ymax - self.ymin))
        kk = self.k if self.k > 0 else self.n
        for si, (label, ys) in enumerate(self.series):
            col = QColor(_COLORS[si % len(_COLORS)])
            p.setPen(QPen(col, 2))
            prev = None
            for idx in range(min(kk, len(ys))):
                v = ys[idx]
                if not isinstance(v, (int, float)):
                    prev = None; continue
                pt = QPointF(X(idx), Y(v))
                if prev is not None:
                    p.drawLine(prev, pt)
                prev = pt
            # cham dau cuoi + gia tri
            if prev is not None:
                p.setBrush(col); p.drawEllipse(prev, 3, 3)
                p.drawText(QRectF(prev.x() + 6, prev.y() - 10, 90, 16),
                           Qt.AlignmentFlag.AlignLeft, "%.3g" % ys[min(kk, len(ys)) - 1])


class TimePlotDialog(QDialog):
    def __init__(self, series, dt, title="Dynamic plot", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle(title)
        self.resize(760, 480)
        lay = QVBoxLayout(self)
        # chu thich mau
        leg = QHBoxLayout()
        for i, (label, _ys) in enumerate(series):
            sw = QLabel("  "); sw.setFixedWidth(16)
            sw.setStyleSheet("background:%s;" % _COLORS[i % len(_COLORS)])
            leg.addWidget(sw); leg.addWidget(QLabel(label))
        leg.addStretch(1)
        lay.addLayout(leg)
        self.area = _PlotArea(series, dt)
        lay.addWidget(self.area, 1)
        bar = QHBoxLayout()
        self.btn = QPushButton("▶ Replay"); self.btn.clicked.connect(self._replay)
        bar.addWidget(self.btn); bar.addStretch(1)
        lay.addLayout(bar)
        # chay dan khi mo
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        self.area.k = 0
        self._timer.start(20)

    def _tick(self):
        self.area.k += max(1, self.area.n // 120)
        if self.area.k >= self.area.n:
            self.area.k = self.area.n; self._timer.stop()
        self.area.update()

    def _replay(self):
        self.area.k = 0; self._timer.start(20)


class _XYCurve(QWidget):
    """Ve duong cong F(x) tu danh sach (x,y)."""
    def __init__(self, pts, parent=None):
        super().__init__(parent)
        self.pts = pts
        self.setMinimumSize(300, 240)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        self.xmin, self.xmax = (min(xs), max(xs)) if xs else (0, 1)
        self.ymin, self.ymax = (min(ys), max(ys)) if ys else (0, 1)
        if self.xmax - self.xmin < 1e-9: self.xmax += 1
        if self.ymax - self.ymin < 1e-9: self.ymax += 1

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height(); L, R, T, B = 52, 14, 12, 30
        x0, y0, x1, y1 = L, T, W - R, H - B
        gw, gh = max(1, x1 - x0), max(1, y1 - y0)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#C3C2B7"), 1))
        p.drawLine(x0, y0, x0, y1); p.drawLine(x0, y1, x1, y1)
        p.setFont(QFont("Segoe UI", 9)); p.setPen(QColor("#898781"))
        for i in range(5):
            yy = y0 + gh * i / 4; yv = self.ymax - (self.ymax - self.ymin) * i / 4
            p.drawText(QRectF(0, yy - 8, L - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "%.3g" % yv)
        for i in range(5):
            xx = x0 + gw * i / 4; xv = self.xmin + (self.xmax - self.xmin) * i / 4
            p.drawText(QRectF(xx - 30, y1 + 4, 60, 16), Qt.AlignmentFlag.AlignHCenter, "%.3g" % xv)
        def X(v): return x0 + gw * (v - self.xmin) / (self.xmax - self.xmin)
        def Y(v): return y1 - gh * (v - self.ymin) / (self.ymax - self.ymin)
        p.setPen(QPen(QColor("#185FA5"), 2)); p.setBrush(QColor("#185FA5"))
        prev = None
        for (xv, yv) in self.pts:
            pt = QPointF(X(xv), Y(yv))
            if prev is not None: p.drawLine(prev, pt)
            p.drawEllipse(pt, 3, 3); prev = pt


class FuncViewDialog(QDialog):
    """Xem bang x-y va duong cong cua khoi F(x)."""
    def __init__(self, pts, title="F(x)", parent=None):
        super().__init__(parent)
        self.setWindowTitle("F(x): %s" % title)
        self.resize(560, 380)
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QSplitter
        lay = QVBoxLayout(self)
        hdr = QLabel(title); hdr.setStyleSheet("font-size:15px; font-weight:600;")
        lay.addWidget(hdr)
        split = QSplitter(Qt.Orientation.Horizontal)
        tbl = QTableWidget(len(pts), 2)
        tbl.setHorizontalHeaderLabels(["X (in)", "Y (out)"])
        for i, (xv, yv) in enumerate(pts):
            tbl.setItem(i, 0, QTableWidgetItem("%g" % xv))
            tbl.setItem(i, 1, QTableWidgetItem("%g" % yv))
        tbl.setMaximumWidth(220)
        split.addWidget(tbl)
        split.addWidget(_XYCurve(pts))
        split.setSizes([200, 340])
        lay.addWidget(split, 1)
