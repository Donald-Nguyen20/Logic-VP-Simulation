# -*- coding: utf-8 -*-
"""Ve KY HIEU CHUAN CUA HANG (core/symbol_shapes.json) bang QPainter.

Day dung BO HINH ma trang logic chinh dang dung (ui/sheetview.py) va ban ve logic noi
(ui/internal_design_dialog.py). Nho vay ruot khoi trong cua so Help trong y het luc
chung nam tren trang logic - nguoi doc khong phai hoc mot bo hinh thu hai.

Hinh trong symbol_shapes.json la hinh hoc THUAN (lines/rects/circles/texts) theo don vi
rieng cua ban ve goc, nhan mot he so ty le la ra pixel.

ports_of() suy diem noi day tu chinh hinh hoc do - khong co bang chan nao di kem hinh.
Ba ham hinh hoc nay truoc nam trong ui/internal_design_dialog.py; dua ra day de hai noi
dung CHUNG mot cach suy, khong the lech nhau.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QFont

_TEP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "core", "symbol_shapes.json")
_SYMS = None

COL_SYM = QColor("#3B6FE0")     # dung mau indigo cua ky hieu tren trang logic chinh


def shapes():
    """Toan bo bo ky hieu, doc mot lan roi nho."""
    global _SYMS
    if _SYMS is None:
        try:
            with open(_TEP, encoding="utf-8") as f:
                _SYMS = json.load(f)
        except Exception:
            # Thieu tep hinh chi lam ban ve tro ve hop chu nhat, khong duoc lam chet app.
            _SYMS = {}
    return _SYMS


def sym_bbox(shp):
    """(x, y, rong, cao) om het net cua ky hieu, theo don vi symbol."""
    xs, ys = [], []
    for x1, y1, x2, y2 in shp.get("lines", []):
        xs += [x1, x2]
        ys += [y1, y2]
    for rx, ry, rw, rh, *_ in shp.get("rects", []):
        xs += [rx, rx + rw]
        ys += [ry, ry + rh]
    for cx, cy, cr, *_ in shp.get("circles", []):
        xs += [cx - cr, cx + cr]
        ys += [cy - cr, cy + cr]
    if not xs:
        return 0.0, 0.0, shp.get("w", 10.0) or 10.0, shp.get("h", 10.0) or 10.0
    return min(xs), min(ys), (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0


def ports_of(shp):
    """Suy ra diem noi (port) tu hinh hoc ky hieu. 1 port la dau day thua (dangling)
    cua 1 stub: dau kia cua stub phai BAM vao than khoi (tren vien/trong than) - nho vay
    khong nham voi duong vien khoi. Chan o canh PHAI = output; trai/tren/duoi = input
    (VD ham chia A/B co B o canh tren). Tra ve list (x, y, side) theo don vi symbol;
    neu khong thay -> mac dinh 1 in trai + 1 out phai."""
    rects = shp.get("rects", [])
    # loai net TRUNG (mot so ky hieu ve lap doan giong het nhau) -> tranh dem sai bac
    # dinh khien mep than khoi bi keo lech va bo sot chan vao/ra
    seen = set()
    lines = []
    for x1, y1, x2, y2 in shp.get("lines", []):
        key = tuple(sorted([(round(x1, 1), round(y1, 1)), (round(x2, 1), round(y2, 1))]))
        if key in seen:
            continue
        seen.add(key)
        lines.append((x1, y1, x2, y2))
    cnt = defaultdict(int)
    for x1, y1, x2, y2 in lines:
        cnt[(round(x1, 1), round(y1, 1))] += 1
        cnt[(round(x2, 1), round(y2, 1))] += 1
    conn = [(x, y) for (x, y), c in cnt.items() if c >= 2]
    for rx, ry, rw, rh, *_ in rects:
        conn += [(rx, ry), (rx + rw, ry + rh), (rx, ry + rh), (rx + rw, ry)]
    if not conn:
        conn = list(cnt.keys())
    if not conn:      # ky hieu rong -> port mac dinh 1 in trai + 1 out phai
        bx, by, bw, bh = sym_bbox(shp)
        return [(bx, by + bh / 2, "in"), (bx + bw, by + bh / 2, "out")]
    xs = [p[0] for p in conn]
    ys = [p[1] for p in conn]
    bl, br, bt, bb = min(xs), max(xs), min(ys), max(ys)

    def on_rect(x, y):
        for rx, ry, rw, rh, *_ in rects:
            if rx - 0.7 <= x <= rx + rw + 0.7 and ry - 0.7 <= y <= ry + rh + 0.7:
                if (abs(x - rx) < 0.7 or abs(x - (rx + rw)) < 0.7
                        or abs(y - ry) < 0.7 or abs(y - (ry + rh)) < 0.7):
                    return True
        return False

    def anchored(x, y):     # diem bam vao than khoi (tren vien hoac trong than)
        return on_rect(x, y) or (bl - 0.5 <= x <= br + 0.5 and bt - 0.5 <= y <= bb + 0.5)

    def outside(x, y):      # tho HAN ra ngoai than (khong phai net trang tri ben trong)
        return x < bl - 0.3 or x > br + 0.3 or y < bt - 0.3 or y > bb + 0.3

    # tim dau day thua cua stub (dau kia bam vao than, dau nay tho ra ngoai) -> 1 diem noi
    tips = []
    for x1, y1, x2, y2 in lines:
        for (ex, ey), (ox, oy) in (((x1, y1), (x2, y2)), ((x2, y2), (x1, y1))):
            k = (round(ex, 1), round(ey, 1))
            if cnt[k] == 1 and not on_rect(ex, ey) and outside(ex, ey) and anchored(ox, oy):
                tips.append((ex, ey))

    clusters = []
    for x, y in tips:
        for c in clusters:
            if abs(c[0] / c[2] - x) <= 2.5 and abs(c[1] / c[2] - y) <= 2.5:
                c[0] += x
                c[1] += y
                c[2] += 1
                break
        else:
            clusters.append([x, y, 1])

    ports = []
    for sx, sy, n in clusters:
        x, y = sx / n, sy / n
        right = x >= br - 0.5 and bt - 0.5 <= y <= bb + 0.5
        ports.append((round(x, 1), round(y, 1), "out" if right else "in"))
    ports.sort(key=lambda p: (p[2] != "in", p[1], p[0]))
    if not ports:
        bx, by, bw, bh = sym_bbox(shp)
        ports = [(bx, by + bh / 2, "in"), (bx + bw, by + bh / 2, "out")]
    return ports


def port_roles(shp, unit_ports):
    """Nhan vai tro tung chan theo NHAN CHU gan nhat trong ky hieu (+, -, A, B, S, R...).
    Dung de biet chan nao la so bi tru / mau so... khi doc hinh."""
    texts = [t for t in shp.get("texts", [])
             if str(t[3]).strip() and len(str(t[3]).strip()) <= 3]
    roles = []
    for (px, py, _side) in unit_ports:
        best, bd = "", None
        for t in texts:
            d = (t[0] - px) ** 2 + (t[1] - py) ** 2
            if bd is None or d < bd:
                bd, best = d, str(t[3]).strip()
        roles.append(best.upper() if (bd is not None and bd <= 40) else "")
    return roles


def _trong_than(x, y, o):
    """Diem (x, y) co nam trong o THAN khoi khong (o = bx, by, rong than, cao than)."""
    bx, by, bw, bh = o
    return bx - 0.01 <= x <= bx + bw + 0.01 and by - 0.01 <= y <= by + bh + 0.01


def paint(q, shp, x, y, sc, col=None, nen=None, ngoai=True):
    """Ve ky hieu vao QPainter q, goc bbox dat tai (x, y), ty le sc px/don-vi.

    Theo dung thu tu cua trang logic chinh: nen trang che day truoc, roi net, roi chu -
    de day di phia sau khong xuyen qua than khoi.

    ngoai=False thi bo cac chu ma hinh ky hieu ghi NGOAI o than. Tren trang logic chinh
    do la cho de ghi tham so ("S=", "T(s) =", "HL=") va ten chan ("A", "B", "+", "-",
    "A/B") - phan mem goc dien tri so vao ngay sau. Ban ve Help lai tu ghi lay: tham so
    thanh mot o rieng ben trai co day noi vao, ten chan thanh nhan xam ngay canh chan,
    cong thuc thanh dong chu duoi khoi. Nen o day chung vua thua vua dam nhau - do "A/B"
    cua ham chia nam PHIA TREN than nen roi trung vao dong "<Rf013>" cua khoi ben tren."""
    col = col or COL_SYM
    bx, by, bw, bh = sym_bbox(shp)

    def X(v):
        return x + (v - bx) * sc

    def Y(v):
        return y + (v - by) * sc

    o_than = (bx, by, min(shp.get("w") or bw, bw), min(shp.get("h") or bh, bh))
    if nen is not None:
        # Che day CHI o THAN khoi, khong che ca khung hinh: nhieu ky hieu keo doan day
        # ra dai gap doi than (ASW_T than 13 don vi, ca hinh 28; TON_T 11 tren 26). Che
        # ca khung thi ben phai moi khoi co mot vung trang rong quet sach cac day di
        # ngang phia sau, ban ve dut doan ma khong ro vi sao. O "w x h" khai bao trong
        # symbol_shapes.json chinh la o than, nen lay lam vung che.
        cw = min(shp.get("w") or bw, bw)
        ch = min(shp.get("h") or bh, bh)
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(nen))
        q.drawRect(QRectF(x, y, cw * sc, ch * sc))
    pen = QPen(col, 1.4)
    to = QBrush(col)
    rong = QBrush(Qt.BrushStyle.NoBrush)
    q.setPen(pen)
    q.setBrush(rong)
    for x1, y1, x2, y2 in shp.get("lines", []):
        q.drawLine(QPointF(X(x1), Y(y1)), QPointF(X(x2), Y(y2)))
    for rx, ry, rw, rh, *fl in shp.get("rects", []):
        q.setBrush(to if (fl and fl[0]) else rong)
        q.drawRect(QRectF(X(rx), Y(ry), rw * sc, rh * sc))
    for cx, cy, cr, *fl in shp.get("circles", []):
        q.setBrush(to if (fl and fl[0]) else rong)
        q.drawEllipse(QPointF(X(cx), Y(cy)), cr * sc, cr * sc)
    q.setBrush(rong)
    f0 = q.font()
    for tx in shp.get("texts", []):
        cx, cy, size, txt = tx[0], tx[1], tx[2], str(tx[3])
        if not ngoai and not _trong_than(cx, cy, o_than):
            continue
        mau = tx[4] if len(tx) > 4 else "#000000"
        ps = max(6, int(round(size * sc)))
        f = QFont(f0)
        f.setPixelSize(ps)
        q.setFont(f)
        den = (not mau) or str(mau).lower() in ("#000000", "#000", "black")
        q.setPen(QPen(col if den else QColor(mau), 1.0))
        # Chu trong ky hieu goc neo o DAY chu, khong phai dinh o -> lui len mot dong.
        q.drawText(QRectF(X(cx) - 2, Y(cy) - ps, 400, ps + 3),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), txt)
    q.setFont(f0)
    q.setPen(pen)
