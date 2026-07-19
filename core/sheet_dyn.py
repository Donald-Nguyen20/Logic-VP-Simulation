# -*- coding: utf-8 -*-
"""
Mo phong DONG cho sheet: chay theo buoc thoi gian dt. Moi buoc:
 1) Giai TINH (sheet_sim) voi dau ra cac khoi dong lam nguon co dinh.
 2) Tien trang thai cac khoi dong (tich phan) mot buoc dt.
Lap nsteps buoc -> gia tri hoi tu. Chi doc DB.

v1: mo hinh khoi TICH PHAN (I - Integral with Limit). Cac khoi dong khac
(PID, lead/lag, station) se bo sung sau.
"""
from __future__ import annotations
from collections import defaultdict
from math import exp as _exp
from . import dbreader as D
from . import sheet_render as SR
from . import sheet_sim as SS

# khoi tich phan (I): out += X/TI*dt
INTEG_CODES = {"406C", "406D", "406E", "406F", "507D", "507E", "507F"}
# khoi dao ham (d/dt): out = G*(X - X_truoc)/dt  (0 khi dau vao on dinh)
DERIV_CODES = {"4070", "4071", "4072", "408D", "408E", "408F", "5082", "5083"}
# khoi loc tre bac nhat F(t): out += (X - out)*dt/T  (bam theo X, tre theo T)
LAG_CODES = {"4036", "4037", "4038", "4039", "403A", "403B"}


def _dyn_blocks(db, sheet, overrides=None):
    """Danh sach khoi dong tren sheet: {bid, code, out, x(net), sw(net), ti, init, state}.
    overrides: {bid: {'ti':.., 'init':..}} ghi de tham so cho tung khoi."""
    overrides = overrides or {}
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
    params = SS._params(db, sheet)
    out = []
    for bid, pl in pins.items():
        sym, code = binfo[bid]
        if code in INTEG_CODES:
            kind = "I"
        elif code in DERIV_CODES:
            kind = "D"
        elif code in LAG_CODES:
            kind = "L"
        else:
            continue
        pdef = (MP.get(sym) or {}).get("pins", {})
        ins = []; onet = None
        for pn, net, pt in pl:
            info = pdef.get(str(pn), {})
            side = info.get("side")
            if side == "out":
                onet = onet or net
            elif side == "in":
                ins.append({"net": net, "pt": pt, "dx": info.get("dx", 0.0)})
        if not onet:
            continue
        ana = [d for d in ins if d.get("pt") != 1]
        sw = next((d["net"] for d in ins if d.get("pt") == 1), None)
        # X = chan analog trai nhat (luong tin hieu chinh)
        xnet = min(ana, key=lambda d: d.get("dx", 0.0))["net"] if ana else None
        pm = params.get(bid, {})
        # tich phan: TI (param2); dao ham: G (param2)
        gain = SS._num(pm.get("2"))
        if gain is None:
            for k in sorted(pm, key=lambda x: SS._num(x) or 999):
                gain = SS._num(pm[k])
                if gain:
                    break
        ov = overrides.get(bid, {})
        if ov.get("ti") is not None:
            gain = ov["ti"]
        init = ov.get("init", 0.0)
        out.append({"bid": bid, "code": code, "kind": kind, "out": onet, "x": xnet,
                    "sw": sw, "ti": gain or 1.0, "init": init, "state": init, "xprev": None})
    return out


def run(db, sheet, dig_env=None, ana_env=None, dt=0.5, nsteps=200, record=None, overrides=None):
    """Chay dong nsteps buoc. Tra (val cuoi, history{net:[...]}, blocks).
    dig_env: dau vao digital {net:0/1}; ana_env: dau vao analog {net: so}.
    overrides: {bid:{'ti','init'}} ghi de tham so khoi dong.
    record: danh sach net can ghi lai theo thoi gian."""
    dig_env = dig_env or {}
    ana_env = ana_env or {}
    blocks = _dyn_blocks(db, sheet, overrides)
    for b in blocks:
        b["state"] = b.get("init", 0.0); b["xprev"] = None
    hist = defaultdict(list)
    record = record or []
    val = {}

    def _num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    for _ in range(nsteps + 1):
        aov = dict(ana_env)
        for b in blocks:
            aov[b["out"]] = b["state"]           # dau ra khoi dong = trang thai hien tai
        val, _it = SS.simulate(db, sheet, dig_env, aov)
        for n in record:
            hist[n].append(val.get(n))
        # tien trang thai khoi dong
        for b in blocks:
            x = val.get(b["x"])
            sw = val.get(b["sw"]) if b["sw"] else None
            if not _num(x):
                continue
            if b["kind"] == "I":                 # tich phan: cong don
                if sw != 1:
                    b["state"] += (x / b["ti"]) * dt   # SW=1 -> giu
            elif b["kind"] == "L":               # loc tre bac nhat: bam theo x, tre T
                if sw != 1:
                    T = b["ti"] if b["ti"] else 1e-6
                    a = 1.0 - _exp(-dt / T)      # he so chinh xac, on dinh moi dt
                    b["state"] += (x - b["state"]) * a
            else:                                # dao ham: G*(x - x_truoc)/dt
                xp = b["xprev"]
                b["state"] = 0.0 if xp is None else b["ti"] * (x - xp) / dt
                b["xprev"] = x
    return val, dict(hist), blocks
