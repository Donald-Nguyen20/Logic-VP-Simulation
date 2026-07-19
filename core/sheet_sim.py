# -*- coding: utf-8 -*-
"""
Mo phong DIGITAL ca sheet: set 0/1 vao net bat ky -> lan qua cac cong logic
(logic_sem) -> tinh gia tri MOI net. Lap toi on dinh de xu ly hoi tiep (chot SR).
Chi doc DB. None = chua biet (dau vao chua set / khoi analog chua mo hinh).
"""
from __future__ import annotations
import os
import json
from collections import defaultdict
from . import dbreader as D
from . import cond_tree as CT
from . import sheet_render as SR
from . import signal_graph as SG


def _all_nets(db, sheet):
    c = D.connect(db).cursor()
    nets = set()
    for (sig,) in c.execute(
            "SELECT DISTINCT p.SIGNALID FROM CAD_BLOCK_PIN p JOIN CAD_BLOCK b "
            "ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=?", (sheet,)):
        s = D._clean(sig)
        if s:
            nets.add(s)
    return nets


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


_PARAMS = {}


def _params(db, sheet):
    """{bid: {paramno(str): value(str)}} cho cac block tren sheet."""
    key = (db, sheet)
    if key in _PARAMS:
        return _PARAMS[key]
    c = D.connect(db).cursor()
    pm = {}
    for bid, pno, pv in c.execute(
            "SELECT bp.BLOCK_ID, bp.PARAMNO, bp.PARAMVALUE FROM CAD_BLOCK_PARAM bp "
            "JOIN CAD_BLOCK b ON bp.BLOCK_ID=b.BLOCK_ID WHERE b.ID=?", (sheet,)):
        pm.setdefault(bid, {})[str(pno)] = pv
    _PARAMS[key] = pm
    return pm


def _cmp_threshold(db, sheet, p):
    """Nguong so sanh (thang tho) cho 1 khoi CMP: param so o vi tri '2'.
    Tra None neu la CMP dong (nguong lay tu chan vao)."""
    pm = _params(db, sheet).get(p["bid"], {})
    v = _num(pm.get("2"))
    return v


def _compute(net, prod, sem, val, thr=None):
    thr = thr or {}
    p = prod.get(net)
    if not p:
        return val.get(net)                 # net nguon: giu (None neu chua set)
    s = sem.get(p["code"])
    if not s:
        return val.get(net)                 # khoi analog/chua mo hinh: bien
    op = s["op"]
    ins = []
    for (innet, ns) in p["ins"]:
        v = val.get(innet)
        if v is not None and ns and v in (0, 1):
            v = 1 - v
        ins.append(v)
    if op == "CONST":
        return int(s.get("val", 0))
    if op == "PASS":
        return ins[0] if ins else None
    if op == "CMP":
        rel = s.get("rel", ">=")
        t = thr.get(net)                    # nguong tinh (param) hoac None (dong)
        xs = [x for x in ins if x is not None]
        if t is None:                       # CMP dong: so 2 chan vao dau tien
            if len(xs) < 2:
                return None
            a, b = xs[0], xs[1]
        else:
            if not xs:
                return None
            a, b = xs[0], t
        if a is None or b is None:
            return None
        if rel in (">=", "GE"):
            return 1 if a >= b else 0
        if rel in ("<=", "LE"):
            return 1 if a <= b else 0
        if rel in (">", "GT"):
            return 1 if a > b else 0
        if rel in ("<", "LT"):
            return 1 if a < b else 0
        return None
    if op == "NOT":
        return None if (not ins or ins[0] is None) else 1 - ins[0]
    if op == "XOR":
        return None if any(x is None for x in ins) else (sum(ins) % 2)
    if op == "SR":
        S = ins[0] if len(ins) > 0 else None
        Rr = ins[1] if len(ins) > 1 else None
        cur = val.get(net)
        if s.get("priority") == "set":
            return 1 if S == 1 else (0 if Rr == 1 else cur)
        return 0 if Rr == 1 else (1 if S == 1 else cur)
    if op in ("AND", "NAND"):
        r = 0 if any(x == 0 for x in ins) else (None if any(x is None for x in ins) else 1)
        return (1 - r) if (op == "NAND" and r is not None) else r
    if op in ("OR", "NOR"):
        r = 1 if any(x == 1 for x in ins) else (None if any(x is None for x in ins) else 0)
        return (1 - r) if (op == "NOR" and r is not None) else r
    return val.get(net)


def simulate(db, sheet, overrides=None, analog=None, max_iter=80):
    """Tra ve (values{net:0/1 (digital) hoac so (analog)/None}, so_vong_lap).
    overrides = dau vao digital {net:0/1}; analog = dau vao analog {net: so}."""
    overrides = {k: int(v) for k, v in (overrides or {}).items()}
    analog = {k: float(v) for k, v in (analog or {}).items()}
    sem = CT._sem()
    prod = CT._producers(db, sheet)
    aprod = _analog_producers(db, sheet)
    nets = _all_nets(db, sheet) | set(prod) | set(aprod) | set(overrides) | set(analog)
    # nguong cho cac khoi so sanh
    thr = {}
    for onet, p in prod.items():
        if (sem.get(p["code"]) or {}).get("op") == "CMP":
            thr[onet] = _cmp_threshold(db, sheet, p)
    val = {}
    for n in nets:
        if n in overrides:
            val[n] = overrides[n]
        elif n in analog:
            val[n] = analog[n]
        else:
            val[n] = None
    it = 0
    for it in range(1, max_iter + 1):
        changed = False
        for n in nets:
            if n in overrides:
                nv = overrides[n]
            elif n in analog:
                nv = analog[n]
            elif n in aprod:
                nv = _eval_analog(n, aprod, val, db, sheet)
            else:
                nv = _compute(n, prod, sem, val, thr)
            if val.get(n) != nv:
                val[n] = nv; changed = True
        if not changed:
            break
    return val, it


def comparators(db, sheet):
    """Danh sach khoi so sanh tren sheet: (out_net, in_net, rel, threshold).
    De hien nguong len giao dien."""
    sem = CT._sem()
    prod = CT._producers(db, sheet)
    out = []
    for onet, p in prod.items():
        s = sem.get(p["code"]) or {}
        if s.get("op") != "CMP":
            continue
        innet = p["ins"][0][0] if p["ins"] else None
        out.append((onet, innet, s.get("rel", ">="), _cmp_threshold(db, sheet, p)))
    return out


_KIND_CACHE = {}


def _kind_map(db, sheet):
    """net -> 'D' (digital/bit), 'A' (analog/so thuc), '?' (khong ro).
    Uu tien DATATYPE cua tin hieu co ten (CAD_ID), du phong REG_TYPE cua day (CAD_LIN).
    Quy uoc DB: 1=digital, 3=analog(word), 2=dac biet -> coi la analog/so."""
    key = (db, sheet)
    if key in _KIND_CACHE:
        return _KIND_CACHE[key]
    c = D.connect(db).cursor()
    dt = {}
    try:
        for sig, typ in c.execute("SELECT SIGNALID, DATATYPE FROM CAD_ID WHERE ID=?", (sheet,)):
            s = D._clean(sig)
            if s and typ is not None:
                dt[s] = typ
    except Exception:
        pass
    reg = {}
    try:
        for sig, typ in c.execute("SELECT SIGNALID, REG_TYPE FROM CAD_LIN WHERE ID=?", (sheet,)):
            s = D._clean(sig)
            if s and typ is not None and s not in reg:
                reg[s] = typ
    except Exception:
        pass
    km = {}
    for n in (_all_nets(db, sheet) | set(dt) | set(reg)):
        t = dt.get(n, reg.get(n))
        km[n] = "D" if t == 1 else ("A" if t in (2, 3) else "?")
    _KIND_CACHE[key] = km
    return km


def net_kind(db, sheet, net):
    """Phan loai 1 net: 'D' digital / 'A' analog / '?' khong ro."""
    return _kind_map(db, sheet).get(D._clean(net), "?")


# ============ ANALOG TINH (SUB/MUL/DIV/ADD/AVG/ABS/FUNC/PASS) ============
_ASEM = None


def _analog_sem():
    global _ASEM
    if _ASEM is None:
        p = os.path.join(os.path.dirname(__file__), "analog_sem.json")
        try:
            _ASEM = json.load(open(p, encoding="utf-8"))
        except Exception:
            _ASEM = {}
    return _ASEM


_APROD = {}


def _analog_producers(db, sheet):
    """{out_net: {code, op, bid, ins:[(net, pin_name)]}} cho khoi analog co trong analog_sem."""
    key = (db, sheet)
    if key in _APROD:
        return _APROD[key]
    asem = _analog_sem()
    c = D.connect(db).cursor()
    MP = SR._macro_pins()
    binfo = {}
    for bid, sym, code in c.execute(
            "SELECT BLOCK_ID,SYMBOL,MACROCODE FROM CAD_BLOCK WHERE ID=?", (sheet,)):
        binfo[bid] = (sym or "", (code or "").upper())
    pins = defaultdict(list)
    for bid, pn, sig, pt in c.execute(
            "SELECT p.BLOCK_ID,p.PINNO,p.SIGNALID,p.PIN_TYPE FROM CAD_BLOCK_PIN p "
            "JOIN CAD_BLOCK b ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=? ORDER BY p.PINNO", (sheet,)):
        pins[bid].append((pn, D._clean(sig), pt))
    aprod = {}
    for bid, pl in pins.items():
        sym, code = binfo[bid]
        if code not in asem:
            continue
        pdef = (MP.get(sym) or {}).get("pins", {})
        ins = []; outs = []
        for pn, net, pt in pl:
            info = pdef.get(str(pn), {})
            side = info.get("side")
            if side == "out":
                outs.append(net)
            elif side == "in":
                ins.append({"net": net, "name": info.get("name", ""),
                            "ptype": pt, "dx": info.get("dx", 0.0), "dy": info.get("dy", 0.0)})
        op = asem[code]["op"]
        box = (MP.get(sym) or {}).get("box", {})
        sel = None
        if op == "SELECT":
            sel = _resolve_transfer(ins, asem[code].get("name", ""), box)
        for oidx, onet in enumerate(outs):
            if not onet or onet in aprod:
                continue
            # PASS/link nhieu ngo ra: ghep tung ngo ra voi ngo vao cung vi tri
            if op == "PASS" and len(outs) > 1 and oidx < len(ins):
                oins = [ins[oidx]]
            else:
                oins = ins
            rec = {"code": code, "op": op, "bid": bid, "ins": oins}
            if sel:
                rec["sel"] = sel        # (x1_net, x2_net, sw_net)
            aprod[onet] = rec
    _APROD[key] = aprod
    return aprod


def _resolve_transfer(ins, name, box):
    """Xac dinh (X1_net, X2_net, SW_net) cho khoi Transfer.
    SW = chan digital (ptype=1). X1/X2 gan theo canh ghi trong ten '(X1:L /X2:D /SW:U)'
    (L=trai, D=duoi, U=tren); neu ten khong ghi -> mac dinh X1=chan trai nhat."""
    import re
    sw = next((d["net"] for d in ins if d.get("ptype") == 1), None)
    ana = [d for d in ins if d.get("ptype") != 1]
    if len(ana) < 2:
        return (ana[0]["net"] if ana else None, None, sw)
    lx = box.get("lx", 0.0); ly = box.get("ly", 0.0); ry = box.get("ry", 10.0)

    def escore(d, letter):
        if letter == "L":
            return -abs(d.get("dx", 0.0) - lx)
        if letter == "U":
            return -abs(d.get("dy", 0.0) - ly)          # tren: dy ~ 0
        if letter == "D":
            return -abs(d.get("dy", 0.0) - (-ry))       # duoi: dy ~ -ry
        return -1e9

    m1 = re.search(r"X1:([LUD])", name); m2 = re.search(r"X2:([LUD])", name)
    a, b = ana[0], ana[1]
    if m1 and m2:
        e1, e2 = m1.group(1), m2.group(1)
        if escore(a, e1) + escore(b, e2) >= escore(b, e1) + escore(a, e2):
            x1, x2 = a, b
        else:
            x1, x2 = b, a
    else:
        # mac dinh: X1 = chan trai nhat (dx nho nhat, uu tien tren)
        s = sorted(ana, key=lambda d: (d.get("dx", 0.0), -d.get("dy", 0.0)))
        x1, x2 = s[0], s[1]
    return (x1["net"], x2["net"], sw)


def func_points(db, sheet, bid):
    """Bang gay khuc F(x): danh sach (x, y) da sap theo x. Cac cap tu param6 tro di."""
    pm = _params(db, sheet).get(bid, {})
    pts = []
    i = 6
    while True:
        xv = _num(pm.get(str(i))); yv = _num(pm.get(str(i + 1)))
        if xv is None or yv is None:
            break
        pts.append((xv, yv)); i += 2
    pts.sort()
    return pts


def func_name(db, sheet, bid):
    """Ten chuc nang cua khoi F(x) (param5), vd 'RAMP RATE CMP (INC)'."""
    pm = _params(db, sheet).get(bid, {})
    nm = (pm.get("5") or "").strip()
    return nm


def func_blocks(db, sheet):
    """{bid: [(x,y)...]} cho cac khoi F(x) tren sheet."""
    asem = _analog_sem()
    c = D.connect(db).cursor()
    out = {}
    for bid, code in c.execute("SELECT BLOCK_ID,MACROCODE FROM CAD_BLOCK WHERE ID=?", (sheet,)):
        if (asem.get((code or "").upper()) or {}).get("op") == "FUNC":
            pts = func_points(db, sheet, bid)
            if pts:
                out[bid] = pts
    return out


def _func_interp(db, sheet, bid, x):
    """Noi suy tuyen tinh F(x) tu bang gay khuc."""
    pts = func_points(db, sheet, bid)
    if len(pts) < 2:
        return None
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else (y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return None


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _eval_analog(net, aprod, val, db, sheet):
    p = aprod[net]; op = p["op"]; ins = p["ins"]
    xs = [val.get(d["net"]) for d in ins]
    named = {}
    for d in ins:
        if d["name"]:
            named[d["name"]] = val.get(d["net"])

    def allnum(vs):
        return len(vs) > 0 and all(_isnum(v) for v in vs)

    if op in ("SELECT", "MAX", "MIN", "MID"):
        # dau vao analog (ptype 3) va chan chon SW (ptype digital 1)
        ana = [d for d in ins if d.get("ptype") != 1]
        sw = [d for d in ins if d.get("ptype") == 1]
        av = [val.get(d["net"]) for d in ana]
        if op == "SELECT":
            sel = p.get("sel")
            if not sel:
                return av[0] if (av and _isnum(av[0])) else None
            x1n, x2n, swn = sel
            s = val.get(swn) if swn else None
            if s is None:
                return None
            pick = val.get(x1n) if s == 1 else val.get(x2n)   # SW=1->X1, SW=0->X2 (manual 4073)
            return pick if _isnum(pick) else None
        nums = [v for v in av if _isnum(v)]
        if not nums:
            return None
        if op == "MAX":
            return max(nums)
        if op == "MIN":
            return min(nums)
        if op == "MID":
            ss = sorted(nums)
            return ss[len(ss) // 2]
    if op == "CONST":
        pm = _params(db, sheet).get(p["bid"], {})
        v = _num(pm.get("2"))
        if v is None:                       # du phong: param so dau tien
            for k in sorted(pm, key=lambda x: _num(x) or 999):
                v = _num(pm[k])
                if v is not None:
                    break
        return v
    if op == "GAIN":                        # P - Proportional: ra = vao x he so (param2)
        if not xs or not _isnum(xs[0]):
            return None
        pm = _params(db, sheet).get(p["bid"], {})
        g = _num(pm.get("2"))
        return xs[0] * g if g is not None else None
    if op == "PASS":
        return xs[0] if xs and _isnum(xs[0]) else None
    if op == "ABS":
        return abs(xs[0]) if xs and _isnum(xs[0]) else None
    if op == "MUL":
        if not allnum(xs):
            return None
        r = 1.0
        for v in xs:
            r *= v
        return r
    if op == "ADD":
        return float(sum(xs)) if allnum(xs) else None
    if op == "AVG":
        return float(sum(xs)) / len(xs) if allnum(xs) else None
    if op == "SUB":
        a, b = named.get("+"), named.get("-")
        if not (_isnum(a) and _isnum(b)):
            if len(xs) >= 2 and _isnum(xs[0]) and _isnum(xs[1]):
                a, b = xs[0], xs[1]
            else:
                return None
        return a - b
    if op == "DIV":
        a, b = named.get("A"), named.get("B")
        if not (_isnum(a) and _isnum(b)):
            if len(xs) >= 2 and _isnum(xs[0]) and _isnum(xs[1]):
                a, b = xs[0], xs[1]
            else:
                return None
        return None if b == 0 else a / b
    if op == "FUNC":
        x = xs[0] if xs else None
        return _func_interp(db, sheet, p["bid"], x) if _isnum(x) else None
    return None


def input_nets(db, sheet):
    """Cac net LA DAU VAO cua sheet (khong do khoi nao mo hinh sinh ra) -> de nguoi set."""
    prod = CT._producers(db, sheet)
    sem = CT._sem()
    aprod = _analog_producers(db, sheet)
    nets = _all_nets(db, sheet)
    out = []
    for n in nets:
        p = prod.get(n)
        modeled_digital = bool(p and sem.get(p["code"]))
        if modeled_digital or n in aprod:      # da co mo hinh -> khong phai dau vao
            continue
        nm = CT.SG._name_of(db, sheet, n)
        out.append((n, nm or n))
    return out
