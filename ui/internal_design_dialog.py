# -*- coding: utf-8 -*-
"""BAN VE MO PHONG: khung tu rap so do roi cho chay thu.

Vao thang tu thanh cong cu > "Internal logic" - bam la ra ban ve luon, khong qua bang
danh muc trung gian nao. Ben trai co ba the (xem ui/internal_panels.py):
  Ky hieu       - 931 hinh khoi trong thu vien, nhay doi de them
  F(x)          - 4.290 khoi ham THAT cua du an; tha vao la kem dung bang gay khuc
                  cua rieng khoi do (4.290 khoi deu chung ma 4035 nen ten ma khong
                  du de biet dang dung duong cong nao)
  Khoi chuc nang- 299 ma khoi cua cac DB; chon mot ma la chuyen sang ban ve cua ma do

Hai che do, khac nhau o cho co gan voi mot ma khoi hay khong:
  TU DO (code rong) - ban thu cua rieng nguoi dung. Khong co chan mac dinh nen phai
    bam "+ Node vao / + Node ra" de tu tao dau vao/ra. Ghi vao data/design/ canh app.
  THEO MA KHOI      - mo hinh noi bo cua ma do, dung chung cho MOI thuc the cua ma
    trong ca du an. Node vao/ra dat san theo chan that (core/macro_pins.json). Ghi vao
    core/internal_design/<code>.json vi no di kem ma nguon.

Ca hai che do deu khong gan voi mot khoi cu the tren trang nao, nen khong co gia tri
that de lay: nhay doi node VAO de tu go gia tri thu, roi bam "Tinh logic noi".

Moi khoi co san cac DIEM NOI (port, cham tron): input ben trai, output ben phai. Noi
day bang cach keo tu 1 cham tron tha vao 1 cham tron khac.

Ban ve luu dang:
    {"pins":[{"id","name","side","x","y"}],
     "blocks":[{"id","sym","x","y", "fx":{"ten","pts"} neu la F(x)}],
     "wires":[[[idA,portA],[idB,portB]], ...]}
"""
from __future__ import annotations
import os
import json
from collections import defaultdict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QGraphicsScene, QGraphicsView, QGraphicsItemGroup,
    QGraphicsItem, QMessageBox, QCheckBox, QInputDialog, QSpinBox, QDoubleSpinBox,
    QFileDialog, QTabWidget,
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap, QIcon
from PySide6.QtCore import Qt, QRectF, QPointF, QSize

SC = 6.0                       # ty le ve ky hieu (don vi symbol_shapes -> px)
_COL_SYM = QColor("#3346B5")
_COL_WIRE = QColor("#6B7280")
_COL_PORT = QColor("#0A8A9C")
_COL_PORT_IN = QColor("#0EA5A5")
_COL_PORT_OUT = QColor("#E8963B")
_COL_PIN_IN = QColor("#EAF6FF")
_COL_PIN_OUT = QColor("#FEF3C7")
_PORT_R = 4.0

_SYMS = None
_THUMBS = {}
_MACRO_PINS = None
_USED_SYMS = {}                # folder -> [sym,...] cac ky hieu THUC SU dung trong DB du an
# khoi TICH PHAN (dong): out += X/TI*dt moi buoc (giong core/sheet_dyn.py)
_INTEG_CODES = {"406C", "406D", "406E", "406F", "507D", "507E", "507F"}

# op (trong netlist van ban) -> ky hieu symbol_shapes dai dien (cho bo NHAP netlist)
_NET_OP_SYM = {
    "SRLATCH": "FFS_TS", "SR": "FFS_TS", "CLAMP": "LMI_TS", "INTEG": "F_INL1_I",
    "SELECT": "ASW_T", "OR": "OR2_I", "AND": "AND2_I", "NOT": "NOT_I",
    "SUB": "F_DIF2_I", "ADD": "F_SUM2_I", "SUM": "F_SUM2_I", "MUL": "F_MUL2_I",
    "DIV": "F_DIV3_I", "ABS": "F_ABS1_I", "GAIN": "F_GAN1_I", "TON": "DI2_I",
    "DELAY": "DLY1_I", "MAX": "509A", "MIN": "509G",
}
# ung cu vien nhan chan cho tung vai tro (khop port khi nap netlist)
_ROLE_CAND = {
    "s": ["S"], "r": ["R"], "a": ["1", "A", "+"], "b": ["2", "B", "-"],
    "sel": ["ASW", "DSW", "N", "SW"], "in": ["X", "IN"],
    "hi": ["H", "HL", "HI"], "lo": ["L", "LL", "LO", "T"],
}


def _op_symbol(op):
    """Ten OP hoac ma symbol -> ma symbol_shapes de ve."""
    o = (op or "").upper()
    sym = _NET_OP_SYM.get(o)
    if sym and _symbol_shapes().get(sym):
        return sym
    if _symbol_shapes().get(op):
        return op                # nguoi dung ghi thang ma symbol
    return op                    # fallback: hien o chu nhat + nhan


def _parse_netlist(text):
    """Doc mo ta netlist van ban -> (blocks, out_map).
    Moi dong khoi: 'ten : OP : dau_vao(kem vai tro) : tham_so'.
    Dong ngo ra:   'OUT: pin=src, pin=src, ...'. Dong '#...' la ghi chu."""
    blocks, out_map = [], {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("OUT:"):
            for part in line.split(":", 1)[1].split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out_map[k.strip()] = v.strip()
            continue
        parts = line.split(":")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        op = parts[1].strip()
        inputs = []
        if len(parts) >= 3 and parts[2].strip():
            for item in parts[2].split(","):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    role, src = item.split("=", 1)
                    inputs.append((role.strip().lower(), src.strip()))
                else:
                    inputs.append(("in", item))
        params = {}
        if len(parts) >= 4 and parts[3].strip():
            for item in parts[3].split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    try:
                        params[k.strip().lower()] = float(v)
                    except ValueError:
                        params[k.strip().lower()] = v.strip()
        blocks.append({"name": name, "op": op, "inputs": inputs, "params": params})
    return blocks, out_map


def _symbol_shapes():
    global _SYMS
    if _SYMS is None:
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "symbol_shapes.json")
        try:
            _SYMS = json.load(open(p, encoding="utf-8"))
        except Exception:
            _SYMS = {}
    return _SYMS


def _used_symbols(db_path):
    """Danh sach ky hieu THUC SU dung trong cac file DB cua du an (folder chua db_path),
    da loc theo nhung ky hieu co hinh trong symbol_shapes.json, sap theo so lan dung
    (nhieu -> it). Cache theo folder. Rong neu khong co DB."""
    if not db_path:
        return []
    import glob
    import sqlite3
    folder = os.path.dirname(db_path)
    if folder in _USED_SYMS:
        return _USED_SYMS[folder]
    have = set(_symbol_shapes().keys())
    count = {}
    for db in sorted(glob.glob(os.path.join(folder, "*.db"))):
        try:
            c = sqlite3.connect(db).cursor()
            for sym, n in c.execute("SELECT SYMBOL,COUNT(*) FROM CAD_BLOCK GROUP BY SYMBOL"):
                if sym and sym in have:
                    count[sym] = count.get(sym, 0) + int(n or 0)
        except Exception:
            continue
    used = sorted(count.keys(), key=lambda s: (-count[s], s))
    _USED_SYMS[folder] = used
    return used


_RAW_PINS = None
_SEM = None


def _raw_pins():
    """core/macro_pins.json nguyen ban (key = ten SYMBOL) -> tra macrocode cua symbol."""
    global _RAW_PINS
    if _RAW_PINS is None:
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "macro_pins.json")
        try:
            _RAW_PINS = json.load(open(p, encoding="utf-8"))
        except Exception:
            _RAW_PINS = {}
    return _RAW_PINS


def _sem_all():
    """Gop analog_sem + logic_sem: macrocode -> {op, ...}. Dung de tinh khi chay so do."""
    global _SEM
    if _SEM is None:
        _SEM = {}
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core")
        for f in ("analog_sem.json", "logic_sem.json"):
            try:
                d = json.load(open(os.path.join(base, f), encoding="utf-8"))
                for k, v in d.items():
                    _SEM[str(k).upper()] = v
            except Exception:
                pass
    return _SEM


def _sym_op(sym):
    """(macrocode, sem_entry) cho 1 ky hieu; sem_entry co 'op' neu tinh duoc."""
    code = str((_raw_pins().get(sym) or {}).get("macrocode", "")).upper()
    return code, (_sem_all().get(code) or {})


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _noi_suy(pts, x):
    """Noi suy tuyen tinh tren bang gay khuc F(x).

    Phai tra DUNG NHU core/sheet_sim._func_interp: ngoai khoang thi giu muc dau/cuoi,
    khong ngoai suy. Lech o day thi cung mot khoi F(x) se cho hai so khac nhau giua so
    do noi va trang - va nguoi dung khong biet tin cai nao."""
    if len(pts) < 2 or not _num(x):
        return None
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else (y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return None


def _compute_op(op, ins, roles, sem, blk=None):
    """Tinh 1 khoi. ins/roles song song theo tung chan VAO (value hoac None; role la
    nhan chu gan chan: '+','-','A','B','S','R'...). Tra ve gia tri ngo ra (hoac None
    neu thieu du lieu / op chua ho tro).

    blk chi can cho FUNC: bang gay khuc la cua RIENG tung khoi F(x) (4.290 khoi deu
    chung ma 4035), khong suy ra duoc tu op hay sem."""
    vals = [v for v in ins if _num(v)]
    if op == "FUNC":
        pts = list(getattr(blk, "fx_pts", None) or [])
        return _noi_suy(pts, vals[0]) if (pts and vals) else None

    def byrole(*names):
        for nm in names:
            for r, v in zip(roles, ins):
                if r == nm and _num(v):
                    return v
        return None

    if op in ("ADD", "SUM"):
        return sum(vals) if vals else None
    if op == "MUL":
        if not vals:
            return None
        p = 1.0
        for v in vals:
            p *= v
        return p
    if op == "SUB":
        plus, minus = byrole("+"), byrole("-")
        if plus is None or minus is None:
            return (vals[0] - vals[1]) if len(vals) >= 2 else None
        return plus - minus
    if op == "DIV":
        a, b = byrole("A"), byrole("B")
        if a is None or b is None:
            if len(vals) < 2:
                return None
            a, b = vals[0], vals[1]
        return (a / b) if b not in (0, 0.0) else None
    if op == "MAX":
        return max(vals) if vals else None
    if op == "MIN":
        return min(vals) if vals else None
    if op == "AVG":
        return sum(vals) / len(vals) if vals else None
    if op == "MID":
        if not vals:
            return None
        s = sorted(vals)
        return s[len(s) // 2]
    if op == "ABS":
        return abs(vals[0]) if vals else None
    if op == "PULSE":
        # Xung mot nhat (PO/TDWO): o trang thai XAC LAP xung da tat nen ra 0, khong bam
        # theo dau vao. Phai tra dung nhu core/sheet_sim.py, neu khong thi so do noi va
        # sheet se hien 2 gia tri khac nhau cho cung 1 khoi. PG la mach dao dong, khong
        # co trang thai xac lap nao -> None ("chua biet") thay vi bia ra 0 hay 1.
        return None if (sem or {}).get("tmr") == "PG" else 0
    if op in ("GAIN", "PASS"):
        return vals[0] if vals else None      # GAIN: thieu tham so k -> tam coi k=1
    if op == "CONST":
        return sem.get("val")
    if op == "NOT":
        return None if (not ins or ins[0] is None) else (1 - (1 if ins[0] else 0))
    if op in ("AND", "NAND"):
        if any(_num(v) and v == 0 for v in ins):
            r = 0
        elif any(v is None for v in ins):
            r = None
        else:
            r = 1 if vals else None
        return r if op == "AND" else (None if r is None else 1 - r)
    if op in ("OR", "NOR"):
        if any(_num(v) and v != 0 for v in ins):
            r = 1
        elif any(v is None for v in ins):
            r = None
        else:
            r = 0
        return r if op == "OR" else (None if r is None else 1 - r)
    if op == "XOR":
        if any(v is None for v in ins):
            return None
        return sum(1 for v in vals if v != 0) % 2
    if op == "SR":
        s, r = byrole("S"), byrole("R")
        if s is None and r is None:
            return None
        if s:
            return 1
        return 0
    return None       # FUNC / CMP / SELECT ... chua ho tro tinh tu dong


def _macro_pins_by_code():
    """macrocode -> {'abbr', 'pins':[(pinno, name, side)]} lay tu core/macro_pins.json
    (chan that cua khoi: so chan + ten + phia in/out)."""
    global _MACRO_PINS
    if _MACRO_PINS is None:
        _MACRO_PINS = {}
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "macro_pins.json")
        try:
            raw = json.load(open(p, encoding="utf-8"))
        except Exception:
            raw = {}
        for _sym, v in raw.items():
            code = str(v.get("macrocode", "")).upper()
            if not code or code in _MACRO_PINS:
                continue
            pins = []
            for k, pin in v.get("pins", {}).items():
                pins.append((str(k), pin.get("name") or "", pin.get("side", "in")))
            _MACRO_PINS[code] = {"abbr": v.get("abbr", ""), "pins": pins}
    return _MACRO_PINS


def _resolve_pin_signals(db_path, bid):
    """{pinno(str): (netid, label)} - tin hieu ngoai that noi vao tung chan cua 1 khoi
    cu the (BLOCK_ID) trong DB du an. Rong neu khong co DB/khoi."""
    if not (db_path and bid is not None):
        return {}
    try:
        import core.dbreader as D
        import core.sheet_render as SR
        c = D.connect(db_path).cursor()
        R = D._resolvers(db_path)
        srow = c.execute("SELECT ID FROM CAD_BLOCK WHERE BLOCK_ID=? LIMIT 1", (bid,)).fetchone()
        sheet_id = srow[0] if srow else None
        out = {}
        for pn, sig in c.execute(
                "SELECT PINNO,SIGNALID FROM CAD_BLOCK_PIN WHERE BLOCK_ID=? ORDER BY PINNO", (bid,)):
            sig = D._clean(sig)
            label = ""
            if sig and sheet_id is not None:
                label, _ref = SR._res(R, sheet_id, sig)
            out[str(pn)] = (sig, label)
        return out
    except Exception:
        return {}


def _sym_bbox(shp):
    xs, ys = [], []
    for x1, y1, x2, y2 in shp.get("lines", []):
        xs += [x1, x2]; ys += [y1, y2]
    for rx, ry, rw, rh, *_ in shp.get("rects", []):
        xs += [rx, rx + rw]; ys += [ry, ry + rh]
    for cx, cy, cr, *_ in shp.get("circles", []):
        xs += [cx - cr, cx + cr]; ys += [cy - cr, cy + cr]
    if not xs:
        return 0.0, 0.0, shp.get("w", 10.0) or 10.0, shp.get("h", 10.0) or 10.0
    return min(xs), min(ys), (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0


def _ports_of(shp):
    """Suy ra diem noi (port) tu hinh hoc ky hieu. 1 port la dau day 'thua' (dangling)
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
    if not conn:      # ky hieu rong (op khong co shape) -> port mac dinh 1 in trai + 1 out phai
        bx, by, bw, bh = _sym_bbox(shp)
        return [(bx, by + bh / 2, "in"), (bx + bw, by + bh / 2, "out")]
    xs = [p[0] for p in conn]; ys = [p[1] for p in conn]
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
                c[0] += x; c[1] += y; c[2] += 1; break
        else:
            clusters.append([x, y, 1])

    ports = []
    for sx, sy, n in clusters:
        x, y = sx / n, sy / n
        right = x >= br - 0.5 and bt - 0.5 <= y <= bb + 0.5
        ports.append((round(x, 1), round(y, 1), "out" if right else "in"))
    ports.sort(key=lambda p: (p[2] != "in", p[1], p[0]))
    if not ports:
        bx, by, bw, bh = _sym_bbox(shp)
        ports = [(bx, by + bh / 2, "in"), (bx + bw, by + bh / 2, "out")]
    return ports


def _port_roles(shp, unit_ports):
    """Nhan vai tro tung chan theo NHAN CHU gan nhat trong ky hieu ('+','-','A','B',
    'S','R'...). Dung de biet chan nao la so bi tru / mau so... khi tinh."""
    texts = [t for t in shp.get("texts", []) if str(t[3]).strip() and len(str(t[3]).strip()) <= 3]
    roles = []
    for (px, py, _side) in unit_ports:
        best, bd = "", None
        for t in texts:
            d = (t[0] - px) ** 2 + (t[1] - py) ** 2
            if bd is None or d < bd:
                bd, best = d, str(t[3]).strip()
        roles.append(best.upper() if (bd is not None and bd <= 40) else "")
    return roles


def _sym_icon(sym):
    if sym in _THUMBS:
        return _THUMBS[sym]
    shp = _symbol_shapes().get(sym, {})
    bx, by, bw, bh = _sym_bbox(shp)
    W, H, pad = 84, 60, 8
    scale = min((W - 2 * pad) / bw, (H - 2 * pad) / bh)
    ox = (W - bw * scale) / 2 - bx * scale
    oy = (H - bh * scale) / 2 - by * scale
    pm = QPixmap(W, H); pm.fill(QColor("#FFFFFF"))
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(_COL_SYM, 1.2))

    def X(v):
        return ox + v * scale

    def Y(v):
        return oy + v * scale

    for x1, y1, x2, y2 in shp.get("lines", []):
        p.drawLine(int(X(x1)), int(Y(y1)), int(X(x2)), int(Y(y2)))
    for rx, ry, rw, rh, *fl in shp.get("rects", []):
        if fl and fl[0]:
            p.fillRect(QRectF(X(rx), Y(ry), rw * scale, rh * scale), QBrush(_COL_SYM))
        p.drawRect(QRectF(X(rx), Y(ry), rw * scale, rh * scale))
    for cx, cy, cr, *fl in shp.get("circles", []):
        p.drawEllipse(QRectF(X(cx - cr), Y(cy - cr), 2 * cr * scale, 2 * cr * scale))
    for tx in shp.get("texts", []):
        ps = max(6, int(tx[2] * scale))
        fnt = QFont("Segoe UI"); fnt.setPixelSize(ps); fnt.setBold(True); p.setFont(fnt)
        p.drawText(int(X(tx[0])), int(Y(tx[1])), str(tx[3]))
    p.end()
    ic = QIcon(pm)
    _THUMBS[sym] = ic
    return ic


# Ky hieu khoi F(x) trong thu vien (macrocode 4035). Kiem lai neu doi symbol_shapes.
_SYM_FX = "FNG_I"


def _design_path(code):
    """Noi ghi ban ve.

    Ban ve theo MA khoi nam trong core/internal_design: no la mo hinh cua khoi, dung
    chung cho moi du an, di kem ma nguon. Ban ve TU DO thi khong thuoc ma nao va la
    cua rieng nguoi dung, nen ghi vao data/ canh app - cho do khong bi ban cap nhat
    app de len (xem core/duong_dan.py)."""
    if not code:
        from core import duong_dan as DD
        d = os.path.join(DD.thu_muc_du_lieu(), "design")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "so_do_tu_do.json")
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "internal_design")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % code)


class _BaseItem(QGraphicsItemGroup):
    """Nen chung: keo duoc, chon duoc, co danh sach port (local px). Khi doi vi tri
    -> yeu cau dialog ve lai day. Khi click trong che do noi day -> chon port gan nhat."""

    def __init__(self, bid, dialog):
        super().__init__()
        self.bid = bid
        self._dialog = dialog
        self.ports = []          # list (px, py, side) local
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def _add_port_dots(self):
        for px, py, side in self.ports:
            col = _COL_PORT_IN if side == "in" else _COL_PORT_OUT
            d = self._dialog.scene.addEllipse(
                px - _PORT_R, py - _PORT_R, 2 * _PORT_R, 2 * _PORT_R,
                QPen(col, 1.0), QBrush(QColor("#FFFFFF")))
            d.setZValue(3)
            self.addToGroup(d)

    def port_scene_pos(self, idx):
        px, py, _s = self.ports[idx]
        return self.mapToScene(QPointF(px, py))

    def nearest_port(self, local_pt):
        best, bd = 0, None
        for i, (px, py, _s) in enumerate(self.ports):
            d = (px - local_pt.x()) ** 2 + (py - local_pt.y()) ** 2
            if bd is None or d < bd:
                bd, best = d, i
        return best

    def nearest_port_within(self, local_pt, thresh=13.0):
        """(idx, khoang cach) cua port gan diem nhat neu trong nguong; nguoc lai None."""
        best, bd = None, None
        for i, (px, py, _s) in enumerate(self.ports):
            d = ((px - local_pt.x()) ** 2 + (py - local_pt.y()) ** 2) ** 0.5
            if bd is None or d < bd:
                bd, best = d, i
        return (best, bd) if (best is not None and bd <= thresh) else None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._dialog._redraw_wires()
        return super().itemChange(change, value)

    def mousePressEvent(self, ev):
        # bam GAN 1 chan (port) -> keo de noi day; bam vao than khoi -> di chuyen binh thuong
        hit = self.nearest_port_within(ev.pos())
        if hit is not None:
            self._wiring = True
            self._dialog._begin_wire(self, hit[0], ev.scenePos())
            ev.accept()
            return
        self._wiring = False
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if getattr(self, "_wiring", False):
            self._dialog._update_wire(ev.scenePos())
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if getattr(self, "_wiring", False):
            self._wiring = False
            self._dialog._end_wire(ev.scenePos())
            ev.accept()
            return
        super().mouseReleaseEvent(ev)


class _SymItem(_BaseItem):
    """1 ky hieu tinh toan tren canvas - ve tu geometry symbol_shapes + cac port."""

    def __init__(self, bid, sym, dialog, fx=None):
        super().__init__(bid, dialog)
        self.sym = sym
        self.kind = "block"
        # Bang gay khuc RIENG cua mot khoi F(x) that trong DB. Rong = khoi thuong.
        self.fx_pts = [tuple(p) for p in (fx or {}).get("pts") or []]
        self.fx_name = ((fx or {}).get("ten") or "").strip()
        self.macrocode, sem = _sym_op(sym)
        self.op = sem.get("op", "")
        self.sem = sem
        self.port_roles = []
        self._out_texts = {}     # port_idx -> QGraphicsTextItem (gia tri tinh duoc)
        # khoi tich phan (dong)
        self.is_integ = self.macrocode in _INTEG_CODES
        self.ti = 1.0            # hang so thoi gian tich phan (cai duoc)
        self.init_val = 0.0      # gia tri khoi tao
        self.state = 0.0
        self.x_port_idx = None   # chan VAO chinh (X) de tich phan
        self.out_idx = None
        self._build()
        if self.fx_pts:
            self.update_label()
        if self.is_integ:
            self.op = self.op or "INTEG"
            ins = [i for i, p in enumerate(self.ports) if p[2] == "in"]
            outs = [i for i, p in enumerate(self.ports) if p[2] == "out"]
            self.out_idx = outs[0] if outs else None
            if ins:      # X = chan vao trai nhat, gan giua than nhat
                midy = sum(self.ports[i][1] for i in ins) / len(ins)
                self.x_port_idx = min(ins, key=lambda i: (self.ports[i][0], abs(self.ports[i][1] - midy)))
            self.update_label()

    def _build(self):
        shp = _symbol_shapes().get(self.sym, {})
        pen = QPen(_COL_SYM, 1.4); blk = QBrush(_COL_SYM); nob = QBrush(Qt.BrushStyle.NoBrush)
        sc = self._dialog.scene
        made = []
        for x1, y1, x2, y2 in shp.get("lines", []):
            made.append(sc.addLine(x1 * SC, y1 * SC, x2 * SC, y2 * SC, pen))
        for rx, ry, rw, rh, *fl in shp.get("rects", []):
            made.append(sc.addRect(rx * SC, ry * SC, rw * SC, rh * SC, pen,
                                   blk if (fl and fl[0]) else nob))
        for cx, cy, cr, *fl in shp.get("circles", []):
            made.append(sc.addEllipse((cx - cr) * SC, (cy - cr) * SC, 2 * cr * SC, 2 * cr * SC,
                                      pen, blk if (fl and fl[0]) else nob))
        for tx in shp.get("texts", []):
            ps = max(6, int(tx[2] * SC))
            fnt = QFont("Segoe UI"); fnt.setPixelSize(ps); fnt.setBold(True)
            it = sc.addText(str(tx[3]), fnt)
            col = tx[4] if len(tx) > 4 else "#000000"
            it.setDefaultTextColor(_COL_SYM if (not col or col.lower() in ("#000000", "#000", "black"))
                                   else QColor(col))
            it.setPos(tx[0] * SC - 2, tx[1] * SC - ps)
            made.append(it)
        if not made:
            made.append(sc.addRect(0, 0, 10 * SC, 6 * SC, pen, nob))
        for it in made:
            self.addToGroup(it)
        unit_ports = _ports_of(shp)
        self.ports = [(px * SC, py * SC, side) for (px, py, side) in unit_ports]
        self.port_roles = _port_roles(shp, unit_ports)
        self._add_port_dots()
        lab = sc.addText("%s%s" % (self.sym, ("  [%s]" % self.op) if self.op else ""),
                         QFont("Segoe UI", 7))
        lab.setDefaultTextColor(QColor("#94A3B8"))
        br = self.childrenBoundingRect()
        lab.setPos(br.x(), br.y() - 15)
        self.addToGroup(lab)
        self._lab = lab
        self.setToolTip("%s%s" % (self.sym, ("  op=%s" % self.op) if self.op else ""))

    def set_out_value(self, idx, v):
        """Hien gia tri tinh duoc canh chan ra idx (mau cam)."""
        t = self._out_texts.get(idx)
        if t is None:
            t = self._dialog.scene.addText("", QFont("Segoe UI", 9, QFont.Weight.Bold))
            t.setDefaultTextColor(QColor("#B45309"))
            t.setZValue(4)
            self.addToGroup(t)            # gan vao group TRUOC
            px, py, _s = self.ports[idx]
            t.setPos(px + 6, py - 10)     # roi dat toa do LOCAL trong group
            self._out_texts[idx] = t
        t.setPlainText("" if v is None else ("%.4g" % v if _num(v) else str(v)))

    def update_label(self):
        if getattr(self, "_lab", None) is None:
            return
        if self.fx_pts:
            # Ten ma "4035"/"FNG_I" khong noi len gi vi 4.290 khoi F(x) deu chung ma do;
            # phai hien TEN va so diem thi moi biet dang cam dung duong cong nao.
            extra = "  %s (%d diem)" % (self.fx_name or "F(x)", len(self.fx_pts))
        elif self.is_integ:
            extra = "  TI=%.4g" % self.ti
        else:
            extra = ("  [%s]" % self.op) if self.op else ""
        self._lab.setPlainText("%s%s" % (self.sym, extra))

    def mouseDoubleClickEvent(self, ev):
        if self.is_integ:
            self._dialog._edit_integ(self)
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)


class _PinItem(_BaseItem):
    """1 node VAO/RA cua khoi (chan that): o bo + ten chan, ten tin hieu ngoai (that)
    va gia tri song; 1 port (input->phai, output->trai)."""

    W, H = 168, 46

    def __init__(self, bid, name, side, dialog, pinno=""):
        super().__init__(bid, dialog)
        self.pname = name
        self.side = side
        self.pinno = str(pinno)
        self.kind = "pin"
        self.ext_net = ""
        self.ext_label = ""
        self.value = None        # gia tri so hien tai (de bo tinh dung lam nguon)
        self._ext_item = None
        self._val_item = None
        self._build()

    def _build(self):
        sc = self._dialog.scene
        fill = _COL_PIN_IN if self.side == "in" else _COL_PIN_OUT
        pen = QPen(_COL_PORT, 1.3)
        r = sc.addRect(0, 0, self.W, self.H, pen, QBrush(fill))
        self.addToGroup(r)
        t = sc.addText(self.pname or "(pin)", QFont("Segoe UI", 8, QFont.Weight.Bold))
        t.setDefaultTextColor(QColor("#1E2433"))
        t.setPos(4, 2)
        self.addToGroup(t)
        # dong 2: ten tin hieu ngoai that (link tu DB)
        self._ext_item = sc.addText("", QFont("Segoe UI", 7))
        self._ext_item.setDefaultTextColor(QColor("#0A6B7A"))
        self._ext_item.setTextWidth(self.W - 34)
        self._ext_item.setPos(4, self.H / 2 - 3)
        self.addToGroup(self._ext_item)
        # gia tri song (goc ngoai cua node)
        self._val_item = sc.addText("", QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._val_item.setDefaultTextColor(QColor("#B45309"))
        self.addToGroup(self._val_item)
        if self.side == "in":
            self.ports = [(self.W, self.H / 2, "out")]
            self._val_item.setPos(self.W + 8, self.H / 2 - 9)
        else:
            self.ports = [(0, self.H / 2, "in")]
            self._val_item.setPos(-34, self.H / 2 - 9)
        self._add_port_dots()

    def set_external(self, net, label):
        self.ext_net = net or ""
        self.ext_label = label or ""
        txt = (("%s  %s" % (net, label)).strip() if (net or label) else "(chua noi)")
        self._ext_item.setPlainText(txt)
        self.setToolTip("%s%s" % (self.pname, ("  <-  %s %s" % (net, label)) if net else ""))

    def mouseDoubleClickEvent(self, ev):
        """Nhay doi node VAO -> go gia tri thu. Mo tu danh muc thi khong gan voi khoi nao
        tren sheet nen khong co gia tri that de lay: khong nhap tay duoc thi so do chi
        toan None va nut 'Tinh logic noi' khong noi len dieu gi."""
        if self.side != "in":
            return super().mouseDoubleClickEvent(ev)
        cu = "" if self.value is None else ("%g" % self.value)
        txt, ok = QInputDialog.getText(
            self._dialog, "Gia tri thu cho chan %s" % self.pname,
            "Nhap so (digital go 0 hoac 1). De TRONG = chua biet:", text=cu)
        if not ok:
            return
        txt = (txt or "").strip()
        if not txt:
            self.set_value(None)
        else:
            try:
                self.set_value(float(txt))
            except ValueError:
                self._dialog._hint.setText("'%s' khong phai la so - bo qua." % txt)
                return
        self._dialog._evaluate()          # doi dau vao -> thay ngay dau ra

    def set_value(self, v):
        self.value = v
        if v is None:
            self._val_item.setPlainText("")
        elif isinstance(v, bool):
            self._val_item.setPlainText("1" if v else "0")
        elif isinstance(v, (int, float)):
            self._val_item.setPlainText("%.4g" % v)
        else:
            self._val_item.setPlainText(str(v))


class InternalDesignDialog(QDialog):
    """Khung ve logic noi: node vao/ra dat san, nguoi dung them khoi tinh toan o giua
    va noi day qua cac port."""

    def __init__(self, code, name="", parent=None, db_path=None, sheet_id=None, bid=None,
                 sim_values=None, dig_env=None, ana_env=None):
        super().__init__(parent)
        self.main = parent
        self.code = (code or "").upper()
        # Khong co ma khoi = BAN VE TU DO: mot ban thu de tu rap so do va cho chay,
        # khong phai mo hinh noi bo cua khoi nao ca.
        self.tu_do = not self.code
        self.bname = name
        self.db_path = db_path
        self.sheet_id = sheet_id
        self.bid = bid
        # gia tri mo phong DANG hien ben ngoai (tren sheet) - de trong dung y het ben ngoai
        self._sim_values = dict(sim_values) if sim_values else None
        self._dig_env = dict(dig_env) if dig_env else {}
        self._ana_env = dict(ana_env) if ana_env else {}
        self._pin_sig = _resolve_pin_signals(db_path, bid)   # pinno -> (net, label)
        self.resize(1200, 760)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self._items = {}          # bid -> _BaseItem
        self._wires = []          # list[[[idA,portA],[idB,portB]]]
        self._wire_items = []
        self._next_id = 1
        self._wire_from = None     # (item, portidx) khi dang keo day
        self._wire_temp = None     # duong tam theo chuot
        self._drop_n = 0

        lay = QVBoxLayout(self)
        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)
        self._dat_tieu_de()

        bar = QHBoxLayout()
        b_del = QPushButton("Xoa khoi chon"); b_del.clicked.connect(self._delete_selected)
        bar.addWidget(b_del)
        b_in = QPushButton("+ Node vao")
        b_in.setToolTip("Them mot dau vao de go gia tri thu vao so do")
        b_in.clicked.connect(lambda: self._them_node("in"))
        bar.addWidget(b_in)
        b_out = QPushButton("+ Node ra")
        b_out.setToolTip("Them mot dau ra de doc ket qua")
        b_out.clicked.connect(lambda: self._them_node("out"))
        bar.addWidget(b_out)
        b_pins = QPushButton("Dat lai node vao/ra"); b_pins.clicked.connect(self._reset_pins)
        bar.addWidget(b_pins)
        b_clear = QPushButton("Xoa het khoi them"); b_clear.clicked.connect(self._clear_blocks)
        bar.addWidget(b_clear)
        bar.addSpacing(20)
        self.b_val = QPushButton("Tinh gia tri (tu DB)")
        self.b_val.clicked.connect(self._refresh_values)
        self.b_val.setEnabled(bool(self.db_path and self.sheet_id is not None))
        self.b_val.setToolTip(
            "Lay gia tri that cua khoi nay tren mot trang dang mo."
            if self.b_val.isEnabled() else
            "Mo tu danh muc nen khong gan voi khoi cu the nao tren trang. "
            "Nhay doi vao node VAO de tu go gia tri thu.")
        bar.addWidget(self.b_val)
        self.b_eval = QPushButton("Tinh logic noi (chay so do)")
        self.b_eval.clicked.connect(self._evaluate)
        bar.addWidget(self.b_eval)
        bar.addWidget(QLabel("dt"))
        self.sp_dt = QDoubleSpinBox(); self.sp_dt.setRange(0.001, 1e4); self.sp_dt.setDecimals(3)
        self.sp_dt.setValue(1.0); self.sp_dt.setFixedWidth(70); bar.addWidget(self.sp_dt)
        bar.addWidget(QLabel("buoc"))
        self.sp_n = QSpinBox(); self.sp_n.setRange(1, 100000); self.sp_n.setValue(100)
        self.sp_n.setFixedWidth(70); bar.addWidget(self.sp_n)
        self.b_run = QPushButton("Run (tich phan)"); self.b_run.clicked.connect(self._run_dynamic)
        bar.addWidget(self.b_run)
        self.b_net = QPushButton("Nhap netlist...")
        self.b_net.clicked.connect(self._import_netlist_file)
        self.b_net.setToolTip("Dung so do tu file mo ta netlist van ban (ten:OP:dau_vao:tham_so)")
        bar.addWidget(self.b_net)
        b_save = QPushButton("Luu"); b_save.clicked.connect(self._save); bar.addWidget(b_save)
        bar.addStretch(1)
        lay.addLayout(bar)

        body = QHBoxLayout(); lay.addLayout(body, 1)

        pal = QWidget(); pv = QVBoxLayout(pal); pv.setContentsMargins(0, 0, 0, 0)
        pv.addWidget(QLabel("Thu vien ky hieu - nhay doi de them:"))
        # chi cac ky hieu THUC SU dung trong cac file DB cua du an (neu co DB)
        self._used_syms = _used_symbols(self.db_path)
        self.cb_all = QCheckBox("Hien tat ca ky hieu (%d)" % len(_symbol_shapes()))
        if self._used_syms:
            self.cb_all.setText("Hien tat ca ky hieu (%d) - dang loc theo DB (%d dung)"
                                % (len(_symbol_shapes()), len(self._used_syms)))
        else:
            self.cb_all.setChecked(True); self.cb_all.setEnabled(False)
        self.cb_all.toggled.connect(self._on_scope_changed)
        pv.addWidget(self.cb_all)
        self.search = QLineEdit(); self.search.setPlaceholderText("Tim ky hieu... (OR, XFR, LMI, FF...)")
        self.search.textChanged.connect(self._filter); pv.addWidget(self.search)
        self.plist = QListWidget()
        self.plist.setViewMode(QListWidget.ViewMode.IconMode)
        self.plist.setIconSize(QSize(84, 60))
        self.plist.setGridSize(QSize(104, 90))
        self.plist.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.plist.setMovement(QListWidget.Movement.Static)
        self.plist.setWordWrap(True)
        self.plist.setSpacing(4)
        self.plist.itemDoubleClicked.connect(self._add_item)
        pv.addWidget(self.plist, 1)
        # Ba the, vi ba nguon khoi khac han nhau: ky hieu la HINH (ve gi cung duoc),
        # F(x) la mot BANG SO cua rieng tung khoi that, con khoi chuc nang la mot BAN VE
        # da luu. De chung mot danh sach thi khong loc noi cai nao ra cai nao.
        from ui import internal_panels as _P
        self.pal_tabs = QTabWidget()
        self.pal_tabs.addTab(pal, "Ky hieu")
        self.p_fx = _P.FxPanel(self.main)
        self.p_fx.chon.connect(self._add_fx)
        self.pal_tabs.addTab(self.p_fx, "F(x)")
        self.p_khoi = _P.KhoiPanel(self.main)
        self.p_khoi.chon.connect(self._mo_ma)
        self.pal_tabs.addTab(self.p_khoi, "Khoi chuc nang")
        self.pal_tabs.setFixedWidth(360)
        body.addWidget(self.pal_tabs)

        self._refresh_scope()
        self._filter("")

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-100, -100, 3000, 2000)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#FBFCFE")))
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        body.addWidget(self.view, 1)

        self._load()
        # tu hien ngay gia tri ben ngoai (neu co) de khoi phai bam nut
        if self.b_val.isEnabled():
            self._refresh_values(quiet=True)

    # ---------- tieu de / node tu them ----------
    def _dat_tieu_de(self):
        if self.tu_do:
            self.setWindowTitle("Ban ve mo phong (tu thiet ke)")
            self._hint.setText(
                "Ban ve TU DO: bam '+ Node vao' de tao dau vao, nhay doi ky hieu ben trai "
                "de them khoi tinh, hoac sang the F(x) tha vao mot duong cong that. NOI DAY: "
                "keo tu 1 cham tron sang 1 cham tron khac. Nhay doi node VAO de go gia tri, "
                "roi bam 'Tinh logic noi'. Chon khoi + Delete de xoa. 'Luu' de ghi.")
        else:
            self.setWindowTitle("Ve logic noi (tu ve): %s (%s)" % (self.bname or "", self.code))
            self._hint.setText(
                "Node vao (trai) / ra (phai) da co san theo chan that cua ma %s. Nhay doi ky "
                "hieu ben trai de them khoi tinh toan, keo tha tu do (bam vao THAN khoi de di "
                "chuyen). De NOI DAY: keo tu 1 cham tron (chan) tha vao 1 cham tron khac. Nhay "
                "doi node VAO de go gia tri thu. Chon khoi + Delete de xoa. 'Luu' de ghi."
                % self.code)

    def _them_node(self, side):
        """Them mot node vao/ra do nguoi dung tu dat ten. Ban ve tu do khong co ma khoi
        nen khong co chan mac dinh nao - khong co nut nay thi khong the dat dau vao."""
        cu = [i for i in self._items.values()
              if getattr(i, "kind", "") == "pin" and i.side == side]
        goi = "%s%d" % ("IN" if side == "in" else "OUT", len(cu) + 1)
        ten, ok = QInputDialog.getText(
            self, "Them node %s" % ("VAO" if side == "in" else "RA"), "Ten node:", text=goi)
        if not ok or not (ten or "").strip():
            return
        x = 40 if side == "in" else 1180
        it = self._add_pin(ten.strip(), side, x, 60 + len(cu) * 58)
        self.view.centerOn(it)

    # ---------- F(x) that tu DB / doi ma khoi ----------
    def _add_fx(self, info):
        """Tha mot khoi F(x) CO THAT vao so do, kem dung bang gay khuc cua no.

        Khong lay duoc bang thi khong them: mot khoi F(x) rong luon tra None, keo theo
        ca nhanh phia sau cung None - nhin nhu so do sai chu khong nhu thieu du lieu."""
        from ui import internal_panels as _P
        pts, ten, ghi = _P.diem_fx(info["db"], info["sheet"], info["tag"])
        if not pts:
            self._hint.setText("Khong tha duoc F(x) '%s': %s" % (info["ten"], ghi))
            return
        self._drop_n += 1
        off = (self._drop_n % 12) * 26
        it = self._add_block(_SYM_FX, 480 + off, 120 + off,
                             fx={"pts": pts, "ten": ten or info["ten"]})
        self.view.centerOn(it)
        self._hint.setText("Da tha F(x) '%s' - %d diem, x tu %g den %g.%s"
                           % (ten or info["ten"], len(pts), pts[0][0], pts[-1][0],
                              ("  [%s]" % ghi) if ghi else ""))

    def _mo_ma(self, code, ten):
        """Chuyen ca so do sang ban ve cua mot ma khoi khac (the 'Khoi chuc nang')."""
        code = (code or "").upper()
        if code == self.code:
            self._hint.setText("Dang o ban ve cua ma %s roi." % code)
            return
        if self._items and QMessageBox.question(
                self, "Doi ban ve",
                "Chuyen sang ban ve cua ma %s? Phan chua luu tren so do hien tai se mat."
                % code) != QMessageBox.StandardButton.Yes:
            return
        for it in list(self._items.values()):
            self._remove_item(it)
        self._wires = []
        self._redraw_wires()
        self.code, self.bname, self.tu_do = code, ten, False
        self._next_id, self._drop_n = 1, 0
        self._dat_tieu_de()
        self._load()

    # ---------- palette ----------
    def _refresh_scope(self):
        """Chon nguon ky hieu: chi cac ky hieu dung trong DB (mac dinh) hoac ca thu vien."""
        if self.cb_all.isChecked() or not self._used_syms:
            self._all_syms = sorted(_symbol_shapes().keys())
        else:
            self._all_syms = list(self._used_syms)   # da sap theo so lan dung

    def _on_scope_changed(self, _on):
        self._refresh_scope()
        self._filter(self.search.text())

    def _filter(self, txt):
        t = (txt or "").strip().upper()
        self.plist.clear()
        matched = [s for s in self._all_syms if (not t or t in s.upper())]
        shown = matched[:400]
        for s in shown:
            it = QListWidgetItem(_sym_icon(s), s); it.setToolTip(s)
            self.plist.addItem(it)
        if len(matched) > len(shown):
            self.plist.addItem(QListWidgetItem(
                "... +%d nua, go them tu khoa de loc" % (len(matched) - len(shown))))
        if self.plist.count():
            self.plist.setCurrentRow(0)

    def _add_item(self, it):
        if it is not None and it.text() and _symbol_shapes().get(it.text()):
            self._drop_n += 1
            off = (self._drop_n % 12) * 26
            self._add_block(it.text(), 480 + off, 120 + off)

    # ---------- tao item ----------
    def _new_id(self):
        i = str(self._next_id); self._next_id += 1
        return i

    def _add_block(self, sym, x, y, bid=None, fx=None):
        if bid is None:
            bid = self._new_id()
        else:
            if str(bid).isdigit():
                self._next_id = max(self._next_id, int(bid) + 1)
        item = _SymItem(bid, sym, self, fx=fx)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.scene.addItem(item); item.setPos(x, y)
        self._items[bid] = item
        return item

    def _add_pin(self, name, side, x, y, bid=None, pinno=""):
        if bid is None:
            k = len([i for i in self._items.values()
                     if getattr(i, "kind", "") == "pin"]) + 1
            while ("pin%d" % k) in self._items:
                k += 1        # xoa node giua chung roi them lai thi so dem se trung id
            bid = "pin%d" % k
        item = _PinItem(bid, name, side, self, pinno=pinno)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.scene.addItem(item); item.setPos(x, y)
        self._items[bid] = item
        if self._pin_sig:                      # link ten tin hieu ngoai that (neu co DB)
            net, label = self._pin_sig.get(str(pinno), ("", ""))
            item.set_external(net, label)
        return item

    def _init_pins(self):
        info = _macro_pins_by_code().get(self.code)
        if not info:
            return
        yin = yout = 60
        for pinno, nm, side in info["pins"]:
            if side == "in":
                self._add_pin(nm, "in", 40, yin, pinno=pinno); yin += 58
            else:
                self._add_pin(nm, "out", 1180, yout, pinno=pinno); yout += 58

    def _refresh_values(self, quiet=False):
        """Hien gia tri hien tai cua moi tin hieu ngoai len node vao/ra. Uu tien DUNG
        gia tri dang hien ben ngoai (sheet) de khop y het; neu chua co thi chay lai bo
        mo phong voi dung dau vao nguoi dung da dat ben ngoai (sim_env/sim_analog)."""
        if not (self.db_path and self.sheet_id is not None):
            return
        val = self._sim_values
        src = "gia tri dang hien ben ngoai (sheet)"
        if val is None:
            try:
                import core.sheet_sim as SS
                val, _it = SS.simulate(self.db_path, self.sheet_id, self._dig_env, self._ana_env)
            except Exception as e:
                if not quiet:
                    QMessageBox.warning(self, "Loi", "Khong tinh duoc gia tri: %s" % e)
                return
            src = "mo phong lai voi dau vao ben ngoai"
        n = 0
        for it in self._items.values():
            if getattr(it, "kind", "") == "pin":
                it.set_value(val.get(it.ext_net) if it.ext_net else None)
                n += 1
        if not quiet:
            self._hint.setText("Da lay gia tri (%s) cho %d node vao/ra. Neu ben ngoai chua bat "
                               "mo phong / chua dat dau vao thi cac o gia tri se trong." % (src, n))

    def _build_src(self):
        """{(bid, in_port_idx): (src_bid, out_port_idx)} tu danh sach day noi."""
        items = self._items
        src = {}
        for (a, pa), (b, pb) in self._wires:
            ia, ib = items.get(a), items.get(b)
            if not ia or not ib or pa >= len(ia.ports) or pb >= len(ib.ports):
                continue
            if ib.ports[pb][2] == "in":
                src[(b, pb)] = (a, pa)
            if ia.ports[pa][2] == "in":
                src[(a, pa)] = (b, pb)
        return src

    def _in_val(self, blk, i, val, src):
        s = src.get((blk.bid, i))
        return val.get(s) if s else None

    def _combinational(self, val, src, static_blocks):
        """Lan truyen gia tri qua cac khoi TINH (to hop) toi on dinh. val da duoc gieo
        san nguon (node vao) va ngo ra cac khoi tich phan (= trang thai hien tai)."""
        for _ in range(60):
            for blk in static_blocks:
                ins, roles = [], []
                for i, (px, py, side) in enumerate(blk.ports):
                    if side != "in":
                        continue
                    ins.append(self._in_val(blk, i, val, src))
                    roles.append(blk.port_roles[i] if i < len(blk.port_roles) else "")
                out = _compute_op(blk.op, ins, roles, blk.sem, blk)
                for i, (px, py, side) in enumerate(blk.ports):
                    if side == "out":
                        val[(blk.bid, i)] = out
        return val

    def _seed_and_split(self):
        items = self._items
        val = {}
        for it in items.values():
            if getattr(it, "kind", "") == "pin" and it.side == "in":
                val[(it.bid, 0)] = it.value
        static_blocks = [it for it in items.values()
                         if getattr(it, "kind", "") == "block" and it.op and not it.is_integ]
        integ = [it for it in items.values()
                 if getattr(it, "kind", "") == "block" and it.is_integ]
        return val, static_blocks, integ

    def _show_results(self, val, src, static_blocks, integ):
        nfilled = 0
        for blk in static_blocks + integ:
            for i, (px, py, side) in enumerate(blk.ports):
                if side == "out":
                    v = val.get((blk.bid, i))
                    blk.set_out_value(i, v)
                    if v is not None:
                        nfilled += 1
        for it in self._items.values():
            if getattr(it, "kind", "") == "pin" and it.side == "out":
                s = src.get((it.bid, 0))
                if s is not None:
                    it.set_value(val.get(s))
        return nfilled

    def _evaluate(self):
        """CHAY TINH TO HOP (khong tien thoi gian): khoi tich phan giu nguyen trang thai
        hien tai. Dung de xem cac khoi tinh (SUB/DIV/AND...) va gia tri tich phan hien co."""
        self._refresh_values(quiet=True)
        val, static_blocks, integ = self._seed_and_split()
        src = self._build_src()
        for b in integ:                       # ngo ra khoi tich phan = trang thai hien tai
            if b.out_idx is not None:
                val[(b.bid, b.out_idx)] = b.state
        self._combinational(val, src, static_blocks)
        n = self._show_results(val, src, static_blocks, integ)
        skipped = sorted({b.sym for b in static_blocks if b.op in ("FUNC", "CMP", "SELECT")})
        msg = "Da tinh to hop: %d khoi tinh, %d khoi tich phan, %d ngo ra co gia tri." % (
            len(static_blocks), len(integ), n)
        if integ:
            msg += " Bam 'Run (tich phan)' de tien theo dt cho khoi tich phan."
        if skipped:
            msg += " Chua tinh op: %s." % ", ".join(skipped[:6])
        self._hint.setText(msg)

    def _run_dynamic(self):
        """CHAY DONG: khoi tich phan cong don theo dt qua nhieu buoc (out += X/TI*dt),
        cac khoi tinh tinh lai moi buoc. Ket qua cuoi hien tren so do."""
        self._refresh_values(quiet=True)
        val, static_blocks, integ = self._seed_and_split()
        src = self._build_src()
        dt = self.sp_dt.value(); nsteps = self.sp_n.value()
        for b in integ:
            b.state = b.init_val
        for _ in range(nsteps + 1):
            step_val = dict(val)
            for b in integ:                   # gieo ngo ra = trang thai hien tai
                if b.out_idx is not None:
                    step_val[(b.bid, b.out_idx)] = b.state
            self._combinational(step_val, src, static_blocks)
            for b in integ:                   # tien trang thai: state += X/TI*dt
                if b.x_port_idx is None:
                    continue
                x = self._in_val(b, b.x_port_idx, step_val, src)
                if _num(x):
                    b.state += (x / (b.ti or 1e-9)) * dt
        # hien buoc cuoi
        final = dict(val)
        for b in integ:
            if b.out_idx is not None:
                final[(b.bid, b.out_idx)] = b.state
        self._combinational(final, src, static_blocks)
        n = self._show_results(final, src, static_blocks, integ)
        self._hint.setText("Da chay dong %d buoc (dt=%.3f): %d khoi tich phan cong don, "
                           "%d ngo ra co gia tri." % (nsteps, dt, len(integ), n))

    def _edit_integ(self, blk):
        """Cai dat tham so khoi tich phan: TI (hang so thoi gian) + gia tri khoi tao."""
        ti, ok = QInputDialog.getDouble(self, "Khoi tich phan %s" % blk.sym,
                                        "TI (hang so thoi gian tich phan):", blk.ti, -1e9, 1e9, 4)
        if not ok:
            return
        init, ok2 = QInputDialog.getDouble(self, "Khoi tich phan %s" % blk.sym,
                                           "Gia tri khoi tao (init):", blk.init_val, -1e12, 1e12, 4)
        if not ok2:
            return
        blk.ti = ti if ti != 0 else 1.0
        blk.init_val = init
        blk.state = init
        blk.update_label()
        self._hint.setText("Khoi %s: TI=%.4g, init=%.4g. Bam 'Run (tich phan)' de chay." % (
            blk.sym, blk.ti, blk.init_val))

    # ---------- nhap tu netlist van ban ----------
    def _first_out(self, it):
        for i, p in enumerate(it.ports):
            if p[2] == "out":
                return i
        return 0

    def _pick_in_port(self, blk, tag, used):
        inports = [i for i, p in enumerate(blk.ports) if p[2] == "in"]
        cand = _ROLE_CAND.get(tag, [])
        for i in inports:
            if i in used:
                continue
            r = (blk.port_roles[i] if i < len(blk.port_roles) else "").upper()
            if r and any(r == c or r.startswith(c) for c in cand):
                return i
        free = [i for i in inports if i not in used]
        if not free:
            return None
        if tag == "sel":
            return min(free, key=lambda i: blk.ports[i][1])
        if tag == "in":
            return min(free, key=lambda i: (blk.ports[i][0], blk.ports[i][1]))
        return free[0]

    def _import_netlist_file(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core",
                            "internal_design", "netlist")
        os.makedirs(base, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Chon file netlist", base,
                                              "Netlist/Text (*.txt *.netlist *.net);;All (*)")
        if not path:
            return
        try:
            text = open(path, encoding="utf-8").read()
        except Exception as e:
            QMessageBox.warning(self, "Loi", "Khong doc duoc file: %s" % e)
            return
        self._apply_netlist(text)

    def _apply_netlist(self, text):
        """Dung so do tu mo ta netlist: tha symbol theo OP, tu xep theo do sau phu thuoc,
        noi day theo mo ta. Node vao/ra giu nguyen (theo chan that)."""
        specs, out_map = _parse_netlist(text)
        if not specs:
            QMessageBox.information(self, "Netlist rong", "Khong doc duoc khoi nao tu mo ta.")
            return
        for it in [i for i in self._items.values() if getattr(i, "kind", "") == "block"]:
            self._remove_item(it)
        if not any(getattr(i, "kind", "") == "pin" for i in self._items.values()):
            self._init_pins()
        in_pins = {it.pname: it for it in self._items.values()
                   if getattr(it, "kind", "") == "pin" and it.side == "in"}
        out_pins = {it.pname: it for it in self._items.values()
                    if getattr(it, "kind", "") == "pin" and it.side == "out"}

        # nguon la ten LA (khong phai khoi, khong phai chan tram): VD OPS_IN5, PRM_6,
        # Ftime, hang so 0 -> tao them node bien ben trai de so do khong bi dut day
        names = {s["name"] for s in specs}
        extra = []
        for s in specs:
            for _role, src in s["inputs"]:
                if src not in names and src not in in_pins and src not in extra:
                    extra.append(src)
        ey = 60 + 58 * len([1 for i in self._items.values()
                            if getattr(i, "kind", "") == "pin" and i.side == "in"])
        for nm in extra:
            it = self._add_pin(nm, "in", 40, ey, pinno="")
            in_pins[nm] = it
            ey += 58

        deps = {s["name"]: [src for (_role, src) in s["inputs"] if src in names] for s in specs}
        depth = {}

        def dep(n, trail):
            if n in depth:
                return depth[n]
            if n in trail:
                return 0
            ps = deps.get(n, [])
            d = 0 if not ps else 1 + max((dep(p, trail | {n}) for p in ps), default=0)
            depth[n] = d
            return d
        for s in specs:
            dep(s["name"], frozenset())
        rows = {}
        name2item = {}
        for s in specs:
            c = depth.get(s["name"], 0)
            rows[c] = rows.get(c, 0) + 1
            bx = 320 + c * 175
            by = 40 + (rows[c] - 1) * 130
            sym = _op_symbol(s["op"])
            it = self._add_block(sym, bx, by)
            if it.is_integ and "ti" in s["params"]:
                try:
                    it.ti = float(s["params"]["ti"]) or 1.0
                    it.init_val = float(s["params"].get("init", 0.0))
                    it.state = it.init_val
                    it.update_label()
                except (TypeError, ValueError):
                    pass
            name2item[s["name"]] = it

        def source(nm):
            if nm in name2item:
                it = name2item[nm]
                return it, (it.out_idx if getattr(it, "out_idx", None) is not None else self._first_out(it))
            if nm in in_pins:
                return in_pins[nm], 0
            return None

        wires = []
        skipped = []
        for s in specs:
            blk = name2item[s["name"]]
            used = set()
            for role, src in s["inputs"]:
                srcinfo = source(src)
                if srcinfo is None:
                    skipped.append("%s.%s=%s" % (s["name"], role, src))
                    continue
                tidx = self._pick_in_port(blk, role, used)
                if tidx is None:
                    continue
                used.add(tidx)
                sit, sidx = srcinfo
                wires.append([[sit.bid, sidx], [blk.bid, tidx]])
        for pin, src in out_map.items():
            if src in name2item and pin in out_pins:
                sit = name2item[src]
                wires.append([[sit.bid, self._first_out(sit)], [out_pins[pin].bid, 0]])
        self._wires = wires
        self._redraw_wires()
        self._refresh_values(quiet=True)
        msg = "Da dung tu netlist: %d khoi, %d day. Xem lai roi 'Luu'." % (len(name2item), len(wires))
        if skipped:
            msg += " Bo qua (hang so/tham so hoac ten chua co): %s." % ", ".join(skipped[:8])
        self._hint.setText(msg)

    def _reset_pins(self):
        if not _macro_pins_by_code().get(self.code):
            # Khong co bang chan thi nut nay chi con tac dung XOA SACH node, khong "dat
            # lai" duoc gi - bam vao la mat het dau vao ma khong hieu vi sao.
            self._hint.setText(
                "Ma '%s' khong co bang chan mac dinh de dat lai. Dung '+ Node vao' / "
                "'+ Node ra' de tu them." % (self.code or "(tu do)"))
            return
        for it in [i for i in self._items.values() if getattr(i, "kind", "") == "pin"]:
            self._remove_item(it)
        self._init_pins()
        self._redraw_wires()

    # ---------- noi day (keo tu chan -> chan) ----------
    def _begin_wire(self, item, idx, scene_pos):
        self._wire_from = (item, idx)
        p = item.port_scene_pos(idx)
        pen = QPen(QColor("#E11D48"), 1.8)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._wire_temp = self.scene.addLine(p.x(), p.y(), scene_pos.x(), scene_pos.y(), pen)
        self._wire_temp.setZValue(5)

    def _update_wire(self, scene_pos):
        if not self._wire_temp or not self._wire_from:
            return
        p = self._wire_from[0].port_scene_pos(self._wire_from[1])
        self._wire_temp.setLine(p.x(), p.y(), scene_pos.x(), scene_pos.y())

    def _port_at(self, scene_pos, exclude=None):
        """Tim (item, port_idx) co cham tron gan diem tha nhat (trong nguong)."""
        best = None
        for it in self._items.values():
            if it is exclude:
                continue
            hit = it.nearest_port_within(it.mapFromScene(scene_pos), thresh=15.0)
            if hit is not None and (best is None or hit[1] < best[2]):
                best = (it, hit[0], hit[1])
        return (best[0], best[1]) if best else None

    def _end_wire(self, scene_pos):
        if self._wire_temp:
            self.scene.removeItem(self._wire_temp)
            self._wire_temp = None
        frm = self._wire_from
        self._wire_from = None
        if not frm:
            return
        tgt = self._port_at(scene_pos)
        if not tgt:
            return
        a_item, a_idx = frm
        b_item, b_idx = tgt
        if a_item is b_item and a_idx == b_idx:
            return
        # tranh noi trung y het
        w = [[a_item.bid, a_idx], [b_item.bid, b_idx]]
        if w in self._wires or [w[1], w[0]] in self._wires:
            return
        self._wires.append(w)
        self._redraw_wires()

    def _redraw_wires(self):
        for ln in self._wire_items:
            self.scene.removeItem(ln)
        self._wire_items = []
        pen = QPen(_COL_WIRE, 1.6)
        for (aid, ap), (bid, bp) in self._wires:
            ia, ib = self._items.get(aid), self._items.get(bid)
            if not ia or not ib or ap >= len(ia.ports) or bp >= len(ib.ports):
                continue
            p1 = ia.port_scene_pos(ap); p2 = ib.port_scene_pos(bp)
            ln = self.scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), pen)
            ln.setZValue(-1)
            self._wire_items.append(ln)

    # ---------- sua ----------
    def _delete_selected(self):
        for it in [i for i in self.scene.selectedItems() if isinstance(i, _BaseItem)]:
            self._remove_item(it)
        self._redraw_wires()

    def _remove_item(self, it):
        bid = it.bid
        self._wires = [w for w in self._wires if w[0][0] != bid and w[1][0] != bid]
        self.scene.removeItem(it)
        self._items.pop(bid, None)

    def _clear_blocks(self):
        blocks = [i for i in self._items.values() if getattr(i, "kind", "") == "block"]
        if blocks and QMessageBox.question(
                self, "Xoa het", "Xoa toan bo khoi da them (giu lai node vao/ra)?") \
                != QMessageBox.StandardButton.Yes:
            return
        for it in blocks:
            self._remove_item(it)
        self._redraw_wires()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected(); ev.accept(); return
        super().keyPressEvent(ev)

    # ---------- luu / nap ----------
    def _save(self):
        pins, blocks = [], []
        for it in self._items.values():
            if getattr(it, "kind", "") == "pin":
                pins.append({"id": it.bid, "name": it.pname, "side": it.side, "pinno": it.pinno,
                             "x": round(it.pos().x(), 1), "y": round(it.pos().y(), 1)})
            else:
                b = {"id": it.bid, "sym": it.sym,
                     "x": round(it.pos().x(), 1), "y": round(it.pos().y(), 1)}
                if it.is_integ:
                    b["ti"] = it.ti; b["init"] = it.init_val
                if it.fx_pts:
                    # Chep han bang gay khuc vao ban ve chu khong luu (db, trang, tag):
                    # so do phai mo lai duoc ca khi khong con file DB do trong may.
                    b["fx"] = {"ten": it.fx_name,
                               "pts": [[float(a), float(c)] for a, c in it.fx_pts]}
                blocks.append(b)
        data = {"pins": pins, "blocks": blocks, "wires": self._wires}
        p = _design_path(self.code)
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        QMessageBox.information(self, "Da luu",
            "Da luu ban ve (%d node vao/ra, %d khoi, %d day) vao: %s"
            % (len(pins), len(blocks), len(self._wires), p))
        if getattr(self, "p_khoi", None) is not None and not self.tu_do:
            self.p_khoi.nap()          # cot "Ban ve" ben trai phai doi ngay

    def _load(self):
        p = _design_path(self.code)
        if not os.path.exists(p):
            self._init_pins()
            return
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception:
            self._init_pins(); return
        for pin in data.get("pins", []):
            self._add_pin(pin["name"], pin.get("side", "in"), pin.get("x", 0), pin.get("y", 0),
                          bid=str(pin["id"]), pinno=pin.get("pinno", ""))
        for b in data.get("blocks", []):
            it = self._add_block(b["sym"], b.get("x", 0), b.get("y", 0), bid=str(b["id"]),
                                 fx=b.get("fx"))
            if it.is_integ:
                it.ti = b.get("ti", 1.0)
                it.init_val = b.get("init", 0.0)
                it.state = it.init_val
                it.update_label()
        if not data.get("pins"):
            self._init_pins()
        self._wires = [[list(a), list(b)] for a, b in data.get("wires", [])]
        self._redraw_wires()
