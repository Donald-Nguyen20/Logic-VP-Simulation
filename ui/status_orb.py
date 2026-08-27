# -*- coding: utf-8 -*-
"""Den bao KET NOI CLAUDE: 1 nut tron nho.
  - CHUA ket noi  -> tat, mau xam toi, khong nhap nhay.
  - DA ket noi    -> sang nhe, quang sang thoi rat cham (hoi tho), khong choi mat.
Di chuot vao de xem ly do (chua co SDK / chua dang nhap / da ket noi bang gi).
"""
from __future__ import annotations
import math

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QRadialGradient, QColor, QPen, QBrush

ON_CORE = QColor("#22C55E")      # xanh la diu
ON_GLOW = QColor(34, 197, 94)
OFF_CORE = QColor("#94A3B8")     # xam nhat
OFF_RING = QColor("#CBD5E1")


class StatusOrb(QWidget):
    """Nut tron 16px + quang sang. set_state(True/False, tooltip)."""

    GLOW = 1.9        # ban kinh quang sang = GLOW * ban kinh nut

    def __init__(self, size=14, parent=None):
        super().__init__(parent)
        self._sz = size
        # widget phai DU RONG cho ca quang sang, neu khong quang bi cat thanh o vuong
        side = int(size * self.GLOW) + 6
        self.setFixedSize(side, side)
        self._on = False
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_state(self, on, tip=""):
        on = bool(on)
        if tip:
            self.setToolTip(tip)
        if on == self._on:
            self.update()
            return
        self._on = on
        if on:
            self._timer.start(60)      # ~16 fps la du cho nhip tho cham
        else:
            self._timer.stop()
        self.update()

    def _tick(self):
        self._t += 0.06
        if self._t > 2 * math.pi:
            self._t -= 2 * math.pi
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        r = self._sz / 2.0
        if self._on:
            # nhip tho: cuong do quang sang dao dong nhe quanh muc trung binh
            k = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(self._t))
            rg = r * self.GLOW
            gr = QRadialGradient(c, rg)
            g1 = QColor(ON_GLOW); g1.setAlpha(int(130 * k))
            g2 = QColor(ON_GLOW); g2.setAlpha(0)
            gr.setColorAt(0.0, g1)
            gr.setColorAt(0.5, QColor(ON_GLOW.red(), ON_GLOW.green(), ON_GLOW.blue(),
                                      int(55 * k)))
            gr.setColorAt(1.0, g2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(gr))
            p.drawEllipse(c, rg, rg)
            core = QColor(ON_CORE)
            p.setBrush(QBrush(core))
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
            p.drawEllipse(c, r, r)
            # diem loe nho o goc tren trai cho co chieu sau
            hl = QRadialGradient(QPointF(c.x() - r * 0.35, c.y() - r * 0.35), r)
            hl.setColorAt(0.0, QColor(255, 255, 255, int(170 * k)))
            hl.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(hl))
            p.drawEllipse(c, r, r)
        else:
            p.setBrush(QBrush(QColor(OFF_CORE.red(), OFF_CORE.green(), OFF_CORE.blue(), 90)))
            p.setPen(QPen(OFF_RING, 1.2))
            p.drawEllipse(c, r, r)
        p.end()


class ClaudeStatusBar(QWidget):
    """Den + dong chu ngan, tu cap nhat dinh ky. Dung o thanh cong cu / hop thoai AI."""

    def __init__(self, show_text=True, interval_ms=4000, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(6)
        self.orb = StatusOrb()
        lay.addWidget(self.orb)
        self.lbl = QLabel("")
        self.lbl.setStyleSheet("color:#64748B; font-size:11px;")
        self.lbl.setVisible(show_text)
        lay.addWidget(self.lbl)
        self._poll = QTimer(self)
        self._poll.timeout.connect(self.refresh)
        self._poll.start(interval_ms)     # dang nhap xong o cua so ngoai -> tu sang len
        self.refresh()

    def refresh(self):
        try:
            from core import ai_client as AC
            ok, txt = AC.status()
        except Exception as e:
            ok, txt = False, "Khong kiem tra duoc: %s" % e
        self.orb.set_state(ok, txt)
        self.lbl.setText("Claude: da ket noi" if ok else "Claude: chua ket noi")
        self.lbl.setStyleSheet("color:%s; font-size:11px;" % ("#15803D" if ok else "#94A3B8"))
        self.setToolTip(txt)
        return ok
