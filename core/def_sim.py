# -*- coding: utf-8 -*-
"""Bo MO PHONG KHOI TRAM chay THANG tren than lenh goc trong TAG_MCR.DEF
(nguon chuan cua phan mem T-Designer - chinh la thu nap xuong controller).

Thay cho mo hinh chep tay macro_analog.json (mo hinh do bi sai o cho chuyen mach
Auto: no lay thang CHAN MV ngoai lam dau ra, trong khi logic that dung chuyen mach
de chon DAU VAO cho bo tich phan, con dau ra LUON la bo tich phan).

Ngu nghia tap lenh (da kiem chung tren 820E):
  A/OR a,b..  : gop vao thanh ghi tich luy (acc); '-x' = NOT x
  OUT z       : z = acc, va KET THUC dieu kien (lenh FMV1 ngay sau chay vo dieu kien)
  FMV1 s,d    : neu acc dung (hoac khong con dieu kien) thi d = s  -> chuyen mach
  MV1  s,d    : d = s
  F+ F- F* F/ : phep toan so thuc, ket qua vao toan hang cuoi
  FUL x,h,y   : y = min(x,h)      FLL x,l,y : y = max(x,l)
  FITG x,en,TI,y : neu en=1 thi y += x * (dt / TI)   (TI thuong = chu ky quet -> y += x)
  TON  T,w,q  : q=1 khi acc giu 1 lien tuc >= T giay
  CFB/AR/LH/XOR/...: cac lenh phu tro (xu ly toi thieu, khong lam dut mach)
Toan hang:
  CNT_IN n(n)/CNT_OUT n(n) : chan vao/ra thu n     PRM_n : tham so (PARAMNO = n+1)
  OPS_IN/OPS_OUT/OS_*      : lenh & hien thi tu tram van hanh
  Dw/Rw/Rf                 : thanh ghi trung gian   Ftime : chu ky quet (ms)
"""
from __future__ import annotations
import re

from core import macro_def as MD

_BODIES = None
_CACHE = {}


def _bodies():
    global _BODIES
    if _BODIES is None:
        tag, _toden = MD.find_def_files()
        _BODIES = MD.read_bodies(tag) if tag else {}
    return _BODIES


def instrs_for(code):
    """[(lenh,[toan hang])] cua 1 macrocode, hoac None neu khong co than logic."""
    code = (code or "").upper()
    if code in _CACHE:
        return _CACHE[code]
    sym = MD.symbol_of(code)
    body = _bodies().get(sym) if sym else None
    out = MD.parse_body(body) if body else None
    _CACHE[code] = out
    return out


def has_def(code):
    return bool(instrs_for(code))


# tap lenh DA CAI DAT trong DefSim.step()
SUPPORTED = {
    "A", "OR", "OUT", "FMV1", "MV1", "F+", "F-", "F*", "F/", "FABS", "FNEG",
    "FUL", "FLL", "FITG", "TON", "XOR", "CFB", "AR", "SET", "CL",
    "FCP+", "FCP-", "FDLM", "FDT",
}


def unsupported_ops(code):
    """Cac lenh trong than logic ma engine CHUA cai dat (rong = mo phong duoc day du)."""
    ins = instrs_for(code)
    if not ins:
        return None
    return sorted({op for op, _o in ins} - SUPPORTED)


def can_simulate(code):
    """True neu khoi co than logic goc VA moi lenh deu da duoc cai dat."""
    u = unsupported_ops(code)
    return u is not None and not u


class DefSim:
    """Mo phong 1 khoi tram theo dung than lenh goc. Giao dien tuong thich AnalogSim:
    set_input(ten_chan, v) / set_param(ten_hoac_so, v) / step() -> {ten_chan_ra: gia tri}."""

    def __init__(self, code, dt=0.5):
        self.code = (code or "").upper()
        self.instrs = instrs_for(self.code) or []
        self.dt = float(dt)
        self.pins = MD.pins_of(self.code)          # {'in':{n:ten}, 'out':{n:ten}}
        self._name2in = {nm: n for n, nm in self.pins.get("in", {}).items() if nm}
        self._name2out = {nm: n for n, nm in self.pins.get("out", {}).items() if nm}
        self.inputs = {}          # {ten_chan: gia tri}
        self.params = {}          # {ten_hoac_'P7': gia tri}
        self._prm = {}            # {paramno(int): gia tri}
        self.state = {}           # thanh ghi noi (Dw/Rw/Rf) - giu qua cac buoc
        self.ops = {}             # {OPS_IN2: 1} - nut Inc/Dec... tren tram van hanh
        self.out = {}             # {ten_chan_ra: gia tri}
        # TI cho bo tich phan noi. Logic GOC dat TI = chu ky quet (Rf001 = Ftime/1000)
        # nen moi vong quet cong THANG dau vao -> MV chay rat nhanh khi sai lech lon.
        # Dat ti_override = so giay de lam cham cho de quan sat: moi vong cong
        # dau_vao * dt / TI  (TI = so giay de di het mot luong bang dau vao).
        self.ti_override = None
        self._tmr = {}
        self._dt_buf = {}         # bo dem cho lenh tre van chuyen FDT
        # Dong ho trong than lenh (TON, FDT) chi duoc chay khi THOI GIAN THAT troi. Khi
        # nguoi dung chi doi 1 dau vao roi giai lai cho mach on dinh (settle chay hang
        # tram vong) ma van cho dong ho chay thi delay bi an sach - bao dong cai tre 30s
        # keu ngay lap tuc. sheet_dyn.run() bat co nay o duong "doi dau vao".
        self.freeze_tmr = False
        self._acc = None
        self._rung = False
        try:
            from core.block_params import param_names
            self._pname2no = {v: k for k, v in param_names(self.code).items()}
        except Exception:
            self._pname2no = {}

    # ---------- cai dat ----------
    def set_input(self, name, val):
        self.inputs[name] = float(val)

    def set_param(self, name, val):
        """name co the la ten (MSR, ULD...) hoac so thu tu PARAMNO."""
        try:
            v = float(val)
        except (TypeError, ValueError):
            return
        self.params[name] = v
        no = None
        if isinstance(name, int) or (isinstance(name, str) and str(name).isdigit()):
            no = int(name)
        elif name in self._pname2no:
            no = self._pname2no[name]
        if no is not None:
            self._prm[no] = v

    def set_params_by_no(self, pm):
        """pm = {paramno(str/int): gia tri} lay thang tu CAD_BLOCK_PARAM (da gom ca
        gia tri nguoi dung ghi de trong 'Block parameters'). Dong thoi dien vao
        self.params theo TEN (MSR, ULD...) de hop cai dat hien duoc gia tri that."""
        no2name = {v: k for k, v in self._pname2no.items()}
        for k, v in (pm or {}).items():
            try:
                no = int(k)
                val = float(v)
            except (TypeError, ValueError):
                continue
            self._prm[no] = val
            nm = no2name.get(no)
            if nm:
                self.params[nm] = val

    def integ_keys(self):
        """Ten thanh ghi giu gia tri cua cac bo TICH PHAN trong than lenh (FITG)."""
        return [o[3].split("-")[0] for op, o in self.instrs if op == "FITG" and len(o) >= 4]

    def integ_out_pins(self):
        """Ten chan RA duoc cap tu bo tich phan (VD 820E: 'FMV1 Rf008,CNT_OUT2(15)'
        -> chan 15 = 'MV'). Dung de gieo gia tri xuat phat ra dung chan."""
        keys = set(self.integ_keys())
        pins = []
        for op, o in self.instrs:
            if op in ("FMV1", "MV1") and len(o) >= 2 and o[0] in keys:
                m = re.match(r"^CNT_OUT\d*\((\d+)\)$", o[1])
                if m:
                    nm = self.pins.get("out", {}).get(int(m.group(1)))
                    if nm and nm not in pins:
                        pins.append(nm)
        return pins

    def warm_start(self, value):
        """Nap DIEM XUAT PHAT cho bo tich phan (VD MV dang la 200) thay vi bat dau tu 0.
        LUU Y: day chi la TRO GIUP MO PHONG - khoi that KHONG co chan nao de dat MV ban
        dau; MV nam trong bo nho noi va duoc giu qua cac vong quet.
        Goi SAU khi da chay >=1 vong quet (xung 'vong quet dau' da tat) roi step() them
        1 lan de day gia tri ra chan. value = so, hoac {ten_chan_ra: so}."""
        keys = self.integ_keys()
        if not keys:
            return
        if isinstance(value, dict):
            vals = [float(v) for v in value.values() if v is not None]
        else:
            try:
                vals = [float(value)]
            except (TypeError, ValueError):
                return
        if not vals:
            return
        for i, k in enumerate(keys):
            self.state[k] = vals[i] if i < len(vals) else vals[0]
        # gieo luon ra DUNG chan ra cua bo tich phan de vong quet dau tien tren sheet
        # da thay gia tri xuat phat (khong phai 0)
        if isinstance(value, dict):
            for nm, v in value.items():
                if v is not None:
                    self.out[nm] = float(v)
        else:
            for i, nm in enumerate(self.integ_out_pins()):
                self.out[nm] = vals[i] if i < len(vals) else vals[0]

    def reset(self):
        self.state = {}
        self._tmr = {}
        self.out = {}

    def input_meta(self):
        return {nm: {} for nm in self._name2in}

    # ---------- doc/ghi toan hang ----------
    def _get(self, tok):
        neg = tok.startswith("-")
        if neg:
            tok = tok[1:]
        v = self._get_raw(tok)
        return (0.0 if v > 0.5 else 1.0) if neg else v

    def _get_raw(self, tok):
        m = re.match(r"^CNT_IN\d*\((\d+)\)$", tok)
        if m:
            nm = self.pins.get("in", {}).get(int(m.group(1)))
            return float(self.inputs.get(nm, 0.0)) if nm else 0.0
        m = re.match(r"^CNT_OUT\d*\((\d+)\)$", tok)
        if m:
            nm = self.pins.get("out", {}).get(int(m.group(1)))
            return float(self.out.get(nm, 0.0)) if nm else 0.0
        m = re.match(r"^PRM_(\d+)$", tok)
        if m:
            return float(self._prm.get(int(m.group(1)) + 1, 0.0))   # PRM_n = PARAMNO n+1
        if tok == "Ftime":
            return self.dt * 1000.0
        if tok == "Bsec_fc":
            return 1.0
        if tok.startswith("OPS_") or tok.startswith("OS_"):
            return float(self.ops.get(tok, 0.0))
        if tok in self.state:
            return float(self.state[tok])
        try:
            return float(tok)
        except ValueError:
            return 0.0

    def _put(self, tok, v):
        m = re.match(r"^CNT_OUT\d*\((\d+)\)$", tok)
        if m:
            nm = self.pins.get("out", {}).get(int(m.group(1)))
            if nm:
                self.out[nm] = v
            return
        self.state[tok] = v

    def _clear(self):
        self._acc = None
        self._rung = False

    # ---------- 1 vong quet ----------
    def step(self):
        ins = self.instrs
        self._clear()
        i = 0
        while i < len(ins):
            op, o = ins[i]

            if op in ("A", "OR"):
                vals = [self._get(x) for x in o]
                cur = (min(vals) if op == "A" else max(vals)) if len(vals) > 1 else (
                    vals[0] if vals else 0.0)
                cur = 1.0 if cur > 0.5 else 0.0
                if not self._rung:
                    self._acc = cur
                    self._rung = True
                elif op == "A":
                    self._acc = 1.0 if (self._acc > 0.5 and cur > 0.5) else 0.0
                else:
                    self._acc = 1.0 if (self._acc > 0.5 or cur > 0.5) else 0.0

            elif op == "OUT" and o:
                self._put(o[0], self._acc or 0.0)
                self._clear()          # OUT ket thuc dieu kien

            elif op == "FMV1" and len(o) >= 2:
                if self._acc is None or self._acc > 0.5:
                    self._put(o[1], self._get(o[0]))
                self._clear()

            elif op == "MV1" and len(o) >= 2:
                self._put(o[1], self._get(o[0])); self._clear()

            elif op == "F/" and len(o) >= 3:
                b = self._get(o[1])
                self._put(o[2], self._get(o[0]) / b if b else 0.0); self._clear()
            elif op == "F*" and len(o) >= 3:
                self._put(o[2], self._get(o[0]) * self._get(o[1])); self._clear()
            elif op == "F-" and len(o) >= 3:
                self._put(o[2], self._get(o[0]) - self._get(o[1])); self._clear()
            elif op == "F+" and len(o) >= 3:
                self._put(o[2], self._get(o[0]) + self._get(o[1])); self._clear()
            elif op == "FABS" and len(o) >= 2:
                self._put(o[1], abs(self._get(o[0]))); self._clear()
            elif op == "FNEG" and len(o) >= 2:
                self._put(o[1], -self._get(o[0])); self._clear()

            elif op == "FUL" and len(o) >= 3:
                self._put(o[2], min(self._get(o[0]), self._get(o[1]))); self._clear()
            elif op == "FLL" and len(o) >= 3:
                self._put(o[2], max(self._get(o[0]), self._get(o[1]))); self._clear()

            elif op == "FITG" and len(o) >= 4:
                x = self._get(o[0]); en = self._get(o[1])
                ti = self.ti_override if self.ti_override else self._get(o[2])
                key = o[3].split("-")[0]
                cur = float(self.state.get(key, 0.0))
                if en > 0.5:
                    cur += x * (self.dt / ti) if ti else x
                self._put(key, cur); self._clear()

            elif op == "TON" and len(o) >= 3:
                T = self._get(o[0]); key = o[2]
                on = bool(self._acc and self._acc > 0.5)
                buoc = 0.0 if self.freeze_tmr else self.dt
                self._tmr[key] = (self._tmr.get(key, 0.0) + buoc) if on else 0.0
                self._put(key, 1.0 if (on and self._tmr[key] >= T) else 0.0)
                self._clear()

            elif op == "XOR" and len(o) >= 3:
                a = 1.0 if self._get(o[0]) > 0.5 else 0.0
                b = 1.0 if self._get(o[1]) > 0.5 else 0.0
                self._put(o[2], 1.0 if a != b else 0.0); self._clear()

            elif op == "CFB" and len(o) >= 2:
                self._put(o[1], self._get(o[0])); self._clear()

            elif op == "AR" and len(o) >= 3:
                # thu bit: work = a AND b (theo bit); acc = 1 neu khac 0
                # VD 'AR PRM_2,0001H,Rw001 / OUT Dw014' = thu bit 0 cua tham so 2
                a = int(self._get(o[0])); b = int(self._get(o[1]))
                r = a & b
                self._put(o[2], float(r))
                self._acc = 1.0 if r else 0.0
                self._rung = False

            elif op == "SET" and o:
                if self._acc is None or self._acc > 0.5:      # dat bit khi dieu kien dung
                    self._put(o[0], 1.0)
                self._clear()
            elif op == "CL" and o:
                if self._acc is None or self._acc > 0.5:      # xoa bit khi dieu kien dung
                    self._put(o[0], 0.0)
                self._clear()

            elif op in ("FCP+", "FCP-") and len(o) >= 4:
                # so sanh CO TRE (hysteresis): FCP+ x,nguong_bat,nguong_tat,bit
                #   bat khi x >= nguong_bat, tat khi x < nguong_tat, giua thi GIU nguyen
                # FCP- nguoc lai (canh bao thap)
                x = self._get(o[0]); on = self._get(o[1]); off = self._get(o[2])
                cur = float(self.state.get(o[3], 0.0))
                if op == "FCP+":
                    q = 1.0 if x >= on else (0.0 if x < off else cur)
                else:
                    q = 1.0 if x <= on else (0.0 if x > off else cur)
                self._put(o[3], q); self._clear()

            elif op == "FDLM" and len(o) >= 5:
                # han toc do doi (rate limiter): out bam theo in, moi vong quet doi toi da
                # +up / -dn (VD RLMV cua tram MV-POS)
                tgt = self._get(o[0]); en = self._get(o[1])
                up = abs(self._get(o[2])); dn = abs(self._get(o[3]))
                cur = float(self.state.get(o[4], tgt))
                if en > 0.5:
                    cur = min(tgt, cur + up) if tgt > cur else max(tgt, cur - dn)
                self._put(o[4], cur); self._clear()

            elif op == "FDT" and len(o) >= 5:
                # tre van chuyen (dead time): out = in cua T giay truoc
                x = self._get(o[0]); en = self._get(o[1]); T = self._get(o[2])
                key = o[4].split("-")[0]
                buf = self._dt_buf.setdefault(key, [])
                if not self.freeze_tmr:      # dong bang: khong day them, khong cat bot.
                    if en > 0.5:             # (dat dt=0 thi n tut ve 1 va XOA sach hang doi)
                        buf.append(x)
                    n = max(1, int(round(T / self.dt))) if self.dt else 1
                    while len(buf) > n:
                        buf.pop(0)
                self._put(key, buf[0] if buf else x); self._clear()

            else:
                self._clear()          # lenh chua ho tro: bo qua, khong lam dut mach
            i += 1
        return dict(self.out)
