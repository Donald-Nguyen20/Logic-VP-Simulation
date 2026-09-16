# -*- coding: utf-8 -*-
"""TRUONG HOP dau vao cua mot tin hieu + TOAN BO LOGIC TREN TRANG.

Cay truy nguoc trong ai_explain chi ghi "Y <= TRAN-BMP1 of: A, B, C". Doc xong
khong biet chan nao la CONG TAC, cung khong biet moi the cong tac thi Y bam theo
cai nao - ma do moi la thu nguoi doc ban ve can. Module nay tra ra hai thu con
thieu do:

  - cases()       : tung TRUONG HOP dau vao cua khoi sinh ra tin hieu
  - sheet_logic() : toan bo khoi tren trang theo thu tu chay = noi dung logic
  - one_line()    : phep tinh cua khoi analog, viet thang thay vi "through DIF3"

Chi doc DB, khong sua gi."""
from __future__ import annotations
from collections import defaultdict
from . import cond_tree as CT
from . import signal_graph as SG
from . import sheet_sim as SS
from . import sheet_render as SR
from . import dbreader as D

TERM = "E0B1"
_MAX_BLOCKS = 60     # trang lon: cat bot de ngu canh khong phinh


def _nm(db, sheet, net):
    """Ten that cua tin hieu; khong co ten thi tra lai chinh nhan noi bo (a0, b7...)."""
    if not net:
        return "?"
    return SG._name_of(db, sheet, net) or net


def _ops(code):
    """(op_analog, sem_logic) cua ma khoi. Mot khoi chi nam o mot trong hai bang."""
    a = (SS._analog_sem().get(code) or {})
    s = (CT._sem().get(code) or {})
    return a.get("op") or s.get("op"), s, a


def _select_roles(db, sheet, net, prod, s):
    """(x1, x2, sw) cua mot cong tac chuyen mach, hoac None neu khong doc duoc.

    Vai tro chan lay lai dung bo giai da dung cho mo phong (sheet_sim), de giai
    thich va mo phong khong bao gio noi hai dieu khac nhau ve cung mot khoi."""
    rec = SS._analog_producers(db, sheet).get(net)
    if rec and rec.get("sel"):
        x1, x2, sw = rec["sel"]
    elif s and len(prod["ins"]) > max(s.get("sw", 0), s.get("x1", 0), s.get("x2", 0)):
        ins = prod["ins"]
        x1, x2, sw = (ins[s["x1"]][0], ins[s["x2"]][0], ins[s["sw"]][0])
    else:
        return None
    return (x1, x2, sw) if sw and (x1 or x2) else None


def _select_cases(db, sheet, net, prod, s):
    """Cong tac chuyen mach: SW=1 -> Y bam X1, SW=0 -> Y bam X2."""
    r = _select_roles(db, sheet, net, prod, s)
    if not r:
        return []
    x1, x2, sw = r
    n = lambda v: _nm(db, sheet, v)
    return ["CASE  %s = 1  ->  %s follows %s" % (n(sw), n(net), n(x1)),
            "CASE  %s = 0  ->  %s follows %s" % (n(sw), n(net), n(x2))]


def _minmax_cases(db, sheet, net, prod, op):
    """Chon lon/nho: khong co cong tac, nhung VAN la re nhanh - dau vao nao dang
    lon (nho) nhat thi dau vao do cam lai, cac dau vao con lai het tac dung."""
    ins = [v for (v, _ns) in prod["ins"] if v]
    if len(ins) < 2:
        return []
    n = lambda v: _nm(db, sheet, v)
    w = "higher" if op == "MAX" else "lower"
    out = []
    for v in ins:
        rest = [n(x) for x in ins if x != v]
        out.append("CASE  %s is the %s  ->  %s follows %s, and %s has no effect"
                   % (n(v), w, _nm(db, sheet, net), n(v), " / ".join(rest)))
    return out


def _sr_cases(db, sheet, net, prod, s):
    """Khoi chot S/R: ba truong hop, ke ca truong hop hai chan cung len."""
    ins = [v for (v, _ns) in prod["ins"]]
    si, ri = s.get("set", 0), s.get("reset", 1)
    if len(ins) <= max(si, ri):
        return []
    n = lambda v: _nm(db, sheet, v)
    S, R = n(ins[si]), n(ins[ri])
    pr = s.get("priority", "reset")
    win = R if pr == "reset" else S
    y = _nm(db, sheet, net)
    return ["CASE  %s = 1  ->  %s latches up and STAYS up on its own" % (S, y),
            "CASE  %s = 1  ->  %s drops and stays down until set again" % (R, y),
            "CASE  %s = 1 and %s = 1 together  ->  %s wins (%s priority)"
            % (S, R, win, pr)]


def _sub_cases(db, sheet, net, prod):
    """Khoi tru: noi ro ai tru ai. Day la cho de doc nguoc dau nhat tren ban ve."""
    ins = [v for (v, _ns) in prod["ins"] if v]
    if len(ins) < 2:
        return []
    n = lambda v: _nm(db, sheet, v)
    return ["MEANING  %s = %s minus %s, so it is positive while %s is the larger"
            % (_nm(db, sheet, net), n(ins[0]), n(ins[1]), n(ins[0]))]


def cases(db, sheet, net, prod):
    """Cac TRUONG HOP dau vao cua khoi dang sinh ra `net`.

    Chi cac khoi RE NHANH moi co truong hop: cong tac chuyen mach, chon lon/nho,
    chot S/R, va khoi tru (khong phai re nhanh nhung de hieu nguoc dau). Khoi
    khac tra [] - cay truy nguoc san co da du de doc."""
    code = (prod.get("code") or "").upper()
    op, s, _a = _ops(code)
    try:
        if op == "SELECT":
            return _select_cases(db, sheet, net, prod, s)
        if op in ("MAX", "MIN"):
            return _minmax_cases(db, sheet, net, prod, op)
        if op == "SR":
            return _sr_cases(db, sheet, net, prod, s)
        if op == "SUB":
            return _sub_cases(db, sheet, net, prod)
    except Exception:
        return []
    return []


def _nm2(db, sheet, net):
    """Nhu _nm nhung nhan noi bo (a0, b7) thi goi theo KHOI sinh ra no.

    Dong cong thuc mot dong nam o dau ngu canh, doc truoc ca so do; de nguyen
    "b0" thi nguoi doc chua co gi de doi chieu."""
    nm = SG._name_of(db, sheet, net)
    if nm:
        return nm
    p = CT._producers(db, sheet).get(net)
    if not p:
        return net
    code = (p.get("code") or "").upper()
    if _ops(code)[0] == "CONST":                 # hang so: gia tri moi la thu can biet
        v = _const_val(db, sheet, p.get("bid"))
        if v:
            return v
    return "output of %s" % D.macro_name(code, p.get("sym"))


def _const_val(db, sheet, bid):
    """Tri dat cua khoi hang so, kem don vi neu co ("102 %")."""
    pm = SS._params(db, sheet).get(bid) or {}
    num = unit = ""
    for _k, v in sorted(pm.items()):
        v = str(v).strip()
        try:
            float(v)
            if not num:
                num = v
        except ValueError:
            if num and not unit and len(v) <= 8:
                unit = v
    return ("%s %s" % (num, unit)).strip() if num else ""


_ARITH = {"ADD": " + ", "SUB": " - ", "MUL": " x ", "DIV": " / "}
_PICK = {"MAX": "the higher of", "MIN": "the lower of", "MID": "the middle of"}


def one_line(db, sheet, net, prod):
    """Cong thuc MOT DONG cua khoi tinh toan analog.

    cond_tree.formula chi biet bang logic so; gap khoi analog no tra ve "through
    DIF3" - doc xong khong biet gi them. Ham nay viet thang phep tinh ra."""
    code = (prod.get("code") or "").upper()
    op, _s, _a = _ops(code)
    ins = [v for (v, _n) in prod.get("ins") or [] if v]
    n = lambda v: _nm2(db, sheet, v)
    if not ins:
        return ""
    if op in _ARITH and len(ins) >= 2:
        return _ARITH[op].join(n(v) for v in ins[:4])
    if op in _PICK and len(ins) >= 2:
        return "%s %s" % (_PICK[op], " and ".join(n(v) for v in ins[:4]))
    if op == "AVG" and len(ins) >= 2:
        return "average of %s" % ", ".join(n(v) for v in ins[:4])
    if op == "ABS":
        return "size of %s regardless of sign" % n(ins[0])
    if op == "SELECT":
        r = _select_roles(db, sheet, net, prod, _s)
        if r:
            return "%s or %s, whichever %s selects" % (n(r[0]), n(r[1]), n(r[2]))
    return ""


def _blocks_on(db, sheet):
    """[(exeorder, bid, sym, code, in_nets, out_nets)] theo dung THU TU CHAY.

    Bo khoi dau cuc E0B1 (chi la diem noi day, khong phai khoi logic)."""
    c = D.connect(db).cursor()
    MP = SR._macro_pins()
    info = {}
    for bid, sym, code, eo in c.execute(
            "SELECT BLOCK_ID,SYMBOL,MACROCODE,EXEORDER FROM CAD_BLOCK WHERE ID=?", (sheet,)):
        info[bid] = ((sym or ""), (code or "").upper(), eo)
    pins = defaultdict(list)
    for bid, pn, sig in c.execute(
            "SELECT p.BLOCK_ID,p.PINNO,p.SIGNALID FROM CAD_BLOCK_PIN p "
            "JOIN CAD_BLOCK b ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=? ORDER BY p.PINNO",
            (sheet,)):
        pins[bid].append((pn, D._clean(sig)))
    rows = []
    for bid, pl in pins.items():
        sym, code, eo = info.get(bid, ("", "", -1))
        if code == TERM or not code:
            continue
        mdef = MP.get(sym)
        n = len(pl)
        ins, outs = [], []
        for idx, (pn, net) in enumerate(pl):
            (outs if SG._pin_out(mdef, pn, idx, n) else ins).append(net)
        rows.append((eo, bid, sym, code, ins, outs))
    rows.sort(key=lambda r: (r[0] if r[0] is not None and r[0] >= 0 else 9999, r[1]))
    return rows


def sheet_logic(db, sheet, params=None):
    """Noi dung logic CUA CA TRANG, theo thu tu chay.

    Cay truy nguoc chi di theo mot nhanh nen bo sot cac khoi ben canh cung gop
    vao tin hieu. Phan nay ke het, moi khoi mot cum: ten khoi + tri dat rieng +
    day vao/ra + cac truong hop neu la khoi re nhanh.

    `params` la ham (bid) -> chuoi tri dat; truyen tu ngoai vao de module nay
    khong phai goi nguoc ai_explain (vong import)."""
    prod = CT._producers(db, sheet)
    out = []
    rows = _blocks_on(db, sheet)
    for (eo, bid, sym, code, ins, outs) in rows[:_MAX_BLOCKS]:
        blk = D.macro_name(code, sym)
        pv = params(bid) if params else ""
        out.append("  [%s] %s%s" % (("%02d" % eo) if eo is not None and eo >= 0 else "--",
                                    blk, ("   [settings: %s]" % pv) if pv else ""))
        iv = ", ".join(_nm(db, sheet, v) for v in ins if v) or "-"
        ov = ", ".join(_nm(db, sheet, v) for v in outs if v) or "-"
        out.append("        in: %s   ->  out: %s" % (iv, ov))
        for onet in outs:
            pr = prod.get(onet)
            if not pr or pr.get("bid") != bid:
                continue
            for ln in cases(db, sheet, onet, pr):
                out.append("        " + ln)
    if len(rows) > _MAX_BLOCKS:
        out.append("  ... (%d more blocks on this drawing)" % (len(rows) - _MAX_BLOCKS))
    return out
