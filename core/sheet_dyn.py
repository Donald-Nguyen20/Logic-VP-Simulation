# -*- coding: utf-8 -*-
"""
Mo phong DONG cho sheet: chay theo buoc thoi gian dt. Moi buoc:
 1) Giai TINH (sheet_sim) voi dau ra cac khoi dong lam nguon co dinh.
 2) Tien trang thai cac khoi dong (tich phan) mot buoc dt.
Lap nsteps buoc -> gia tri hoi tu. Chi doc DB.

Cac loai khoi co trang thai rieng, phan biet bang khoa "kind":
  I  tich phan (co kep HL/LL va chan tracking) | D  dao ham
  L  loc tre bac nhat  | R  gioi han toc do doi  | G  lead/lag
  Q  tre thuan / lay mau tre (hang doi n buoc)
  C  so sanh co tre cua HCNT (CPPH/CPMH) - RA TIN HIEU SO
  S  tram MV/SV va khoi TAG chay bang than lenh goc (core/def_sim.py)
  T  delay/xung SO: DI, DIL, DT, PO, TDWO, ho TON/TOF cua HCNT, PG dao dong
Rieng nhom T va C la tin hieu SO - dau ra phai di vao dict overrides DIGITAL cua
sheet_sim.simulate(), khong phai analog (xem ghi chu trong run()).
"""
from __future__ import annotations
from collections import defaultdict
from math import exp as _exp
from . import dbreader as D
from . import sheet_render as SR
from . import sheet_sim as SS
from . import analog_sim as AS
from . import macro_def as _MD

# khoi tich phan (I): out += X/TI*dt
INTEG_CODES = {"406C", "406D", "406E", "406F", "507D", "507E", "507F", "20FE"}
# khoi dao ham (d/dt): out = G*(X - X_truoc)/dt  (0 khi dau vao on dinh)
DERIV_CODES = {"4070", "4071", "4072", "408D", "408E", "408F", "5082", "5083"}
# khoi loc tre bac nhat F(t): out += (X - out)*dt/T  (bam theo X, tre theo T)
LAG_CODES = {"4036", "4037", "4038", "4039", "403A", "403B"}
# khoi gioi han toc do doi (RL - Velocity/Rate Limiter): out tien toi X, toi da
# +up*dt (tang) / -dn*dt (giam) moi buoc. "R:para" = up/dn la tham so noi bo
# (PARAMNO 2,3 - xac nhan tu DEF/SR21E/macro_param.csv); "R:input" = up/dn la
# 2 chan vao rieng (ten "I", phan biet theo thu tu PINNO).
RATE_PARA_CODES = {"4057", "4058", "4059", "20FD"}
RATE_INPUT_CODES = {"405A", "405B", "405C"}
RATE_CODES = RATE_PARA_CODES | RATE_INPUT_CODES
# khoi tram MV/SV (station): mo hinh nhieu-chan/nhieu-nut qua core/analog_sim.py + macro_analog.json
STATION_CODES = {"820A", "820B", "820C", "820D", "820E", "820F",
                  "8210", "8211", "8304", "8305"}
# Ho LAG lay hang so thoi gian T tu CHAN VAO thu hai chu khong tu tham so
# ("T:input": LAG3/LAG4/LAG6 trong sach macro).
LAG_TIN_CODES = {"4038", "4039", "403B"}

# ---- (Q) TRE THUAN: DEAD TIME 405E/408B/408C va LAY MAU TRE 407A ----
# Sach macro goc (VP1-C-L2-I-CB-00019-A, trang P-82/83, muc "DEAD TIME - Pure Delay"):
#   "Delay Time (s) = e x T1 x M1"  voi e = chu ky quet CPU (Cyclic Scanning Period),
#   T1 = so chu ky CPU (PARAMNO 2), M1 = so lan lay mau (PARAMNO 3).
# Sach ghi thang "In case e is 0.2 sec, we recommend..." kem bang goi y (0,2/1/1)
# (1/1/5) (2/1/10) (4/1/20) (5/1/25) (6/1/30) (10/2/25) (15/3/25) (20/4/25) (30/5/30)
# - MOI dong deu thoa dung 0,2 x T1 x M1, va trang P-84 xac nhan (T1,M1) = (1,10),
# (2,5), (5,2), (10,1) cho CUNG mot do tre. Trong DB du an KHONG co cot nao ghi chu
# ky quet (CAD_LOOP chi co LOOPNO/LOOPNAME/CPUNO/PROJNO) nen lay dung 0,2 s theo sach.
SCAN_EPS = 0.2
DEAD_CODES = {"405E", "408B", "408C"}       # tre = SCAN_EPS * T1(param2) * M1(param3)
SAMP_CODES = {"407A"}                        # Z^(-n): tre = SCAN_EPS * n(param2)
DELAY_CODES = DEAD_CODES | SAMP_CODES

# ---- (C) SO SANH CO TRE cua HCNT ----
# 20FB CPPH ngo ra "H" (so, PIN_TYPE=1), 20FC CPMH ngo ra "L". Hai muc cai nam o
# PARAMNO 1 va 2. Do tren du an: 11/96 khoi 20FB co P1<>P2 va LAN NAO P1 cung LON hon
# P2 (900/890, 0,5/0,1, -0,3/-1,3, 0/-0,005, 0,45/0,15); 15/59 khoi 20FC co P1<>P2 va
# lan nao P1 cung NHO hon P2 (4500/4510, 50/53, 43,5/46,5, 0/0,5, 600/610, 12/12,1)
# -> P1 la muc BAT, P2 la muc NHA (vong tre).
CMP_HI_CODES = {"20FB"}
CMP_LO_CODES = {"20FC"}
CMP_CODES = CMP_HI_CODES | CMP_LO_CODES

# ---- (G) LEAD/LAG: Y = (1 + TLe*s)/(1 + TLa*s) * X, kep trong [LL1, HL1] ----
# Sach macro trang P-90..94 (LLG1..LLG6) va bang tham so DEF/SR21E/macro_param.csv:
# ban thuong PARAMNO 2=HL1, 3=LL1, 5=Lead, 6=Lag; ban "T:input" (403E/403F/4041) lay
# Lead/Lag tu 2 chan vao in chu "Le"/"La". Ban HCNT 2107 in nhan "HL:" o dong dau va
# co dung 4 tham so -> 1=HL, 2=LL, 3=Lead, 4=Lag.
LLG_PARA_CODES = {"403C", "403D", "4040"}
LLG_INPUT_CODES = {"403E", "403F", "4041"}
LLG_HCNT_CODES = {"2107"}
LLG_CODES = LLG_PARA_CODES | LLG_INPUT_CODES | LLG_HCNT_CODES

# Vi tri tham so cua khoi TICH PHAN co gioi han: (TI, HL, LL). None = lay tu chan vao.
# 406C/406D (L:para): 2=TI1, 3=HL1, 4=LL1. 406E/406F (L:input): chi co 2=TI1, HL/LL la
# 2 chan vao ben phai. 20FE IH cua HCNT in nhan "HL:" truoc -> 1=HL, 2=LL, 3=TI.
INTEG_POS = {"406C": ("2", "3", "4"), "406D": ("2", "3", "4"),
             "406E": ("2", None, None), "406F": ("2", None, None),
             "20FE": ("3", "1", "2")}
# Vi tri tham so toc do (tang, giam) cua khoi gioi han toc do. 20FD DLMH cua HCNT in
# nhan "Ri:" va chi co 2 tham so -> nam o 1 va 2, khac ho 4057-4059 (2 va 3).
RATE_POS = {"20FD": ("1", "2")}

_TIMER_CODES = None


def timer_codes():
    """Ma cac khoi delay/xung SO (DI, DIL, DT, PO, TDWO, ho TON/TOF/SS1/SS2 cua HCNT, PG).
    Lay THANG tu logic_sem.json - muc nao co khoa "tmr" thi la timer. Nho vay bang ngu
    nghia la NOI DUY NHAT khai bao ho timer: them 1 ma moi chi phai sua 1 file."""
    global _TIMER_CODES
    if _TIMER_CODES is None:
        from . import cond_tree as CT
        _TIMER_CODES = {k.upper() for k, v in (CT._sem() or {}).items()
                        if isinstance(v, dict) and v.get("tmr")}
    return _TIMER_CODES


def timer_left(b):
    """Con bao nhieu giay nua thi khoi timer 'b' doi trang thai. None = dang khong dem.

    Badge chi ghi "y=1" thi nguoi dung khong phan biet duoc timer DANG GIU delay voi
    timer da het gio - hai cai nhin y het nhau. Suy tu (xp, y, acc) theo dung nghia
    tung ho da ghi o _step_timer()."""
    T = b.get("Tef", b.get("T"))
    if not isinstance(T, (int, float)) or T <= 0:
        return None
    acc, fam, y, xp = b.get("acc") or 0.0, b.get("tmr"), b.get("y"), b.get("xp")
    if fam == "PG":
        off = b.get("toff") if isinstance(b.get("toff"), (int, float)) else 0.0
        if xp != 1 or T + off <= 0:
            return None
        return T - acc if acc < T else T + off - acc     # con bao lau thi lat nua chu ky
    if fam in ("DI", "DIL"):
        dem = xp == 1 and not y                  # dang cho du gio de BAT
    elif fam == "DT":
        dem = xp != 1 and bool(y)                # dang giu them sau khi dau vao da tat
    else:
        dem = bool(y)                            # PO/TDWO: xung dang phat
    return max(T - acc, 0.0) if dem else None


def _step_timer(b, x, val, dt):
    """Tien 1 buoc dt cho 1 khoi delay/xung so. x = gia tri chan vao (0/1/None).

    Nghia tung ho lay tu sach macro goc cua hang (truong "explain" trong
    core/macro_manual.json, nguyen van tieng Anh cua Toshiba):
      DI/DIL (on-delay):  "After input changes to ON, output is turned ON after a delay
              of the specified time." -> X len 1 va GIU du T thi Y len 1; X ve 0 -> Y ve
              0 NGAY va dong ho dem lai tu dau.
      DT (off-delay): nguoc lai - X len 1 thi Y len 1 ngay, X ve 0 thi Y con GIU them T.
      PO (SS1, one-shot 1): "A time-limit pulse for a specified time is output starting
              when input changes from OFF to ON." -> chi SUON LEN moi phat xung; X ve 0
              KHONG cat xung.
      TDWO (SS2, one-shot 2): nhu PO nhung X ve 0 la cat xung ngay ("wipe out").
      1SH1/1SH2 (one scan shot, trang P-118): "If the input X turns ON (1SH1) / OFF
              (1SH2), the output Y turns ON in one controller cycle." -> xung dai dung
              MOT chu ky CPU, khong co tham so thoi gian nao ca.
      PG (dao dong co cong): X=1 thi phat vuong ON=T / OFF=toff; X=0 thi tat.

    'acc' bi CHAN lai ngay khi dong ho het gio (khong cong don vo han) de _snap() con
    nhan ra khoi da dung yen - neu de acc chay mai thi moi sheet co timer se khong bao
    gio "settle" va luon phai chay du nsteps buoc."""
    T = b["T"]
    if T is None and b["tnet"]:                  # bien the "T:input": thoi gian den tu day
        v = val.get(b["tnet"])
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            T = float(v) * 60.0 if b["tunit"] == "min" else float(v)
    if T is None or T < 0:
        T = 0.0
    b["Tef"] = T                                 # thoi gian THUC SU dung - badge doc o day
    x = 1 if x == 1 else 0
    xp = b["xp"]
    if xp is None:
        xp = x            # buoc dau: coi nhu dau vao da on dinh -> khong tu phat xung ma
    fam = b["tmr"]
    if fam in ("DI", "DIL"):
        if not x:
            b["acc"] = 0.0
            b["y"] = 0
        elif not b["y"]:
            b["acc"] += dt
            if b["acc"] + 1e-9 >= T:
                b["y"] = 1
    elif fam == "DT":
        if x:
            b["acc"] = 0.0
            b["y"] = 1
        elif b["y"]:
            b["acc"] += dt
            if b["acc"] + 1e-9 >= T:
                b["y"] = 0
    elif fam in ("PO", "TDWO"):
        if x and not xp:
            b["acc"] = 0.0
            b["y"] = 1
        elif b["y"]:
            b["acc"] += dt
            if b["acc"] + 1e-9 >= T:
                b["y"] = 0
        if fam == "TDWO" and not x:
            b["y"] = 0                           # SS2: dau vao tat la cat xung ngay
    elif fam in ("1SH1", "1SH2"):
        # Trong mo phong chay theo buoc thi "mot chu ky CPU" = MOT BUOC dt.
        # Khi dt = 0 (freeze_tmr: nguoi dung chi vua doi 1 dau vao, thoi gian THAT chua
        # troi) thi GIU xung lai cho nhin thay, y het cach PO duoc giu - neu tat luon
        # thi ca vong giai lai se khong bao gio hien duoc xung nao.
        if x != xp and (x == 1) == (fam == "1SH1"):
            b["y"] = 1
        elif dt > 0:
            b["y"] = 0
    elif fam == "PG":
        off = b["toff"] if isinstance(b["toff"], (int, float)) else 0.0
        per = T + off
        if not x:
            b["acc"] = 0.0
            b["y"] = 0
        elif per <= 0:
            b["y"] = 0                           # ca hai nua chu ky = 0 -> khong dao dong
        else:
            # Doc dau ra theo goc pha HIEN TAI roi moi tien dong ho. Neu tien truoc roi
            # moi doc thi nua chu ky ON bi ngan mat dung 1 buoc dt (do that: ON=1s voi
            # dt=0,5s chi ra 1 buoc bat thay vi 2).
            b["y"] = 1 if b["acc"] < T else 0
            b["acc"] = (b["acc"] + dt) % per
    b["xp"] = x


_HAS_DYN = {}


def has_dynamic(db, sheet):
    """Sheet nay co khoi DONG nao khong (tich phan/dao ham/loc tre/gioi han toc do/khoi
    TAG co than lenh goc)? Do duoc tren du an: 68% sheet KHONG co khoi nao - voi chung
    thi chay dong la 301 luot giai tinh de roi khong co gi tien len (0,001s -> 0,56s).
    Hoi 1 cau SQL (co nho ket qua) re hon nhieu."""
    key = (db, sheet)
    if key in _HAS_DYN:
        return _HAS_DYN[key]
    ok = False
    try:
        from . import def_sim as _DS
        c = D.connect(db).cursor()
        for (code,) in c.execute("SELECT MACROCODE FROM CAD_BLOCK WHERE ID=?", (sheet,)):
            code = (code or "").upper()
            if (code in INTEG_CODES or code in DERIV_CODES or code in LAG_CODES
                    or code in RATE_CODES or code in DELAY_CODES or code in CMP_CODES
                    or code in LLG_CODES or code in timer_codes()
                    or _DS.can_simulate(code)
                    or (code in STATION_CODES and AS.has_analog(code))):
                ok = True
                break
    except Exception:
        ok = False
    _HAS_DYN[key] = ok
    return ok


def _sem_of(code):
    from . import cond_tree as CT
    return (CT._sem() or {}).get(code) or {}


def _timer_block(bid, code, pl, pdef, db, sheet, ov):
    """Mo ta 1 khoi delay/xung so tu danh sach chan. None neu thieu chan vao hoac ra.

    Chan nhan theo TEN in tren ban ve goc (core/macro_pins.json, do tu MacroDef.db):
      - chan VAO ten "T"  = thoi gian lay tu DAY (bien the "T:input"), thay cho tham so
                            trong CAD_BLOCK_PARAM;
      - chan VAO con lai  = X (dau vao chinh; ten in la "DI"/"PO"/... hoac de trong);
      - chan RA ten "C"   = so dem cua dong ho. KHONG mo phong: sach macro cua hang khong
                            ghi day la thoi gian DA TROI hay CON LAI, ma trong du an co
                            255 khoi dang noi day chan nay - doan bua se sai het. De
                            nguyen "chua biet" nhu truoc.
      - chan RA con lai   = Y (ket qua logic), ten in la "s"/"M"/"S".
    """
    s = _sem_of(code)
    xnet = ynet = tnet = None
    for pn, net, _pt in pl:
        info = pdef.get(str(pn), {})
        nm = (info.get("name") or "").strip()
        if not net:
            continue
        if info.get("side") == "in":
            if nm == "T":
                tnet = tnet or net
            elif xnet is None:
                xnet = net
        elif info.get("side") == "out" and nm != "C" and ynet is None:
            ynet = net
    if not xnet or not ynet:
        return None
    T = SS.timer_secs(db, sheet, s, bid)
    if ov.get("tsec") is not None:               # nguoi dung ghi de thoi gian cho de xem
        T = ov["tsec"]
    toff = None
    if s.get("toff"):                            # PG: nua chu ky TAT nam o 1 tham so khac
        toff = SS._num(SS._params(db, sheet).get(bid, {}).get(s["toff"]))
    return {"bid": bid, "code": code, "kind": "T", "out": ynet, "x": xnet, "tnet": tnet,
            "tmr": s.get("tmr"), "tunit": s.get("tunit"), "T": T, "toff": toff,
            "y": 0, "acc": 0.0, "xp": None}


def _chan_khoi(pl, pdef):
    """Tach chan cua 1 khoi thanh (danh sach chan vao ANALOG da sap, net SW, net ra).

    Chan vao analog sap theo (dx, -dy): trai truoc, cung do trai thi TREN truoc - dung
    thu tu ve tren ban ve goc. Nho vay ana[0] luon la dong tin hieu chinh X, ana[1] la
    chan phu thu nhat (T tracking cua bo tich phan, hang so thoi gian cua LAG "T:input",
    Lead cua LLG "T:input")... Phai pha the bang do CAO vi co khoi ve hai chan cung
    dx=0 (20FE IH: X o dy=-4, T o dy=-8; 403F LLG4 cung vay)."""
    ana = []
    sw = None
    onet = None
    for pn, net, pt in pl:
        info = pdef.get(str(pn), {})
        side = info.get("side")
        if side == "out":
            onet = onet or net
        elif side == "in":
            if pt == 1:
                sw = sw or net
            elif net:
                ana.append({"net": net, "name": (info.get("name") or "").strip(),
                            "dx": info.get("dx", 0.0), "dy": info.get("dy", 0.0),
                            "pn": int(pn)})
    ana.sort(key=lambda d: (d["dx"], -d["dy"], d["pn"]))
    return ana, sw, onet


def _delay_block(bid, code, ana, sw, onet, pm, ov):
    """Khoi TRE THUAN (405E/408B/408C) va LAY MAU TRE (407A). Do tre quy ve GIAY roi
    de vong chay dong doi ra so buoc dt (giong co che FDT trong than lenh khoi tram).
    'ti' giu do tre de badge va o ghi de tham so tren giao dien dung chung mot khoa."""
    if not onet or not ana:
        return None
    if code in SAMP_CODES:
        n1 = SS._num(pm.get("2"))
        delay = SCAN_EPS * n1 if n1 is not None else 0.0
    else:
        t1 = SS._num(pm.get("2"))
        m1 = SS._num(pm.get("3"))
        delay = SCAN_EPS * (t1 or 0.0) * (m1 or 0.0)
    if ov.get("ti") is not None:
        delay = float(ov["ti"])
    init = ov.get("init", 0.0)
    return {"bid": bid, "code": code, "kind": "Q", "out": onet, "x": ana[0]["net"],
            "sw": sw, "ti": delay, "q": None, "init": init, "state": init,
            "xprev": None}


def _cmp_block(bid, code, ana, onet, pm, ov):
    """Khoi so sanh co tre 20FB/20FC. None khi muc cai la thanh ghi AN#### (chinh dinh
    tu ban dieu khien, KHONG co bang nao trong DB du an doi ra so) - de nguyen "chua
    biet" con hon doan bua ra mot nguong sai."""
    if not onet or not ana:
        return None
    on = SS._num(pm.get("1"))
    if on is None:
        return None
    off = SS._num(pm.get("2"))
    if off is None:
        off = on
    if ov.get("ti") is not None:
        on, off = float(ov["ti"]), float(ov["ti"]) + (off - on)   # giu nguyen be rong vong tre
    return {"bid": bid, "code": code, "kind": "C", "out": onet, "x": ana[0]["net"],
            "sw": None, "hi": code in CMP_HI_CODES, "on": on, "off": off,
            "ti": on, "y": 0, "state": 0.0, "xprev": None}


def _llg_block(bid, code, ana, sw, onet, pm, ov):
    """Khoi Lead/Lag. 'w' la trang thai cua khau tre bac nhat ben trong (xem cong thuc
    o vong chay dong). 'ti' = Lag de badge/o ghi de dung chung mot khoa voi ho LAG."""
    if not onet or not ana:
        return None
    le_net = la_net = None
    if code in LLG_HCNT_CODES:
        hl, ll = SS._num(pm.get("1")), SS._num(pm.get("2"))
        le, la = SS._num(pm.get("3")), SS._num(pm.get("4"))
    else:
        hl, ll = SS._num(pm.get("2")), SS._num(pm.get("3"))
        le, la = SS._num(pm.get("5")), SS._num(pm.get("6"))
        if code in LLG_INPUT_CODES:
            le = la = None
            le_net = ana[1]["net"] if len(ana) > 1 else None
            la_net = ana[2]["net"] if len(ana) > 2 else None
    if ov.get("ti") is not None:
        la, la_net = float(ov["ti"]), None
    init = ov.get("init", 0.0)
    return {"bid": bid, "code": code, "kind": "G", "out": onet, "x": ana[0]["net"],
            "sw": sw, "hl": hl, "ll": ll, "le": le, "la": la, "le_net": le_net,
            "la_net": la_net, "ti": la, "w": init, "init": init, "state": init,
            "xprev": None}


def _integ_block(bid, code, kind, ana, sw, onet, pm, ov):
    """Khoi tich phan/dao ham/loc tre bac nhat.

    Rieng bo tich phan co gioi han (406C-406F, 20FE IH) con hai muc kep HL1/LL1 va mot
    chan TRACKING T - sach macro trang P-128:
        SW = 0 -> Y = Max(LL1, Min(HL1, (1/TI1) * tich phan X dt))
        SW = 1 -> Y = Max(LL1, Min(HL1, T))
    (chieu cong tac NGUOC voi ho LAG/LLG/RL: o day SW=1 la BAM THEO T chu khong phai
    "cho phep tac dung"). Truoc day chi giu nguyen gia tri khi SW=1 va khong kep gioi
    han - lech that so voi 153 khoi tich phan cua du an."""
    if not onet:
        return None
    xnet = ana[0]["net"] if ana else None
    hl = ll = hl_net = ll_net = tnet = None
    if kind == "I":
        ti_pos, hl_pos, ll_pos = INTEG_POS.get(code, ("2", None, None))
        gain = SS._num(pm.get(ti_pos))
        tnet = ana[1]["net"] if len(ana) > 1 else None
        if hl_pos:
            hl, ll = SS._num(pm.get(hl_pos)), SS._num(pm.get(ll_pos))
        elif len(ana) > 3:
            hl_net, ll_net = ana[2]["net"], ana[3]["net"]   # ban "L:input": HL tren, LL duoi
    elif kind == "L":
        gain = SS._num(pm.get("2"))
        if code in LAG_TIN_CODES and len(ana) > 1:
            tnet = ana[1]["net"]                            # "T:input": T den tu day
    else:
        gain = SS._num(pm.get("2"))
        if gain is None:
            for k in sorted(pm, key=lambda x: SS._num(x) or 999):
                gain = SS._num(pm[k])
                if gain:
                    break
    if ov.get("ti") is not None:
        gain = ov["ti"]
        tnet = tnet if kind == "I" else None
    init = ov.get("init", 0.0)
    return {"bid": bid, "code": code, "kind": kind, "out": onet, "x": xnet, "sw": sw,
            "ti": gain or 1.0, "tnet": tnet, "hl": hl, "ll": ll, "hl_net": hl_net,
            "ll_net": ll_net, "init": init, "state": init, "xprev": None}


def _dyn_blocks(db, sheet, overrides=None, live_values=None, sim_cache=None,
                freeze_tmr=False):
    """Danh sach khoi dong tren sheet:
      {bid, code, out, x(net), sw(net), ti, init, state}      I/D/L/R
        + hl/ll/hl_net/ll_net/tnet cho bo tich phan co gioi han (I)
      {bid, ..., kind:'Q', ti(giay tre), q(hang doi)}         tre thuan / lay mau tre
      {bid, ..., kind:'C', hi, on, off, y}                    so sanh co tre (ra 0/1)
      {bid, ..., kind:'G', hl, ll, le, la, le_net, la_net, w}  lead/lag
      {bid, code, kind:'S', sim, in_nets, out_nets, last_out} tram MV/SV
      {bid, code, kind:'T', out, x, tnet, tmr, tunit, T, toff, y, acc, xp} delay/xung so
    overrides: {bid: {'ti':.., 'init':..}} (I/D/L/R/Q/G, 'ti' cua C la nguong bat),
               {bid: {'tsec':..}} (timer) hoac
               {bid: {'inputs':{...}, 'params':{...}, 'state':{...}}} (tram).
    live_values: {net: gia_tri} - KET QUA VUA TINH cua ca sheet (SS.simulate), de bom vao
    chan vao (in_nets) cua khoi TRAM truoc khi step() 1 lan, giong het cach run() (mo phong
    dong nhieu buoc) da lam - de badge "Simulate on sheet" (bao gom ca luc dao dong) phan
    anh dung tin hieu dang chay toi no.
    sim_cache: {bid: sim_object} - TUY CHON, do NGUOI GOI (ui/app.py) giu SONG xuyen cac
    lan goi lien tiep (moi lan simulate/dao dong tick). MV cua khoi TRAM la 1 bo TICH LUY
    (state noi bo), khong phai cong thuc tinh thang - neu moi lan deu dung sim MOI (state
    rong) thi MV luon dung yen o gia tri khoi dong du input da dung. Truyen sim_cache vao
    de TAI SU DUNG dung 1 object sim cho moi bid, giup MV thuc su tich luy qua thoi gian
    (giong nhu dang chay dong ngam). None (mac dinh, dung cho run() ben duoi) = KHONG cache,
    moi lan dung sim moi tu dau (dung cho 1 lan chay dong doc lap, khong lien quan lan khac)."""
    overrides = overrides or {}
    live_values = live_values or {}
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
        if code in timer_codes():
            tb = _timer_block(bid, code, pl, (MP.get(sym) or {}).get("pins", {}),
                              db, sheet, overrides.get(bid, {}))
            if tb:
                out.append(tb)
            continue
        from core import def_sim as _DS
        # Chay bang THAN LOGIC GOC cho MOI khoi TAG co du lenh ho tro (khong chi 10 ma
        # tram): van, may cat, bao dong, data link, nut nhan... Khoi nao con lenh chua
        # cai dat thi de bo giai tinh (logic_sem/analog_sem) xu ly nhu truoc.
        if _DS.can_simulate(code) or (code in STATION_CODES and AS.has_analog(code)):
            # pin_defs() chu khong phai MP tho: no dien ten cho chan RA ma hang de trong
            # (chan "di thang" tu chan vao). De tho thi out_nets rong -> 12.476 khoi
            # tinh xong roi vut ket qua di, tin hieu khong chay tiep. Do lai tren 32 sheet
            # cua 4 file .db: so khoi mo phong CO dau ra dung duoc len 4 -> 20.
            # Xem macro_def.pin_defs.
            from core import macro_def as _MD
            pdef = _MD.pin_defs(sym)
            pkey = _MD.pin_wire_keys(pdef)
            in_nets = {}; out_nets = {}
            for pn, net, pt in pl:
                info = pdef.get(str(pn), {})
                # Than lenh TODEN goi chan bang SO; hang de trong ten phan lon chan vao
                # va con dat trung ten o vai khoi OR. Khoa noi day phai duy nhat, neu
                # khong khoi chay voi 0 dau vao hoac hai chan dam vao lam mot.
                nm = (pkey.get(str(pn)) if _DS.PIN_BY_NO
                      else (info.get("name") or "").strip())
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
            cached = sim_cache.get(bid) if sim_cache is not None else None
            is_new = cached is None
            if cached is not None:
                sim = cached                    # TAI SU DUNG - giu nguyen state (MV) tich luy tu truoc
            elif DS.has_def(code):
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
            if is_new and sim_cache is not None:
                sim_cache[bid] = sim
            ov = overrides.get(bid, {})
            for pname, pval in (ov.get("params") or {}).items():
                sim.set_param(pname, pval)          # nguoi dung ghi de tren gia tri DB
            for sname, sval in (ov.get("state") or {}).items():
                sim.state[sname] = sval
            # nut vat ly tren mat tram (vd OPS_IN5 = nut AUT) - nguon THAT su doc lap voi
            # moi day, ton tai song song (xem ghi chu trong ui/app.py::_sim_station_config)
            for opname, opval in (ov.get("ops") or {}).items():
                sim.ops[opname] = opval
            # bom gia tri THAT dang chay toi tung chan vao (tu ket qua vua tinh ca sheet),
            # roi moi toi gia tri nguoi dung ghi de tay (uu tien cao nhat) - dung thu tu
            # nhu vong lap run() o duoi, chi khac la chi step() 1 lan (snapshot) chu khong
            # tich luy qua thoi gian.
            for nm, net in in_nets.items():
                v = live_values.get(net)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    try:
                        sim.set_input(nm, v)
                    except Exception:
                        pass
            for nm, v in (ov.get("inputs") or {}).items():
                try:
                    sim.set_input(nm, v)
                except Exception:
                    pass
            # Dong ho trong than lenh tram (TON tre bat, FDT tre van chuyen) chi duoc
            # chay khi THOI GIAN THAT troi. Buoc step() ngay duoi day chay MOI LAN ve lai
            # sheet, ke ca khi nguoi dung chi bam doi 1 dau vao - khong chan lai thi bam
            # 60 lan la an mat 30s cua mot cai tre bao dong.
            if hasattr(sim, "freeze_tmr"):
                sim.freeze_tmr = freeze_tmr
            last_out = sim.step()          # tien 1 buoc - neu la sim TAI SU DUNG thi tiep noi tu state cu
            # DIEM XUAT PHAT cho bo tich phan (chi la tro giup MO PHONG - khoi that
            # KHONG co chan nao de dat MV ban dau; MV nam trong bo nho noi cua khoi va
            # duoc giu qua cac vong quet, chi ve 0 khi khoi dong nguoi hoac bi override)
            ti_ov = ov.get("ti")           # TI cho bo tich phan noi (lam cham cho de xem)
            if ti_ov and hasattr(sim, "ti_override"):
                sim.ti_override = float(ti_ov)
            init_out = ov.get("init_out")
            # CHI ap dung diem xuat phat khi sim MOI duoc tao (is_new) - neu sim dang duoc
            # TAI SU DUNG (dang tich luy tu cac lan truoc) ma van goi warm_start moi lan thi
            # se KEO MV VE LAI init_out o MOI TICK, khong bao gio tich luy len duoc.
            if is_new and init_out is not None and hasattr(sim, "warm_start"):
                sim.warm_start(init_out)
                last_out = dict(sim.out)   # gia tri xuat phat da nam o dung chan ra
            out.append({"bid": bid, "code": code, "kind": "S", "sim": sim,
                        "in_nets": in_nets, "out_nets": out_nets,
                        "forced_inputs": ov.get("inputs") or {},
                        "forced_ops": ov.get("ops") or {}, "last_out": last_out})
            continue
        if code in INTEG_CODES:
            kind = "I"
        elif code in DERIV_CODES:
            kind = "D"
        elif code in LAG_CODES:
            kind = "L"
        elif code in RATE_CODES:
            kind = "R"
        elif code in DELAY_CODES:
            kind = "Q"
        elif code in CMP_CODES:
            kind = "C"
        elif code in LLG_CODES:
            kind = "G"
        else:
            continue
        pdef = (MP.get(sym) or {}).get("pins", {})
        if kind in ("Q", "C", "G"):
            ana, sw, onet = _chan_khoi(pl, pdef)
            pm = params.get(bid, {})
            ov = overrides.get(bid, {})
            if kind == "Q":
                nb = _delay_block(bid, code, ana, sw, onet, pm, ov)
            elif kind == "C":
                nb = _cmp_block(bid, code, ana, onet, pm, ov)
            else:
                nb = _llg_block(bid, code, ana, sw, onet, pm, ov)
            if nb:
                out.append(nb)
            continue
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
            up_pos, dn_pos = RATE_POS.get(code, ("2", "3"))
            up_val = SS._num(pm.get(up_pos)) if code in RATE_PARA_CODES else None
            dn_val = SS._num(pm.get(dn_pos)) if code in RATE_PARA_CODES else None
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
        ana, sw, onet = _chan_khoi(pl, pdef)
        nb = _integ_block(bid, code, kind, ana, sw, onet, params.get(bid, {}),
                          overrides.get(bid, {}))
        if nb:
            out.append(nb)
    return out


def _kep(y, hl, ll, isnum):
    """Kep y trong [LL, HL]. Muc gioi han co the la tham so (so) hoac chan vao (net).
    Muc nao doc khong ra so (vd tham so ghi AN#### - thanh ghi chinh tu ban dieu khien)
    thi BO QUA phia do, khong doan bua."""
    if isnum(hl):
        y = min(y, hl)
    if isnum(ll):
        y = max(y, ll)
    return y


def _step_integ(b, x, sw, val, dt, isnum):
    """Tich phan co gioi han (406C-406F, 20FE IH). Sach macro trang P-128:
        SW = 0 -> Y = Max(LL1, Min(HL1, (1/TI1) * tich phan X dt))
        SW = 1 -> Y = Max(LL1, Min(HL1, T))          T = chan TRACKING
    Kep NGAY sau moi buoc (khong doi den luc doc) de bo tich phan khong "sac" vuot muc
    roi phai xa nguoc lai - dung nhu khoi that: no khong tich luy qua gioi han."""
    hl, ll = b.get("hl"), b.get("ll")
    if b.get("hl_net"):                          # ban "L:input": muc gioi han den tu day
        v = val.get(b["hl_net"])
        hl = v if isnum(v) else hl
    if b.get("ll_net"):
        v = val.get(b["ll_net"])
        ll = v if isnum(v) else ll
    if sw == 1:
        t = val.get(b["tnet"]) if b.get("tnet") else None
        if isnum(t):
            b["state"] = t                       # bam theo gia tri tracking
    elif isnum(x):
        b["state"] += (x / b["ti"]) * dt
    b["state"] = _kep(b["state"], hl, ll, isnum)


def _step_delay(b, x, sw, dt):
    """Tre thuan: dau ra = dau vao cua 'delay' giay truoc. Giu mot hang doi dai
    n = round(delay/dt) buoc, y het co che FDT trong than lenh khoi tram.

    Sach macro trang P-84 (bang "SW / Input X va Output Y" cua DTM2/DTM3):
      SW = 1 (hoac khoi khong co chan SW nhu 405E) -> AP DUNG do tre
      SW = 0 -> Y = X (bo qua)
    Lan dau chay thi NAP DAY hang doi bang chinh gia tri dang co, khong nap 0: khoi
    that dang o trang thai on dinh chu khong khoi dong tu 0, nap 0 se de ra mot cu sut
    gia tao dai bang dung do tre."""
    if sw == 0 or dt <= 0:
        b["q"] = None
        b["state"] = x
        return
    n = int(round((b["ti"] or 0.0) / dt))
    if n <= 0:
        b["q"] = None
        b["state"] = x
        return
    q = b.get("q")
    if not q:
        q = [x] * n
    while len(q) > n:
        q.pop(0)
    while len(q) < n:
        q.insert(0, q[0] if q else x)
    q.append(x)
    b["state"] = q.pop(0)
    b["q"] = q


def _step_cmp(b, x):
    """So sanh co tre (20FB ra 'H' / 20FC ra 'L'): bat o muc 'on', nha o muc 'off'."""
    if b["hi"]:
        b["y"] = 1 if x >= b["on"] else (0 if x < b["off"] else b["y"])
    else:
        b["y"] = 1 if x <= b["on"] else (0 if x > b["off"] else b["y"])


def _step_llg(b, x, sw, val, dt, isnum):
    """Lead/Lag: Y = (1 + TLe*s)/(1 + TLa*s) * X, kep trong [LL1, HL1] (manual P-90..94).

    Tach khau nay thanh phan thang cong mot khau tre bac nhat, dung y hoc:
        (1 + TLe*s)/(1 + TLa*s) = TLe/TLa + (1 - TLe/TLa) * 1/(1 + TLa*s)
    nen chi can GIU DUNG MOT trang thai w = loc tre bac nhat cua X voi hang so TLa,
    roi Y = (TLe/TLa)*X + (1 - TLe/TLa)*w. Kiem lai bang vi du trong sach (Lead=0,
    Lag=10 s): TLe/TLa = 0 -> Y = w, dat 63,2% sau dung 10 s.
    SW = 0 -> Y = X (bo qua khau dong), giong ho LAG/RL.

    HL1/LL1 van KEP ca khi SW = 0. Bang chan tri trang P-91 chi ghi phan DONG cua khoi
    (hang SW=1 cung khong viet Max/Min du khoi ro rang co hai tham so gioi han), con do
    thi ngay ben canh ve HL va LL thanh hai duong CHAN tren duong Y - tuc bo han che nam
    o dau ra, luon tac dung. Neu hieu nguoc lai thi 25 khoi 2107 cua EHC (vi du HL=10,
    LL=0) se ban ra 100 ngay khi cong tac tat, dieu mot mach dieu khien that khong lam.
    Khi SW = 0 van keo w theo x de luc bat lai khong bi giat (bumpless)."""
    le, la = b.get("le"), b.get("la")
    if b.get("le_net") and not isnum(le):
        le = val.get(b["le_net"])
    if b.get("la_net") and not isnum(la):
        la = val.get(b["la_net"])
    if sw == 0 or not isnum(la) or la <= 0:
        b["w"] = x                               # khong tre -> bam thang
        y = x
    else:
        b["w"] += (x - b["w"]) * (1.0 - _exp(-dt / la))
        r = (le / la) if (isnum(le) and le > 0) else 0.0
        y = r * x + (1.0 - r) * b["w"]
    b["state"] = _kep(y, b.get("hl"), b.get("ll"), isnum)


def run(db, sheet, dig_env=None, ana_env=None, dt=0.5, nsteps=200, record=None,
        overrides=None, settle=0, state=None, sim_cache=None, stats=None,
        freeze_tmr=False, latch=None):
    """Chay dong nsteps buoc. Tra (val cuoi, history{net:[...]}, blocks).
    dig_env: dau vao digital {net:0/1}; ana_env: dau vao analog {net: so}.
    overrides: {bid:{'ti','init'}} ghi de tham so khoi dong.
    record: danh sach net can ghi lai theo thoi gian.

    settle > 0: DUNG SOM ngay khi moi khoi dong het thay doi trong 'settle' buoc lien
        tiep. Do tren du an: hau het sheet on dinh trong vai buoc dau, nen chay du 300
        buoc la lang phi ~300 lan. nsteps luc nay chi con la tran an toan (khoi tich
        phan bi lech thuong truc thi ramp mai, khong bao gio on dinh).
    state: {bid: {"s":.., "xprev":..}} cho khoi I/D/L/R, {bid: {"y","acc","xp"}} cho
        timer. Doc luc bat dau (neu co) va GHI LAI vao chinh dict do luc ket thuc, de
        lan chay sau TIEP TUC tu day thay vi nhay ve 0. Truyen None = bat dau lai tu
        'init' (I/D/L/R) hoac tu trang thai TAT (timer).
    sim_cache: {bid: sim} - giu song doi tuong mo phong cua khoi TAG/tram giua cac lan
        goi (MV cua tram la bo tich luy, khong phai cong thuc tinh thang).
    stats: dict tuy chon - dien {"steps":.., "settled": True/False} de nguoi goi bao lai.
    latch: {bid: 0/1} bo nho cua khoi F/F (S/R) - chuyen thang cho SS.simulate() moi
        buoc. Mac dinh (None) van tao mot dict RIENG cho lan chay nay, de chot it nhat
        cung nho duoc xuyen cac buoc trong cung mot lan chay; truyen dict cua minh vao
        neu muon chot con song sau khi run() ket thuc (giao dien dang lam vay).
    freeze_tmr: DONG BANG dong ho cua khoi timer - chay ca vong lap voi dt=0 RIENG cho
        nhom T. Dung khi nguoi goi chi muon "giai lai mach cho on dinh" sau khi doi 1 dau
        vao: thoi gian THAT chua troi giay nao nen delay khong duoc phep tu tieu di. Van
        goi _step_timer (chu khong bo qua) de cac buoc TUC THOI van chay dung: T=0 len
        ngay, DT thay dau vao len thi bat ngay, PO nhan suon len la phat xung.
        Cung dong bang dong ho NAM TRONG than lenh khoi tram (TON, FDT) - xem
        DefSim.freeze_tmr.
    """
    _MD.dung_db(db)          # chon bo than lenh DEF theo CAD_CPU.CPUTYPE
    dig_env = dig_env or {}
    ana_env = ana_env or {}
    if latch is None:
        latch = {}
    blocks = _dyn_blocks(db, sheet, overrides, sim_cache=sim_cache,
                         freeze_tmr=freeze_tmr)
    for b in blocks:
        if b["kind"] == "S":
            b["sim"].dt = dt                     # dong bo dt nguoi dung chon cho tram
            # Tram cung co dong ho rieng trong than lenh - dong bang y het nhom T
            # (do duoc: 1417 khoi tram trong du an co TON/FDT). KHONG duoc dong bang
            # bang cach dat sim.dt = 0: FDT tinh do dai hang doi n = round(T/dt) va bo
            # qua khi dt=0 -> n tut ve 1, hang doi tre van chuyen bi cat sach.
            b["sim"].freeze_tmr = freeze_tmr
        elif b["kind"] == "T":
            # timer giu 3 thu: y (dau ra), acc (da dem bao lau), xp (dau vao buoc truoc,
            # de nhan SUON LEN). Chay tiep tu lan truoc neu nguoi goi co giu 'state'.
            st = (state or {}).get(b["bid"]) or {}
            b["y"] = st.get("y", b["y"])
            b["acc"] = st.get("acc", b["acc"])
            b["xp"] = st.get("xp", b["xp"])
        elif b["kind"] == "C":
            st = (state or {}).get(b["bid"]) or {}
            b["y"] = st.get("y", b["y"])          # so sanh co tre: nho trang thai BAT/TAT
        else:
            st = (state or {}).get(b["bid"])
            b["state"] = st["s"] if st else b.get("init", 0.0)
            b["xprev"] = st.get("xprev") if st else None
            if b["kind"] == "Q":
                b["q"] = list(st["q"]) if (st and st.get("q")) else None
            elif b["kind"] == "G":
                b["w"] = st.get("w", b["w"]) if st else b["w"]
    hist = defaultdict(list)
    record = record or []
    val = {}

    def _num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    # Net DAU RA cua khoi dong: phai LOAI khoi dig_env truoc khi simulate. Cac net nay
    # bi coi la "dau vao" luc mo sheet (khoi khong co mo hinh tinh) nen da bi gieo mac
    # dinh 0 vao dig_env - ma trong simulate() thi overrides(digital) THANG analog, nen
    # so 0 cu se DE LEN gia tri khoi dong vua tinh (vd Auto=1 cua tram khong bao gio
    # hien ra day '11' tren sheet - bug da gap that).
    dynouts = set()
    for b in blocks:
        if b["kind"] == "S":
            dynouts.update(b["out_nets"].values())
        else:
            dynouts.add(b["out"])
    dig = {k: v for k, v in dig_env.items() if k not in dynouts}
    # Nhom T (timer) va C (so sanh HCNT) deu cho ra tin hieu SO -> ghi vao dict
    # overrides DIGITAL, nen dict do phai la BAN SAO rieng cua tung buoc.
    has_tmr = any(b["kind"] in ("T", "C") for b in blocks)

    def _snap():
        """Anh chup trang thai moi khoi dong - de biet da het thay doi hay chua."""
        o = []
        for b in blocks:
            if b["kind"] == "S":
                o.extend(b["last_out"].get(nm) for nm in sorted(b["out_nets"]))
            elif b["kind"] == "T":
                o.append(b["y"])
                o.append(b["acc"])
            elif b["kind"] == "C":
                o.append(b["y"])
            else:
                o.append(b["state"])
        return o

    def _same(a, b_):
        if a is None or len(a) != len(b_):
            return False
        for x, y in zip(a, b_):
            if not (_num(x) and _num(y)):
                if x != y:
                    return False
                continue
            if abs(x - y) > 1e-6 * max(1.0, abs(x), abs(y)):
                return False
        return True

    prev_snap, quiet, done = None, 0, 0
    for _i in range(nsteps + 1):
        done += 1
        aov = dict(ana_env)
        dov = dict(dig) if has_tmr else dig
        for b in blocks:
            if b["kind"] == "S":
                for nm, net in b["out_nets"].items():
                    aov[net] = b["last_out"].get(nm, 0.0)
            elif b["kind"] in ("T", "C"):
                # Dau ra timer la tin hieu SO nen phai vao dict overrides DIGITAL: trong
                # simulate() thi overrides(digital) THANG analog, bo vao aov se bi chinh
                # dig (con giu so 0 gieo luc mo sheet) de len va timer khong bao gio hien.
                dov[b["out"]] = b["y"]
            else:
                aov[b["out"]] = b["state"]       # dau ra khoi dong = trang thai hien tai
        val, _it = SS.simulate(db, sheet, dov, aov, latch=latch)
        for n in record:
            hist[n].append(val.get(n))
        if _i >= nsteps:
            # Vong CUOI chi DOC lai gia tri sau buoc tien truoc do roi dung. Truoc day
            # vong nao cung tien -> chay nsteps+1 buoc tien nhung 'val' tra ve lai la anh
            # chup TRUOC buoc cuoi, nen man hinh luon cham dung 1 dt so voi 'state' da
            # luu. Do duoc: khoi DI dat T=1,0s, dt=0,5s chi len 1 o dong ho t=1,5s.
            # Bo buoc tien thua nay thi val, hist[-1] va state khop nhau -> DI len dung
            # o t=T (nguoi goi phai truyen nsteps = so buoc dt that su muon tien).
            break
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
                for opname, opval in b.get("forced_ops", {}).items():
                    sim.ops[opname] = opval       # nut vat ly tren tram (vd AUT = OPS_IN5)
                b["last_out"] = sim.step()
                continue
            if b["kind"] == "T":
                _step_timer(b, val.get(b["x"]), val, 0.0 if freeze_tmr else dt)
                continue
            x = val.get(b["x"]) if b.get("x") else None
            sw = val.get(b["sw"]) if b["sw"] else None
            if not _num(x) and not (b["kind"] == "I" and sw == 1):
                continue                         # tri X chua ro; rieng che do bam T thi khong can X
            if b["kind"] == "I":                 # tich phan co gioi han (manual P-128)
                _step_integ(b, x, sw, val, dt, _num)
            elif b["kind"] == "L":               # loc tre bac nhat: bam theo x, tre T
                # Sach macro trang P-87 (bang "SW / Output Y" cua LAG1_I):
                #   SW = 1 -> Y = 1/(1+T1*s) * X   (AP DUNG loc tre)
                #   SW = 0 -> Y = X                (BO QUA loc tre)
                # Truoc day code lam NGUOC (chi loc khi sw != 1) nen 29 khoi
                # 4036/4037/4038 cua du an - ca 29 deu CO noi day chan SW - deu chay sai
                # chieu. Khoi khong co chan SW (403A/403B, 313 khoi) cho sw = None nen
                # van loc nhu cu.
                if sw == 0:
                    b["state"] = x
                else:
                    T = b["ti"] if b["ti"] else 1e-6
                    if b.get("tnet"):            # ban "T:input": hang so thoi gian den tu day
                        tv = val.get(b["tnet"])
                        if _num(tv) and tv > 0:
                            T = tv
                    a = 1.0 - _exp(-dt / T)      # he so chinh xac, on dinh moi dt
                    b["state"] += (x - b["state"]) * a
            elif b["kind"] == "Q":               # tre thuan: hang doi n buoc
                _step_delay(b, x, sw, dt)
            elif b["kind"] == "C":               # so sanh co tre: ra 0/1
                _step_cmp(b, x)
            elif b["kind"] == "G":               # lead/lag
                _step_llg(b, x, sw, val, dt, _num)
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
        if settle:
            cur = _snap()
            quiet = quiet + 1 if _same(prev_snap, cur) else 0
            prev_snap = cur
            if quiet >= settle:
                break
    if state is not None:
        for b in blocks:
            if b["kind"] == "T":
                state[b["bid"]] = {"y": b["y"], "acc": b["acc"], "xp": b["xp"]}
            elif b["kind"] == "C":
                state[b["bid"]] = {"y": b["y"]}
            elif b["kind"] != "S":
                st = {"s": b["state"], "xprev": b["xprev"]}
                if b["kind"] == "Q":
                    st["q"] = list(b["q"] or [])
                elif b["kind"] == "G":
                    st["w"] = b["w"]
                state[b["bid"]] = st
    if stats is not None:
        stats["steps"] = done
        stats["settled"] = bool(settle and quiet >= settle)
    return val, dict(hist), blocks
