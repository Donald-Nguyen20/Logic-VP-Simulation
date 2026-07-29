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
from . import analog_sim as AS

# khoi tich phan (I): out += X/TI*dt
INTEG_CODES = {"406C", "406D", "406E", "406F", "507D", "507E", "507F"}
# khoi dao ham (d/dt): out = G*(X - X_truoc)/dt  (0 khi dau vao on dinh)
DERIV_CODES = {"4070", "4071", "4072", "408D", "408E", "408F", "5082", "5083"}
# khoi loc tre bac nhat F(t): out += (X - out)*dt/T  (bam theo X, tre theo T)
LAG_CODES = {"4036", "4037", "4038", "4039", "403A", "403B"}
# khoi gioi han toc do doi (RL - Velocity/Rate Limiter): out tien toi X, toi da
# +up*dt (tang) / -dn*dt (giam) moi buoc. "R:para" = up/dn la tham so noi bo
# (PARAMNO 2,3 - xac nhan tu DEF/SR21E/macro_param.csv); "R:input" = up/dn la
# 2 chan vao rieng (ten "I", phan biet theo thu tu PINNO).
RATE_PARA_CODES = {"4057", "4058", "4059"}
RATE_INPUT_CODES = {"405A", "405B", "405C"}
RATE_CODES = RATE_PARA_CODES | RATE_INPUT_CODES
# khoi tram MV/SV (station): mo hinh nhieu-chan/nhieu-nut qua core/analog_sim.py + macro_analog.json
STATION_CODES = {"820A", "820B", "820C", "820D", "820E", "820F",
                  "8210", "8211", "8304", "8305"}


def _dyn_blocks(db, sheet, overrides=None):
    """Danh sach khoi dong tren sheet: {bid, code, out, x(net), sw(net), ti, init, state}
    (I/D/L) hoac {bid, code, kind:'S', sim, in_nets, out_nets, last_out} (tram MV/SV).
    overrides: {bid: {'ti':.., 'init':..}} (I/D/L) hoac
               {bid: {'inputs':{...}, 'params':{...}, 'state':{...}}} (tram)."""
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
        from core import def_sim as _DS
        # Chay bang THAN LOGIC GOC cho MOI khoi TAG co du lenh ho tro (khong chi 10 ma
        # tram): van, may cat, bao dong, data link, nut nhan... Khoi nao con lenh chua
        # cai dat thi de bo giai tinh (logic_sem/analog_sem) xu ly nhu truoc.
        if _DS.can_simulate(code) or (code in STATION_CODES and AS.has_analog(code)):
            pdef = (MP.get(sym) or {}).get("pins", {})
            in_nets = {}; out_nets = {}
            for pn, net, pt in pl:
                info = pdef.get(str(pn), {})
                nm = info.get("name")
                if not nm or not net:
                    continue
                if info.get("side") == "in":
                    in_nets[nm] = net
                elif info.get("side") == "out":
                    out_nets[nm] = net
            # ENGINE: uu tien chay THANG than lenh goc trong TAG_MCR.DEF (chinh xac),
            # chi dung mo hinh macro_analog.json khi khoi do khong co than logic goc
            from core import def_sim as DS
            pm = params.get(bid, {})
            if DS.has_def(code):
                sim = DS.DefSim(code)
                sim.set_params_by_no(pm)        # tham so THAT tu CAD_BLOCK_PARAM (PRM_n=PARAMNO n+1)
            else:
                sim = AS.AnalogSim(code)
                # mo hinh cu: anh xa vi tri tham so -> ten (doc tu manual)
                pos_map = (AS.load_analog().get(code) or {}).get("param_pos", {})
                for pos, pname in pos_map.items():
                    v = SS._num(pm.get(pos))
                    if v is not None:
                        sim.set_param(pname, v)
            ov = overrides.get(bid, {})
            for pname, pval in (ov.get("params") or {}).items():
                sim.set_param(pname, pval)          # nguoi dung ghi de tren gia tri DB
            for sname, sval in (ov.get("state") or {}).items():
                sim.state[sname] = sval
            last_out = sim.step()          # gieo gia tri dau ra ban dau (mac dinh)
            # DIEM XUAT PHAT cho bo tich phan (chi la tro giup MO PHONG - khoi that
            # KHONG co chan nao de dat MV ban dau; MV nam trong bo nho noi cua khoi va
            # duoc giu qua cac vong quet, chi ve 0 khi khoi dong nguoi hoac bi override)
            ti_ov = ov.get("ti")           # TI cho bo tich phan noi (lam cham cho de xem)
            if ti_ov and hasattr(sim, "ti_override"):
                sim.ti_override = float(ti_ov)
            init_out = ov.get("init_out")
            if init_out is not None and hasattr(sim, "warm_start"):
                sim.warm_start(init_out)
                last_out = dict(sim.out)   # gia tri xuat phat da nam o dung chan ra
            out.append({"bid": bid, "code": code, "kind": "S", "sim": sim,
                        "in_nets": in_nets, "out_nets": out_nets,
                        "forced_inputs": ov.get("inputs") or {}, "last_out": last_out})
            continue
        if code in INTEG_CODES:
            kind = "I"
        elif code in DERIV_CODES:
            kind = "D"
        elif code in LAG_CODES:
            kind = "L"
        elif code in RATE_CODES:
            kind = "R"
        else:
            continue
        pdef = (MP.get(sym) or {}).get("pins", {})
        if kind == "R":
            xnet = None; onet = None; sw = None; rate_ins = []
            for pn, net, pt in pl:
                info = pdef.get(str(pn), {})
                side = info.get("side")
                if side == "out":
                    onet = onet or net
                elif side == "in":
                    if pt == 1:
                        sw = net
                    elif info.get("name") == "I":
                        rate_ins.append((int(pn), net))
                    else:
                        xnet = xnet or net
            if not onet or not xnet:
                continue
            rate_ins.sort(key=lambda t: t[0])
            up_net = rate_ins[0][1] if len(rate_ins) > 0 else None
            dn_net = rate_ins[1][1] if len(rate_ins) > 1 else None
            pm = params.get(bid, {})
            up_val = SS._num(pm.get("2")) if code in RATE_PARA_CODES else None
            dn_val = SS._num(pm.get("3")) if code in RATE_PARA_CODES else None
            ov = overrides.get(bid, {})
            if ov.get("up") is not None:
                up_val = ov["up"]
            if ov.get("dn") is not None:
                dn_val = ov["dn"]
            init = ov.get("init", 0.0)
            out.append({"bid": bid, "code": code, "kind": "R", "out": onet, "x": xnet,
                        "sw": sw, "up": up_val, "up_net": up_net, "dn": dn_val,
                        "dn_net": dn_net, "ti": 1.0, "init": init, "state": init,
                        "xprev": None})
            continue
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
        if b["kind"] != "S":
            b["state"] = b.get("init", 0.0); b["xprev"] = None
        else:
            b["sim"].dt = dt                     # dong bo dt nguoi dung chon cho tram
    hist = defaultdict(list)
    record = record or []
    val = {}

    def _num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    for _ in range(nsteps + 1):
        aov = dict(ana_env)
        for b in blocks:
            if b["kind"] == "S":
                for nm, net in b["out_nets"].items():
                    aov[net] = b["last_out"].get(nm, 0.0)
            else:
                aov[b["out"]] = b["state"]       # dau ra khoi dong = trang thai hien tai
        val, _it = SS.simulate(db, sheet, dig_env, aov)
        for n in record:
            hist[n].append(val.get(n))
        # tien trang thai khoi dong
        for b in blocks:
            if b["kind"] == "S":
                sim = b["sim"]
                for nm, net in b["in_nets"].items():
                    v = val.get(net)
                    if _num(v):
                        sim.set_input(nm, v)
                for nm, v in b["forced_inputs"].items():
                    sim.set_input(nm, v)         # nguoi dung ghi de (uu tien cao nhat)
                b["last_out"] = sim.step()
                continue
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
            elif b["kind"] == "R":               # gioi han toc do doi: bam x, toi da +up/-dn moi giay
                # Xac nhan tu manual goc (VP1-C-L2-I-CB-00019-A, trang P-95/96, muc
                # "(6) Velocity Limiter: 4057H-405CH", bang "Reference/Internal calculation"):
                #   SW = 1 (hoac khong noi day/None, vi 4059/405C KHONG co chan SW) ->
                #          AP DUNG gioi han toc do (Y bam X theo ramp IR1 khi tang, DR1 khi giam)
                #   SW = 0 -> Y = X TRUC TIEP (BO QUA/bypass hoan toan gioi han)
                # "SW:Upside"/"SW:Downside" trong ten macro CHI la vi tri VE chan SW tren
                # hinh (tren/duoi), KHONG lam thay doi logic - ca 6 ma (4057-405C) dung
                # CHUNG 1 cong thuc nay (bang Input/Output/Parameter trong manual giong het
                # nhau giua RAL1/RAL2/RAL3).
                up = b.get("up")
                if not _num(up) and b.get("up_net"):
                    up = val.get(b["up_net"])
                dn = b.get("dn")
                if not _num(dn) and b.get("dn_net"):
                    dn = val.get(b["dn_net"])
                up = abs(up) if _num(up) else 1e12   # chua ro toc do -> khong gioi han (an toan)
                dn = abs(dn) if _num(dn) else 1e12
                cur = b["state"]
                if sw == 0:                          # SW=0 -> bypass hoan toan, Y=X
                    cur = x
                elif x > cur:
                    cur = min(x, cur + up * dt)
                else:
                    cur = max(x, cur - dn * dt)
                b["state"] = cur
            else:                                # dao ham: G*(x - x_truoc)/dt
                xp = b["xprev"]
                b["state"] = 0.0 if xp is None else b["ti"] * (x - xp) / dt
                b["xprev"] = x
    return val, dict(hist), blocks
