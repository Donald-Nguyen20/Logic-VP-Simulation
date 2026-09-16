# -*- coding: utf-8 -*-
"""Tai lieu "Cach hoat dong" cua tram van hanh (MV, SV...) DOC TU THAN DEF GOC.

Manual Toshiba chi co vai cau cho moi tram. Tai lieu o day viet lai tu chinh than lenh
trong TAG_MCR.DEF: che do Auto/Manual, nut tren man hinh van hanh, bao dong, gioi han...

Moi tram 1 file core/tag_docs/<ma>.json, viet tay song ngu {"en", "vi"} - KHONG goi AI.
Moi y quan trong co KICH BAN mo phong kem "checks" chay tren DefSim (dung bo may chay
ban ve). tests/test_tag_docs.py chay lai het: than lenh hay bo mo phong doi ma tai lieu
noi sai la kiem thu bao do ngay.

Kich ban (scenario):
  dt, until            : buoc quet va thoi gian chay (giay)
  set                  : gia tri dat tu dau {tin_hieu: gia tri}
  events               : [{"t": giay, "set": {...}} | {"t": giay, "pulse": {...}}]
                         pulse = dat 1 vong quet roi tra ve 0 (nut bam)
  show                 : cac hang ve tren bieu do [{"sig", "label", "kind": bit|num}]
  checks               : [{"t": giay hoac [tu, den], "sig", "eq"|"ge"|"le": so}]
Ten tin hieu: "in:<chan vao>", "out:<chan ra>", "prm:<PARAMNO>" (chi dat),
"ops:<OPS_IN../OS_..>" (nut/lenh tu tram van hanh), "st:<thanh ghi noi/OPS_OUT../OPS_CND(n)>".
Chan vao va chan ra co the trung ten (820E: "Auto", "MV") nen luon ghi tien to.
"""
from __future__ import annotations
import json
import os
import re

from core import def_sim as DS
from core import macro_def as MD
from core.block_params import param_meta
from core.help_i18n import EN, lang

_DIR = os.path.join(os.path.dirname(__file__), "tag_docs")
_CACHE = {}
_EPS = 1e-6
_TOK_HMI = re.compile(r"\b(OPS_IN\d+|OPS_OUT\d+|OPS_CND\(\d+\)|OS_[A-Z]+)")


def codes():
    """Cac ma tram da co tai lieu, sap xep."""
    try:
        names = os.listdir(_DIR)
    except OSError:
        return []
    return sorted(n[:-5].upper() for n in names if n.lower().endswith(".json"))


def doc_for(code):
    """Tai lieu cua 1 ma tram (dict) hoac None. File hong -> None, khong lam do cua so."""
    code = (code or "").upper()
    if code not in _CACHE:
        try:
            with open(os.path.join(_DIR, code + ".json"), encoding="utf-8") as f:
                data = json.load(f)
            _CACHE[code] = data if isinstance(data, dict) else None
        except (OSError, ValueError):
            _CACHE[code] = None
    return _CACHE[code]


def pick(pair, code=None):
    """Chu theo ngon ngu dang chon tu cap {"en","vi"}. Thieu ban dich thi lay tieng Anh."""
    if not isinstance(pair, dict):
        return pair or ""
    return pair.get(code or lang()) or pair.get(EN) or ""


# ---------------------------------------------------------------- mo phong
def _dat(s, sig, v):
    kind, _, name = sig.partition(":")
    if kind == "in":
        s.set_input(name, v)
    elif kind == "prm":
        s.set_param(int(name), v)
    elif kind == "ops":
        s.ops[name] = float(v)
    else:
        raise ValueError("cannot set signal %r (use in:, prm: or ops:)" % sig)


def _doc(s, out, sig):
    kind, _, name = sig.partition(":")
    if kind == "in":
        return float(s.inputs.get(name, 0.0))
    if kind == "out":
        return float(out.get(name, 0.0))
    if kind == "ops":
        return float(s.ops.get(name, 0.0))
    if kind == "st":
        return float(s.state.get(name, 0.0))
    raise ValueError("cannot read signal %r (use in:, out:, ops: or st:)" % sig)


def _mac_dinh(s, code):
    """Nap gia tri MAC DINH cua hang cho moi tham so kieu so - giong khoi moi dat."""
    for no, m in param_meta().get(code, {}).items():
        if m.get("kind") != "0":
            continue
        try:
            s.set_param(no, float(m.get("default")))
        except (TypeError, ValueError):
            continue


def _signals(sc):
    sigs = [r["sig"] for r in sc.get("show", [])]
    sigs += [c["sig"] for c in sc.get("checks", [])]
    return list(dict.fromkeys(sigs))


def run_scenario(code, sc):
    """Chay 1 kich ban. Tra {"t": [giay], "v": {tin_hieu: [gia tri sau moi vong quet]}}.

    Su kien o thoi diem t duoc dat TRUOC vong quet t, gia tri ghi lai la SAU vong do."""
    code = (code or "").upper()
    dt = float(sc.get("dt", 0.5))
    n = int(round(float(sc["until"]) / dt)) + 1
    s = DS.DefSim(code, dt=dt)
    _mac_dinh(s, code)
    for sig, v in (sc.get("set") or {}).items():
        _dat(s, sig, v)
    events = sorted(sc.get("events", []), key=lambda e: float(e["t"]))
    sigs = _signals(sc)
    ts, vals, xung = [], {k: [] for k in sigs}, {}
    j = 0
    for k in range(n):
        t = round(k * dt, 9)
        for sig in xung:                      # nut bam o vong truoc: nha ra
            _dat(s, sig, 0.0)
        xung = {}
        while j < len(events) and float(events[j]["t"]) <= t + _EPS:
            for sig, v in (events[j].get("set") or {}).items():
                _dat(s, sig, v)
            for sig, v in (events[j].get("pulse") or {}).items():
                _dat(s, sig, v)
                xung[sig] = True
            j += 1
        out = s.step()
        ts.append(t)
        for sig in sigs:
            vals[sig].append(_doc(s, out, sig))
    return {"t": ts, "v": vals}


def _chon_mau(res, t):
    """Chi so cac mau trong khoang t (so hoac [tu, den])."""
    lo, hi = (t, t) if not isinstance(t, (list, tuple)) else (t[0], t[1])
    return [i for i, x in enumerate(res["t"]) if lo - _EPS <= x <= hi + _EPS]


def check_scenario(code, sc, res=None):
    """Danh sach loi (chuoi) cua cac "checks" trong kich ban. Rong = tai lieu noi dung."""
    res = res or run_scenario(code, sc)
    loi = []
    for c in sc.get("checks", []):
        idx = _chon_mau(res, c["t"])
        if not idx:
            loi.append("%s: no sample at t=%s" % (sc.get("id"), c["t"]))
            continue
        for i in idx:
            v = res["v"][c["sig"]][i]
            ok = True
            if "eq" in c:
                ok = abs(v - float(c["eq"])) <= 1e-6 * max(1.0, abs(float(c["eq"])))
            if "ge" in c:
                ok = ok and v >= float(c["ge"]) - _EPS
            if "le" in c:
                ok = ok and v <= float(c["le"]) + _EPS
            if not ok:
                loi.append("%s: %s at t=%g is %g, expected %s" % (
                    sc.get("id"), c["sig"], res["t"][i], v,
                    {k: c[k] for k in ("eq", "ge", "le") if k in c}))
                break
    return loi


# ---------------------------------------------------------------- do phu
def hmi_tokens(code):
    """Cac tin hieu tram van hanh (OPS_IN/OPS_OUT/OPS_CND/OS_) ma than lenh THAT dung."""
    sym = MD.symbol_of(code)
    body = MD.body_of(sym) if sym else []
    return sorted({m for ln in body for m in _TOK_HMI.findall(ln)})


def coverage(code):
    """Nhung gi than lenh / bang chan / bang tham so co ma tai lieu CHUA noi toi."""
    code = (code or "").upper()
    d = doc_for(code) or {}
    miss = []
    pins = MD.pins_of(code, khoa=False)
    so_chan = sorted({n for side in pins.values() for n in side})
    miss += ["pin %d" % n for n in so_chan if str(n) not in d.get("pins", {})]
    miss += ["param P%d" % n for n in sorted(param_meta().get(code, {}))
             if str(n) not in d.get("params", {})]
    co = {h.get("tok") for h in d.get("hmi", [])}
    miss += ["hmi %s" % t for t in hmi_tokens(code) if t not in co]
    return miss
