# -*- coding: utf-8 -*-
"""Phan "How it works (read from the vendor logic)" trong cua so Help cua tram van hanh.

Noi dung lay tu core/tag_docs/<ma>.json (viet tay song ngu, xem core/tag_docs.py):
tom tat -> tung phan kem so dong than lenh DEF -> bieu do kich ban -> luu y -> bang chan,
tham so, tin hieu tram van hanh -> dong nguon.

Bieu do KHONG ve san: moi lan mo cua so, kich ban duoc chay lai bang DefSim (dung bo may
chay ban ve), nen hinh va tai lieu khong the lech nhau.

Chu cua tai lieu chon theo ngon ngu bang TD.pick; chu khung (tieu de, ten cot) qua tr().
"""
from __future__ import annotations
import html

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QSizePolicy, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QFont

from core import tag_docs as TD
from core import macro_def as MD
from core.block_params import param_meta
from core.help_i18n import tr
from ui.block_diagram import COL_NHAT, COL_NEN, _pen

COL_SO = QColor("#1F4E79")        # duong gia tri so
COL_LUOI = QColor("#E2E8F0")
COL_TRUC = QColor("#CBD5E1")
_CELL = "style='padding:2px 12px 2px 0;vertical-align:top'"
_H2 = "<p style='margin:12px 0 2px 0'><b>%s</b></p>"
_BUOC = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, 300.0)
_EPS = 1e-9


def has_doc(code):
    """Ma khoi co tai lieu tram doc tu logic goc (file JSON doc duoc) hay khong."""
    return TD.doc_for(code) is not None


def tag_doc_panel(code, cuon=True):
    """O "How it works" hoan chinh.

    `cuon=False` tra ve o CAO DUNG BANG noi dung, khong co thanh cuon rieng - dung khi
    ben goi da dat ca than cua so vao mot vung cuon chung (ui/block_help_dialog.py)."""
    code = (code or "").upper()
    d = TD.doc_for(code) or {}
    g = QGroupBox(tr("How it works (read from the vendor logic)"))
    inner = QWidget()
    iv = QVBoxLayout(inner)
    iv.setContentsMargins(4, 2, 14, 6)
    iv.addWidget(_nhan("<p style='font-size:10.5pt'>%s</p>" % html.escape(TD.pick(d.get("summary")))))
    iv.addWidget(_nhan(_cac_phan(d)))
    _them_bieu_do(iv, code, d)
    for part in (_luu_y(d), _bang_chan(code, d), _bang_tham_so(code, d), _bang_hmi(d)):
        if part:
            iv.addWidget(_nhan(part))
    iv.addWidget(_nhan("<span style='color:#777;font-size:9pt'>%s</span>" % _nguon(code, d)))
    v = QVBoxLayout(g)
    v.setContentsMargins(6, 6, 6, 6)
    if not cuon:
        v.addWidget(inner)
        return g
    iv.addStretch(1)
    sc = QScrollArea()
    sc.setWidget(inner)
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.Shape.NoFrame)
    v.addWidget(sc)
    return g


def _nhan(html_text):
    lb = QLabel(html_text)
    lb.setTextFormat(Qt.TextFormat.RichText)
    lb.setWordWrap(True)
    lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lb


def _ds(items):
    return "<ul style='margin-top:0;margin-bottom:0'>%s</ul>" % "".join(
        "<li>%s</li>" % html.escape(x) for x in items if x)


def _cac_phan(d):
    """Tung phan: tieu de + (so dong than lenh) + cac y."""
    out = []
    for s in d.get("sections", []):
        ref = ""
        if s.get("def"):
            ref = " <span style='color:#777'>(%s)</span>" % html.escape(tr("DEF body lines %s") % s["def"])
        out.append("<p style='margin:10px 0 2px 0'><b>%s</b>%s</p>%s" % (
            html.escape(TD.pick(s.get("title"))), ref,
            _ds(TD.pick(p) for p in s.get("points", []))))
    return "".join(out)


def _them_bieu_do(lay, code, d):
    """Chay lai tung kich ban co "chart": true va ve ra. Loi chay thi noi ro, khong bo qua."""
    scs = [s for s in d.get("scenarios", []) if s.get("chart")]
    if not scs:
        return
    lay.addWidget(_nhan(_H2 % html.escape(tr("Examples run in the simulator")) + html.escape(
        tr("Each chart is run again from the vendor logic every time this window opens. "
           "On/off rows: red = 1, green = 0. Number rows: a blue line with the value written "
           "where it settles."))))
    for sc in scs:
        lay.addWidget(_nhan("<p style='margin:10px 0 0 0'><b>%s</b><br>%s</p>" % (
            html.escape(TD.pick(sc.get("title"))), html.escape(TD.pick(sc.get("note"))))))
        try:
            res = TD.run_scenario(code, sc)
        except Exception as e:      # than DEF thieu / kich ban hong: bao ngay tren cua so
            lay.addWidget(_nhan("<span style='color:#B45309'>%s</span>" % html.escape(
                tr("This example could not be run: %s") % e)))
            continue
        lay.addWidget(ScenarioChart(sc, res))


def _luu_y(d):
    notes = [TD.pick(n) for n in d.get("notes", [])]
    if not notes:
        return ""
    return (_H2 % "<span style='color:#B45309'>%s</span>" % html.escape(tr("Good to know"))) + _ds(notes)


def _bang(tieu_de, cot, hang):
    """Bang HTML. O trong 'hang' da escape san (co the chua <b>)."""
    if not hang:
        return ""
    head = "".join("<th align='left' %s>%s</th>" % (_CELL, html.escape(c)) for c in cot)
    body = "".join("<tr>%s</tr>" % "".join("<td %s>%s</td>" % (_CELL, x) for x in r)
                   for r in hang)
    return (_H2 % html.escape(tieu_de)) + "<table cellspacing='0'><tr>%s</tr>%s</table>" % (head, body)


def _bang_chan(code, d):
    pins = MD.pins_of(code) or {}
    mo_ta = d.get("pins", {})
    hang = [(no, "<b>%s</b>" % html.escape(ten), tr(side), html.escape(TD.pick(mo_ta.get(str(no)))))
            for side in ("in", "out") for no, ten in pins.get(side, {}).items()]
    hang.sort(key=lambda r: r[0])
    return _bang(tr("Pins"), (tr("Pin"), tr("Name"), tr("Side"), tr("What it does")),
                 [(str(r[0]),) + r[1:] for r in hang])


def _bang_tham_so(code, d):
    meta = param_meta().get(code, {})
    hang = []
    for k, p in sorted(d.get("params", {}).items(), key=lambda kv: int(kv[0])):
        m = meta.get(int(k), {})
        mac = tr("text") if m.get("kind") == "1" else html.escape(str(m.get("default", "")))
        ten = html.escape(p.get("name", ""))
        if p.get("short"):
            ten = "<b>%s</b> %s" % (html.escape(p["short"]), ten)
        hang.append(("P%s" % k, ten, mac, html.escape(TD.pick(p))))
    return _bang(tr("Parameters"), (tr("Param"), tr("Name"), tr("Default"), tr("What it does")), hang)


def _bang_hmi(d):
    hang = [("<b>%s</b>" % html.escape(h.get("name") or ""), html.escape(h.get("tok", "")),
             html.escape(TD.pick(h))) for h in d.get("hmi", [])]
    return _bang(tr("Operator station signals"), (tr("Name"), tr("Signal"), tr("What it does")), hang)


def _nguon(code, d):
    n = len(d.get("scenarios", []))
    return html.escape(
        tr("Source: written by hand from the logic body of %s in the vendor file TAG_MCR.DEF "
           "(line numbers count from the first line of that body), no AI. %d simulated "
           "examples check these statements every time the tests run.")
        % (MD.symbol_of(code) or code, n))


# ---------------------------------------------------------------- bieu do
class ScenarioChart(QWidget):
    """Bieu do nhieu hang cua 1 kich ban. Hang bit do/xanh nhu gian do xung cua sheet; hang
    so la duong bac thang (gia tri giu nguyen tron 1 vong quet) kem so ghi o cho dung yen."""

    TOP, H_BIT, H_SO, H_TRUC = 6.0, 30.0, 66.0, 30.0

    def __init__(self, sc, res, parent=None):
        super().__init__(parent)
        self.dt = float(sc.get("dt", 0.5))
        self.res = res
        self.rows = [(r["sig"], r.get("kind", "num"), TD.pick(r.get("label")) or r["sig"])
                     for r in sc.get("show", [])]
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _cao(self):
        return int(self.TOP + sum(self.H_BIT if k == "bit" else self.H_SO for _s, k, _t in self.rows)
                   + self.H_TRUC)

    def sizeHint(self):
        return QSize(760, self._cao())

    def minimumSizeHint(self):
        return QSize(420, self._cao())

    def paintEvent(self, ev):
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.fillRect(self.rect(), COL_NEN)
        ts = self.res.get("t") or []
        if not ts or not self.rows:
            q.end()
            return
        f = QFont(); f.setPointSize(8); q.setFont(f)
        fm = q.fontMetrics()
        L = min(190.0, max(78.0, max(fm.horizontalAdvance(t) for _s, _k, t in self.rows) + 16.0))
        W = max(60.0, self.width() - L - 18.0)
        tmax = ts[-1] + self.dt

        def px(t):
            return L + W * t / tmax

        y_het = self._cao() - self.H_TRUC
        self._ve_luoi(q, px, tmax, y_het)
        y = self.TOP
        for sig, kind, ten in self.rows:
            a = self.res["v"].get(sig) or [0.0] * len(ts)
            self._nhan_hang(q, ten, y + (self.H_BIT if kind == "bit" else self.H_SO) / 2.0, L)
            if kind == "bit":
                self._ve_bit(q, a, ts, px, y)
                y += self.H_BIT
            else:
                self._ve_so(q, a, ts, px, y)
                y += self.H_SO
        self._ve_truc(q, px, tmax, y_het, L, W)
        q.end()

    def _moc(self, tmax):
        """Cac moc thoi gian tren truc: buoc nho nhat cho khong qua 14 moc."""
        buoc = next((b for b in _BUOC if tmax / b <= 14), _BUOC[-1])
        n = int((tmax - self.dt) / buoc + _EPS)
        return [k * buoc for k in range(n + 1)]

    def _ve_luoi(self, q, px, tmax, y_het):
        q.setPen(QPen(COL_LUOI, 1.0))
        for t in self._moc(tmax):
            q.drawLine(QPointF(px(t), self.TOP), QPointF(px(t), y_het))

    def _nhan_hang(self, q, ten, yc, L):
        q.setPen(QPen(COL_NHAT, 1.0))
        chu = q.fontMetrics().elidedText(ten, Qt.TextElideMode.ElideRight, int(L - 12))
        q.drawText(QRectF(2, yc - 8, L - 10, 16),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), chu)

    def _ve_bit(self, q, a, ts, px, y):
        y0, bien = y + 6.0, 18.0
        b = [1 if x > 0.5 else 0 for x in a]
        for i, v in enumerate(b):
            q.setPen(_pen(v, 2.2))
            yv = y0 if v else y0 + bien
            q.drawLine(QPointF(px(ts[i]), yv), QPointF(px(ts[i] + self.dt), yv))
            if i and b[i - 1] != v:
                q.drawLine(QPointF(px(ts[i]), y0), QPointF(px(ts[i]), y0 + bien))

    def _ve_so(self, q, a, ts, px, y):
        y0, gh = y + 16.0, 40.0
        lo, hi = min(a), max(a)

        def py(v):
            return y0 + gh / 2.0 if hi - lo < _EPS else y0 + gh * (hi - v) / (hi - lo)

        q.setPen(QPen(COL_SO, 2.0))
        for i, v in enumerate(a):
            q.drawLine(QPointF(px(ts[i]), py(v)), QPointF(px(ts[i] + self.dt), py(v)))
            if i and abs(a[i - 1] - v) > _EPS:
                q.drawLine(QPointF(px(ts[i]), py(a[i - 1])), QPointF(px(ts[i]), py(v)))
        self._ghi_so(q, a, ts, px, py)

    def _ghi_so(self, q, a, ts, px, py):
        """Ghi so o mau dau va o dau moi doan dung yen (giu tu 2 vong quet). Doan doc
        (dang doc len/xuong) khong ghi; nhan sat nhau qua thi bo nhan sau cho khoi chong."""
        fm = q.fontMetrics()
        q.setPen(QPen(COL_SO, 1.0))
        x_het, n = -1e9, len(a)
        for i in range(n):
            doi = i == 0 or abs(a[i] - a[i - 1]) > _EPS
            dung = i == 0 or (i + 1 < n and abs(a[i + 1] - a[i]) <= _EPS)
            if not (doi and dung):
                continue
            s = "%g" % round(a[i], 4)
            w = fm.horizontalAdvance(s)
            x = min(px(ts[i]) + 3.0, self.width() - 2.0 - w)
            if x < x_het + 8.0:
                continue
            q.drawText(QPointF(x, py(a[i]) - 4.0), s)
            x_het = x + w

    def _ve_truc(self, q, px, tmax, y, L, W):
        ytruc = y + 6.0
        q.setPen(QPen(COL_TRUC, 1.0))
        q.drawLine(QPointF(L, ytruc), QPointF(L + W, ytruc))
        for t in self._moc(tmax):
            q.setPen(QPen(COL_TRUC, 1.0))
            q.drawLine(QPointF(px(t), ytruc - 3), QPointF(px(t), ytruc + 3))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(px(t) - 26, ytruc + 3, 52, 14),
                       int(Qt.AlignmentFlag.AlignCenter), "%g" % t)
        q.drawText(QRectF(2, ytruc + 3, L - 10, 14),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   tr("time (%s)") % "s")
