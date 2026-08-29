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
_PARAM_OVER = {}          # {bid: {paramno(str): value(str)}} - nguoi dung sua trong app


def set_param_override(bid, params):
    """Ghi de tham so CAI DAT cua 1 khoi (nguoi dung sua trong cua so 'Block parameters').
    Cac gia tri nay se duoc dung khi mo phong sheet (nguong CMP, bang F(x), khoi tram...)."""
    if params:
        _PARAM_OVER[bid] = {str(k): str(v) for k, v in params.items()}
    else:
        _PARAM_OVER.pop(bid, None)
    _PARAMS.clear()       # bo cache de lan tinh sau dung gia tri moi


def param_overrides():
    return _PARAM_OVER


def clear_param_overrides():
    _PARAM_OVER.clear()
    _PARAMS.clear()


def _params(db, sheet):
    """{bid: {paramno(str): value(str)}} cho cac block tren sheet (da ap gia tri
    nguoi dung ghi de, neu co)."""
    key = (db, sheet)
    if key in _PARAMS:
        return _PARAMS[key]
    c = D.connect(db).cursor()
    pm = {}
    for bid, pno, pv in c.execute(
            "SELECT bp.BLOCK_ID, bp.PARAMNO, bp.PARAMVALUE FROM CAD_BLOCK_PARAM bp "
            "JOIN CAD_BLOCK b ON bp.BLOCK_ID=b.BLOCK_ID WHERE b.ID=?", (sheet,)):
        pm.setdefault(bid, {})[str(pno)] = pv
    for bid, ov in _PARAM_OVER.items():
        if bid in pm or ov:
            pm.setdefault(bid, {}).update(ov)
    _PARAMS[key] = pm
    return pm


def _cmp_threshold(db, sheet, p):
    """Nguong so sanh (thang tho) cho 1 khoi CMP: param so o vi tri '2'.
    Tra None neu la CMP dong (nguong lay tu chan vao)."""
    pm = _params(db, sheet).get(p["bid"], {})
    v = _num(pm.get("2"))
    return v


def timer_secs(db, sheet, sem_entry, bid):
    """Thoi gian cai dat cua 1 khoi delay/xung, quy ve GIAY. None khi khong doc duoc.

    Do that tren 18 file DB du an: moi khoi DI/DIL/DT/PO/TDWO deu CO thoi gian rieng
    trong CAD_BLOCK_PARAM, chi la truoc day khong ai doc toi. Vi tri PARAMNO khac nhau
    theo loai khoi (ho 40xx de o param 2 vi param 1 la ten tag; ho 20xx cho HCNT de o
    param 1) nen lay tu 'tpar' trong logic_sem.json thay vi doan.
    Don vi: DI/DT/PO/TDWO va ho (H) tinh bang giay - trong DB co ca gia tri le (2,5s;
    0,07s) nen phai doc so thuc, khong lam tron. Rieng DIL ("Delay Initiation (L)",
    Long) tinh bang PHUT: hang cho no tran 32767 trong khi DI chi 1500, va gia tri thuc
    te cai toi 2880 = 2 ngay.
    Tra None khi khoi thuoc bien the "T:input" (thoi gian den tu chan vao ten "T",
    khong co trong tham so) - noi goi phai tu doc gia tri dang chay tren day do."""
    tp = sem_entry.get("tpar")
    if not tp:
        return None
    v = _num(_params(db, sheet).get(bid, {}).get(tp))
    if v is None:
        return None
    return v * 60.0 if sem_entry.get("tunit") == "min" else v


def _const_value(db, sheet, p):
    """Gia tri THAT cua 1 khoi hang so digital, lay tu param '2' cua chinh khoi do.
    Khoi DSW (D-CONST, macrocode 4018) la cong tac cai bang tay: cung mot ma khoi
    nhung moi cai dat 0 hoac 1 rieng - tren ban ve so nay in ngay trong o khoi.
    Do that tren 18 file DB du an: 479 khoi 4018, trong do 221 khoi cai '1'; neu
    lay 'val' co dinh trong logic_sem.json thi ca 221 khoi nay mo phong ra 0,
    nguoc voi con so hien tren ban ve. Cac khoi hang so co dinh (EVO 40A4 = 1,
    EVF 40A5 = 0) khong co param nao -> tra None de dung lai 'val' cua bang.
    Duong analog da lam dung cach nay tu truoc (xem op CONST trong _eval_analog)."""
    pm = _params(db, sheet).get(p["bid"], {})
    return _num(pm.get("2"))


def _compute(net, prod, sem, val, thr=None, cst=None):
    thr = thr or {}
    cst = cst or {}
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
        v = cst.get(net)                    # cai dat rieng cua khoi (DSW)
        if v is None:
            v = s.get("val", 0)             # hang so co dinh theo loai khoi
        return 1 if v else 0
    if op == "PASS":
        return ins[0] if ins else None
    if op == "PULSE":
        # Xung MOT NHAT (PO/TDWO, tuc SS1/SS2 theo ten tieng Nhat cua hang trong
        # DEF/SR21E/macro_master.csv). Sach macro: "A time-limit pulse for a specified
        # time is output starting when input changes from OFF to ON" - dau ra chi len
        # trong T giay ke tu SUON LEN, khong bam theo dau vao. Vay o trang thai XAC LAP
        # (dau vao giu nguyen) xung da tat -> luon 0, khong phu thuoc dau vao. Mo hinh
        # PASS cu tra 1 khi dau vao dang 1, nguoc voi thuc te tren 4.008 khoi.
        # Muon thay chinh cai xung thi dung cua so mo phong DONG (core/sheet_dyn.py).
        # PG (4019) la mach dao dong co cong: khong co trang thai xac lap nao ca, tra
        # None de hien "chua biet" thay vi bia ra 0 hay 1.
        return None if s.get("tmr") == "PG" else 0
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
    # Tu day tro xuong la cac phep DIGITAL: tin hieu chua xac dinh coi nhu 0 (dong bo
    # voi cach hien thi tren so do - digital chi co 0 hoac 1, khong con trang thai '?')
    ins = [0 if x is None else x for x in ins]
    if op == "NOT":
        return 1 - ins[0] if ins else 1
    if op == "XOR":
        return sum(ins) % 2
    if op == "MAJ":
        # 2-trong-3 (400E). Nguon chuan cua hang DEF/MCR/MacroDef.db: MACROABBR
        # '2OUT3', ten '<|2 - Two Out of Three', 3 chan vao / 1 chan ra / 0 tham so.
        # La mach bau da so cua he bao ve: Du k tren tong so dau vao len 1, khong
        # phai DUNG k cai (3/3 ma khong tac dong thi con gi la bao ve nua).
        return 1 if sum(ins) >= s.get("k", 2) else 0
    if op == "SELECT":
        # Cong tac chuyen mach tin hieu so: SW=1 -> Y=X1, SW=0 -> Y=X2.
        # Nguon: manual macro trang 117 muc "Transfer (Digital Switch) 40D5H" - bang
        # chan ly ghi ro SW=ON thi Y=X1, SW=OFF thi Y=X2; toa do chu trong ban ve
        # symbol dat SW o goc tren-trai, X1 ben trai, X2 phia duoi, Y ben phai.
        # Vi tri 3 chan vao lay tu logic_sem vi hai loai khoi xep chan khac nhau:
        # do trong DEF/MCR/MacroDef.db cua hang thi 1030 co SW o chan 3 con 40D5
        # co SW o chan 1 (40D5 trung khit hinh hoc chan voi 4073, khoi ma ten macro
        # cua hang ghi thang quy uoc "(X1:L /X2:D /SW:U)").
        if len(ins) < 3:
            return val.get(net)
        return ins[s["x1"]] if ins[s["sw"]] else ins[s["x2"]]
    if op == "SR":
        S = ins[0] if len(ins) > 0 else None
        Rr = ins[1] if len(ins) > 1 else None
        cur = val.get(net)
        if cur is None:
            cur = 0                      # chot chua xac dinh -> coi nhu 0
        if s.get("priority") == "set":
            return 1 if S == 1 else (0 if Rr == 1 else cur)
        return 0 if Rr == 1 else (1 if S == 1 else cur)
    if op in ("AND", "NAND"):
        r = 0 if any(x == 0 for x in ins) else 1
        return (1 - r) if op == "NAND" else r
    if op in ("OR", "NOR"):
        r = 1 if any(x == 1 for x in ins) else 0
        return (1 - r) if op == "NOR" else r
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
    # cai dat rieng cua tung khoi: nguong so sanh (CMP) va gia tri cong tac (CONST)
    thr = {}
    cst = {}
    for onet, p in prod.items():
        op0 = (sem.get(p["code"]) or {}).get("op")
        if op0 == "CMP":
            thr[onet] = _cmp_threshold(db, sheet, p)
        elif op0 == "CONST":
            cst[onet] = _const_value(db, sheet, p)
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
                nv = _compute(n, prod, sem, val, thr, cst)
            if val.get(n) != nv:
                val[n] = nv; changed = True
        if not changed:
            break
    return val, it


def cmp_blocks(db, sheet):
    """{out_net: {bid, code, rel, thr, reset, unit, innet}} cho moi khoi so sanh nguong.

    Day du hon comparators(): kem DON VI ky thuat (param 4) va DIEM TRO VE (param 3).
    Ten macro cua hang noi ro y nghia 2 tham so nay - 404E la "H/ - Signal Monitor
    (High) (S & R:para)": param 2 la S (Set, nguong tac dong), param 3 la R (Reset,
    nguong nha) - la mot TRI SO TUYET DOI cung don vi, khong phai do rong vung tre va
    khong phai thoi gian. Kiem lai tren du an: 1322 khoi co R khac S, va CA 1322 deu
    dung chieu (loai H/ co R < S, loai /L co R > S), khong mot ngoai le."""
    sem = CT._sem()
    pm_all = _params(db, sheet)
    out = {}
    for onet, p in CT._producers(db, sheet).items():
        s = sem.get(p["code"]) or {}
        if s.get("op") != "CMP":
            continue
        pm = pm_all.get(p["bid"], {})
        out[onet] = {"bid": p["bid"], "code": p["code"], "rel": s.get("rel", ">="),
                     "thr": _num(pm.get("2")), "reset": _num(pm.get("3")),
                     "unit": (pm.get("4") or "").strip(),
                     "innet": p["ins"][0][0] if p["ins"] else None}
    return out


def comparators(db, sheet):
    """Danh sach khoi so sanh tren sheet: (out_net, in_net, rel, threshold).
    De hien nguong len giao dien."""
    return [(onet, c["innet"], c["rel"], c["thr"])
            for onet, c in cmp_blocks(db, sheet).items()]


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
        if asem[code].get("sig") == "left":
            # Loc tre F(t) va gioi han toc do RL o BAI TOAN TINH: on dinh roi thi ra = vao.
            # Loc tre chi lam CHAM, khong doi tri so cuoi cung; gioi han toc do chi han
            # TOC DO doi, thoi doi la no bam dung dau vao. Chay dong (sheet_dyn nhanh
            # kind 'L'/'R') van dung mo hinh dong that: gia tri do vao simulate() bang
            # duong ghi de analog, ma ghi de thang lop tinh nay nen khong bi de len.
            ins = _chan_tin_hieu(ins)
        for oidx, onet in enumerate(outs):
            if not onet or onet in aprod:
                continue
            # PASS/link nhieu ngo ra: ghep tung ngo ra voi ngo vao cung vi tri
            if op == "PASS" and len(outs) > 1 and oidx < len(ins):
                oins = [ins[oidx]]
            else:
                oins = ins
            rec = {"code": code, "op": op, "bid": bid, "ins": oins, "oidx": oidx}
            if sel:
                rec["sel"] = sel        # (x1_net, x2_net, sw_net)
            if op == "SIGNSUM":
                rec["signs"] = asem[code].get("signs", [])
            aprod[onet] = rec
    _APROD[key] = aprod
    return aprod


def _chan_tin_hieu(ins):
    """Chan mang DONG TIN HIEU CHINH cua khoi loc tre F(t) / gioi han toc do RL.

    Hai ho khoi nay con chan khac: SW (cho phep hay bo qua tac dung) va chan nhan hang
    so thoi gian T / toc do R tu ben ngoai. Lay nham chan thi ngo ra thanh mot tri so
    vo nghia, nen chon y het cach bo giai DONG dang dung (core/sheet_dyn.py, nhanh
    kind 'L' va 'R'): bo chan so (PIN_TYPE=1 la SW) va chan ten 'I' (toc do), con lai
    lay chan TRAI NHAT. Do tren 1.134 khoi cua du an: sau khi loc khong khoi nao con
    hai chan cung do trai, tuc quy tac luon chi ra dung mot chan."""
    ana = [d for d in ins if d.get("ptype") != 1 and d.get("name") != "I"]
    if not ana:
        return ins
    return [min(ana, key=lambda d: d.get("dx", 0.0))]


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
    """Bang gay khuc F(x): danh sach (x, y) da sap theo x. Cac cap tu param6 tro di.

    Bang LUON co 15 o (param 6..35) nhung so diem THAT SU dung nam o param 2 - o thua
    giu lai rac cua lan sua truoc. Khong cat thi rac lot vao duong cong: khoi 3360001
    (03 BSM_A sheet 336) khai 8 diem, cac o thua con (0,0) nen sau khi sap xep chung
    nhay len DAU bang, tai x=0 tra 0 thay vi 1.3. Do tren ca 4322 khoi F(x) cua du an:
    3322 khoi khai it hon so o doc duoc, va 382 khoi (9%) doi han ket qua noi suy -
    khoi 3120009 tai x=1000 truoc tra 9.5, dung ra la 0.95."""
    pm = _params(db, sheet).get(bid, {})
    pts = []
    i = 6
    while True:
        xv = _num(pm.get(str(i))); yv = _num(pm.get(str(i + 1)))
        if xv is None or yv is None:
            break
        pts.append((xv, yv)); i += 2
    n = _num(pm.get("2"))
    if n is not None and 1 <= int(n) < len(pts):
        pts = pts[:int(n)]
    pts.sort()
    return pts


def func_name(db, sheet, bid):
    """Ten chuc nang cua khoi F(x) (param5), vd 'RAMP RATE CMP (INC)'."""
    pm = _params(db, sheet).get(bid, {})
    nm = (pm.get("5") or "").strip()
    return nm


def func_info(db, sheet, bid):
    """Mo ta day du 1 khoi F(x) de hien len tai lieu: nhan tag (param1), ten chuc nang
    (param5), don vi truc X/Y (param3/param4) va bang gay khuc. Nguong dong cua nhieu
    mach bao ve la 1 duong cong nhu the nay chu khong phai 1 con so."""
    pm = _params(db, sheet).get(bid, {})
    return {"bid": bid, "tag": (pm.get("1") or "").strip(),
            "name": (pm.get("5") or "").strip(), "xunit": (pm.get("3") or "").strip(),
            "yunit": (pm.get("4") or "").strip(), "pts": func_points(db, sheet, bid)}


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
                s = 0                       # cong tac chua xac dinh -> coi nhu 0 (khop hien thi)
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
    if op == "SIGNSUM":
        # tong co dau co dinh theo tung chan vao (vd Summing 4in:++--)
        if not allnum(xs):
            return None
        signs = p.get("signs") or []
        total = 0.0
        for i, v in enumerate(xs):
            s = signs[i] if i < len(signs) else "+"
            total += -v if s == "-" else v
        return total
    if op in ("CLAMPHI", "CLAMPLO"):
        # Limiter co canh bao/so sanh (vd 210F/2110/410D/410F): ins=[X, L]
        # oidx=0 -> ngo ra gia tri da gioi han (Y); oidx=1 -> co so sanh (D, dang bi kep hay khong)
        if len(xs) < 2 or not allnum(xs[:2]):
            return None
        x, lim = xs[0], xs[1]
        oidx = p.get("oidx", 0)
        if op == "CLAMPHI":
            if oidx == 0:
                return min(x, lim)
            return 1.0 if x >= lim else 0.0
        else:
            if oidx == 0:
                return max(x, lim)
            return 1.0 if x <= lim else 0.0
    if op == "MULG":
        # nhan 2 dau vao roi nhan them he so co dinh (param vi tri "2", giong quy uoc GAIN)
        if len(xs) < 2 or not allnum(xs[:2]):
            return None
        pm = _params(db, sheet).get(p["bid"], {})
        g = _num(pm.get("2"))
        if g is None:
            g = 1.0
        return xs[0] * xs[1] * g
    if op == "WSUM":
        # D-SUM (405F/4060/4061/4062/4063): Y = sum(Gi*Xi). param1=nhan ID,
        # param2..param(n+1)=G1..Gn theo dung thu tu chan vao (PINNO tang dan).
        # Mac dinh Gi=0 neu chua dat (dung nhu default trong macro_param.csv).
        if not allnum(xs):
            return None
        pm = _params(db, sheet).get(p["bid"], {})
        total = 0.0
        for i, v in enumerate(xs):
            g = _num(pm.get(str(i + 2)))
            if g is None:
                g = 0.0
            total += g * v
        return total
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
