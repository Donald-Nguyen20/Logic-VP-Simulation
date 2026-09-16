# -*- coding: utf-8 -*-
"""So do KHOI CHUC NANG noi cua mot macro, dung cho cua so Help.

Vi sao khong noi rong core/block_logic.py: module do chi doc 7 lenh logic thuan
(A/OR/OUT/LH/XO/MV1/FF-S) va cat ban ve o 14 lenh - vua dung cho ho cong nho, va 69 ma
dang ve dep bang no. Ho tram van hanh ma nguoi dung hoi (820E MV, 820D MV-POS, 820C SV,
820F MV-FF-POS) dai 120-195 lenh va gan mot nua la lenh SO HOC (F*, F/, FUL, FITG,
TON...). Noi rong module kia se doi ban ve cua 69 ma dang tot, nen tach rieng o day.

Bo lenh doc duoc = DUNG bo lenh core/def_sim.py chay that. Moi nhanh trong _lenh() la
ban sao cau truc cua def_sim.step(); doi ben do thi phai doi ben nay. Gap lenh ngoai bo
do thi BO CA BAN VE va noi ten lenh ra - ve mot nua roi de nguoi doc tuong la day du
con nguy hiem hon khong ve gi. Cu the: ho lenh TODEN kieu cu (UL, LL, ITG, NEG, CP+,
DIF, ROT...) chua co trong def_sim nen o day cung khong ve.

Ca ma duoc ve TRON MOT BAN, khong cat theo tung chan ra: cua so Help mo toan man hinh
nen du cho (ban rong nhat la 820D/820F 3.924px). Cat ra thi cac nhanh dung chung nut
nhin nhu doc lap, ma dung chung nut moi la thu can thay.
"""
from __future__ import annotations
import re

from . import macro_def as MD
from .help_i18n import tr

# 'D0001' -> chan 1. Chu thuong o vi tri thu hai ('Dw001', 'Rf005') khong khop nen
# thanh ghi lam viec khong bi lan voi chan.
_PIN = re.compile(r"^([DXR])(\d{3,4})$")
_CNT = re.compile(r"^CNT_(IN|OUT)\d*\((\d+)\)$")
_PRM = re.compile(r"^PRM_(\d+)$")
_SO = re.compile(r"^-?\d+(\.\d+)?$")
_HEX = re.compile(r"^-?[0-9A-F]+H$")
# 'Rf003-2' va 'Rf003' la CUNG mot o nho: def_sim cat duoi bang o[3].split("-")[0] khi
# chay FITG/FDT. Khong cat o day thi bo tich phan cua 4057/820E dut lam doi.
_DUOI = re.compile(r"^([A-Za-z]\w*)-\d+$")

# Gia tri he thong cua hang, def_sim._get_raw() cap: nhip quet va so vong / giay-phut.
_HE_THONG = {"Ftime": "scan time", "Bsec_fc": "scans per second",
             "Bmin_c": "scans per minute", "Fsec_fc": "scans per second"}

# ---------------------------------------------------------------------------
# Bang lenh SO HOC / HAM. Moi dong:
#   ma_lenh: (chi so toan hang NGUON, vai tro tung nguon, chi so toan hang DICH,
#             nhan tren hop, dong chu nho duoi nhan, co chiu dieu kien khong)
# "chiu dieu kien" = def_sim goi _cho_ghi() truoc khi ghi: dieu kien dang tich luy sai
# thi o dich GIU NGUYEN tri cu, tuc la mot cai chuyen mach chu khong phai bo qua.
# ---------------------------------------------------------------------------
_HAM = {
    "F+":   ((0, 1), ("a", "b"),        (2,), "ADD",        "a + b",            True),
    "F-":   ((0, 1), ("a", "b"),        (2,), "SUBTRACT",   "a - b",            True),
    "F*":   ((0, 1), ("a", "b"),        (2,), "MULTIPLY",   "a x b",            True),
    "F/":   ((0, 1), ("a", "b"),        (2,), "DIVIDE",     "a / b",            True),
    "FABS": ((0,),   ("a",),            (1,), "ABSOLUTE",   "| a |",            True),
    "FNEG": ((0,),   ("a",),            (1,), "NEGATE",     "- a",              True),
    "FUL":  ((0, 1), ("a", "lim"),      (2,), "HIGH LIMIT", "min(a, lim)",      True),
    "FLL":  ((0, 1), ("a", "lim"),      (2,), "LOW LIMIT",  "max(a, lim)",      True),
    "CFB":  ((0,),   ("a",),            (1,), "CONVERT",    "real -> integer",  True),
    "CBF":  ((0,),   ("a",),            (1,), "CONVERT",    "integer -> real",  True),
    "AR":   ((0, 1), ("a", "mask"),     (2,), "BIT AND",    "a AND mask",       False),
    "FITG": ((0, 1, 2), ("x", "run", "Ti"), (3,), "INTEGRATE", "adds x each scan", False),
    "FCP+": ((0, 1, 2), ("x", "on", "off"), (3,), "COMPARE HI",
             "on x>=on, off x<off", False),
    "FCP-": ((0, 1, 2), ("x", "on", "off"), (3,), "COMPARE LO",
             "on x<=on, off x>off", False),
    "FDLM": ((0, 1, 2, 3), ("tgt", "run", "up", "dn"), (4,), "RATE LIMIT",
             "slope limited ramp", False),
    "FDT":  ((0, 1, 2), ("x", "run", "T"), (4,), "DEAD TIME", "x delayed by T", False),
}

# TON/TONL viet nhieu o cung mot luc nen khong nhet vua bang tren.
_TON = {
    "TON":  ((0,),   ("T",),            (1, 2), "ON DELAY", "output 1 after T"),
    "TONL": ((0, 1), ("min", "T"),      (2, 3, 4), "ON DELAY", "T in minutes"),
}

# Chan tren so hop cua MOT ban ve (ca ma, khong cat). Ma to nhat do duoc tren 21 db la
# 8201 voi 72 hop, nen nguong nay khong loai bo ma that nao - no chi de mot ma phinh ra
# den muc khong ai doc noi.
MAX_NUT = 184

# Chuoi bao nhieu nhanh tro len thi gom lai thanh MOT hop nhieu duong. Bo ky hieu cua
# hang chi co cong tac HAI duong (ASW), nen chuoi hai nhanh de nguyen la ve duoc bang
# dung hai o cong tac noi tiep - giong het to giay cua hang - con gom lai thi phai ve
# mot hop chu nhat co tieu de, la hinh khong co trong bo ky hieu. Do tren 21 db, 62 ma
# ve duoc: 14 chuoi 1 nhanh, 15 chuoi 2 nhanh, 1 chuoi 5 nhanh (8214) - ve het bang
# cong tac chi lam 8214 rong them 223px va khong them muc nao. Nguong 7 giu dung cho
# truong hop bang chu thich noi toi: 7-10 lenh FMV1 lien tiep vao cung mot o, luc do
# chuoi cong tac moi keo ban ve dai them gan chuc cot.
_MUX_GOP = 7


# ---------------------------------------------------------------- doc than lenh
_BODY = {}


def _bang_than():
    """{symbol: [dong lenh]} gop tu moi thu muc DEF, doc mot lan roi nho.

    _than() cua block_logic.py doc lai file moi lan goi. O day mot ma co the phai hoi
    nhieu lan (draw_mode, roi outputs, roi tung chan ra) nen phai nho, khong thi moi
    lan mo Help lai quet 12 file DEF."""
    if _BODY:
        return _BODY
    for tag, toden in MD.find_all_def_files():
        for f in (tag, toden):
            if not f:
                continue
            for k, v in MD.read_bodies(f).items():
                _BODY.setdefault(k, v)
    return _BODY


def _than(code):
    """[dong lenh] cua macro, hoac None."""
    sym = MD.symbol_of(code)
    if not sym:
        return None
    b = _bang_than()
    return b.get(sym) or b.get(MD._bo_tien_to(sym))


# ---------------------------------------------------------------- dung do thi
class _Doc:
    """Chay than lenh mot luot, sinh DO THI thay vi sinh gia tri.

    Cau truc cua chay() bam theo def_sim.step(): cung thu tu nhanh, cung dieu kien do
    dai toan hang, cung cho goi _cho_ghi(). Chi khac cho: def_sim ghi mot con so vao o
    nho, con day ghi TEN MOT NUT vao o nho do."""

    def __init__(self, code):
        p = MD.pins_of(code) or {}
        self.pin_in = p.get("in") or {}
        self.pin_out = p.get("out") or {}
        self.npin = len(self.pin_in) + len(self.pin_out)
        self.nodes = []
        self.byid = {}
        self.alias = {}       # ten o nho -> nguon dang giu gia tri
        self.outs = {}        # so chan ra -> nguon
        self.chot = {}        # ten o nho -> id nut SR do SET/CL dung nen
        self.acc = None
        self.rung = False
        self.raw = []
        self.cua_rung = set()   # nut vua sinh trong rung dang chay, de gop cong
        self.n = 0
        self.bad = None

    # ---------- tien ich ----------
    def _new(self, op, ins, **kw):
        self.n += 1
        nid = "n%d" % self.n
        # "ma": ma lenh TODEN goc (F+, FUL, TON...). Ban ve chon KY HIEU CUA HANG theo
        # ma nay, nen no phai di theo nut chu khong chi nam trong nhan chu tieng Anh.
        nd = {"id": nid, "op": op, "ins": list(ins), "nhan": "", "phu": "", "ma": ""}
        nd.update(kw)
        self.nodes.append(nd)
        self.byid[nid] = nd
        self.cua_rung.add(nid)
        return nid

    def _o(self, tok):
        """Bo duoi '-2' de 'Rf003-2' va 'Rf003' tro cung mot o nho."""
        m = _DUOI.match(tok)
        return m.group(1) if m else tok

    def _chan(self, tok):
        """Toan hang TODEN -> ('in'|'out', so_chan) hoac ('prm', so) hoac None.

        Quy tac giai ma lay nguyen cua def_sim._chan(): so <= tong so chan la SO CHAN,
        lon hon la tham so thu (so - tong so chan)."""
        m = _PIN.match(tok)
        if not m:
            return None
        n = int(m.group(2))
        if n > self.npin:
            return ("prm", n - self.npin)
        if n in self.pin_in:
            return ("in", n)
        if n in self.pin_out:
            return ("out", n)
        return None

    def _base(self, tok):
        """Token -> ten nguon de noi day."""
        tok = self._o(tok.strip())
        m = _CNT.match(tok)
        if m:
            return "%s:%s" % ("pin" if m.group(1) == "IN" else "out", m.group(2))
        m = _PRM.match(tok)
        if m:
            # def_sim: PRM_n doc PARAMNO n+1. Nguoi dung nhin bang tham so nen phai ghi
            # dung so cua bang do, khong thi ho do so nay voi bang kia khong khop.
            return "par:%d" % (int(m.group(1)) + 1)
        ch = self._chan(tok)
        if ch:
            return {"in": "pin:%d", "out": "out:%d", "prm": "par:%d"}[ch[0]] % ch[1]
        if tok in self.alias:
            return self.alias[tok]
        if tok in _HE_THONG:
            return "sys:%s" % tok
        if tok.startswith("OPS_") or tok.startswith("OS_"):
            return "ops:%s" % tok
        if _SO.match(tok) or _HEX.match(tok):
            return "const:%s" % tok
        return "reg:%s" % tok

    def _res(self, tok):
        """Nhu _base nhung dau '-' o dau thanh mot cong dao."""
        tok = tok.strip()
        if tok.startswith("-"):
            return self._new("NOT", [("in", self._base(tok[1:]))])
        return self._base(tok)

    def _clear(self):
        self.acc = None
        self.rung = False
        self.raw = []
        self.cua_rung = set()

    def _ghi(self, dst, node):
        """Dat ket qua vao o nho, va neu o do la chan ra thi ghi luon ra bang chan."""
        dst = self._o(dst)
        self.alias[dst] = node
        m = _CNT.match(dst)
        if m and m.group(1) == "OUT":
            self.outs[int(m.group(2))] = node
            return
        ch = self._chan(dst)
        if ch and ch[0] == "out":
            self.outs[ch[1]] = node

    def _ten_dich(self, tok):
        """Ten o nho ma hang ghi ket qua vao, chi khi do la THANH GHI TRONG.

        Ghi kem ten nay duoi hop de nguoi doc doi chieu nguoc duoc voi than lenh trong
        DEF; chan ra thi da co nhan ben phai roi nen khong lap lai."""
        tok = self._o(tok.strip())
        return "" if (self._chan(tok) or _CNT.match(tok) or _PRM.match(tok)) else tok

    def _dieu_kien(self, dst, node):
        """Lenh so hoc chiu dieu kien: dieu kien sai thi o dich giu tri cu.

        def_sim._cho_ghi() bo qua phep ghi, tuc o nho van la gia tri vong truoc. Ve dung
        y do phai la mot chuyen mach 2 duong chu khong phai 'khong co gi' - bo qua thi
        ban ve mat han cap if/else ma hang viet cho 8214 DUAL va ca ho tram MV."""
        if self.acc is None:
            return node
        cu = self.alias.get(self._o(dst))
        return self._new("MUX", [("if", self.acc), ("then", node),
                                 ("else", cu if cu else "const:0")])

    # ---------- tung lenh ----------
    def _bool(self, op, toks):
        if not self.rung:
            self.acc = None
            self.raw = []
            self.rung = True
        self.raw.append((op, list(toks)))
        srcs = [self._res(t) for t in toks]
        if not srcs:
            return
        kind = "OR" if op == "OR" else "AND"
        if self.acc is None:
            self.acc = (srcs[0] if len(srcs) == 1
                        else self._new(kind, [("in", s) for s in srcs]))
        elif (self.acc in self.cua_rung and self.byid[self.acc]["op"] == kind):
            # 'A a / A b / A c' la AND(AND(a,b),c), dung y het mot cong AND ba dau vao.
            # Ve thanh chuoi cong hai dau vao thi ban ve sau them ba cot ma khong noi
            # them dieu gi - ho tram co rung dai toi 8 buoc nen khac han ve be ngang.
            self.byid[self.acc]["ins"].extend(("in", s) for s in srcs)
        else:
            self.acc = self._new(kind, [("in", self.acc)] + [("in", s) for s in srcs])

    def _uu_tien(self, target):
        """Chot tu giu uu tien SET hay RESET, doc theo BUOC CUOI cua rung.

        Giong het core/block_logic._uu_tien(): 4011 FLIP1 viet xoa sau cung nen RESET
        thang, 40BB FLIP2 viet dat sau cung nen SET thang. Doc theo thu tu lenh chu
        khong doan theo ten khoi."""
        for op, toks in reversed(self.raw):
            con = [t for t in toks if self._o(t.lstrip("-")) != target]
            if not con:
                continue
            if op == "OR" and any(not t.startswith("-") for t in con):
                return "S"
            if op == "A" and all(t.startswith("-") for t in con):
                return "R"
            return "S" if op == "OR" else "R"
        return "R"

    def _out(self, target):
        """OUT / LH: ket qua dieu kien vao o nho. Co tu tham chieu -> chot S/R."""
        target = self._o(target)
        tu_giu = any(self._o(t.lstrip("-")) == target
                     for _op, toks in self.raw for t in toks)
        if tu_giu:
            dat, xoa = [], []
            for _op, toks in self.raw:
                for t in toks:
                    b = self._o(t.lstrip("-"))
                    if b == target:
                        continue          # nhanh hoi tiep, khong phai dau vao that
                    (xoa if t.startswith("-") else dat).append(b)
            node = self._new("SR",
                             [("S", self._base(s)) for s in dat]
                             + [("R", self._base(r)) for r in xoa],
                             prio=self._uu_tien(target))
        else:
            node = self.acc if self.acc is not None else "const:0"
        self._ghi(target, node)
        self._clear()

    def _mv(self, op, o):
        """MV1 / FMV1: chep gia tri. FMV1 chiu dieu kien -> chuyen mach 2 duong."""
        val = self._base(o[0])
        dst = self._o(o[1])
        node = val if op == "MV1" else self._dieu_kien(dst, val)
        self._ghi(dst, node)
        self._clear()

    def _set_cl(self, op, target):
        """SET / CL: dat hoac xoa mot bit theo dieu kien - ca cap la MOT cai chot.

        Ve rieng moi lenh mot nut thi lenh sau de len lenh truoc va ban ve chi con
        nhanh xoa. Nen gom vao mot nut SR theo dung ten o nho; lenh nao dung SAU trong
        than lenh thi ben do thang khi ca hai cung dung, y nhu def_sim chay tuan tu."""
        target = self._o(target)
        vai = "S" if op == "SET" else "R"
        nid = self.chot.get(target)
        if nid is None or nid not in self.byid:
            nid = self._new("SR", [], prio=vai)
            self.chot[target] = nid
        self.byid[nid]["ins"].append((vai, self.acc or "const:1"))
        self.byid[nid]["prio"] = vai
        self._ghi(target, nid)
        self._clear()

    def _ham(self, op, o):
        """Mot lenh so hoc / ham -> mot hop chuc nang."""
        isrc, vai, idst, nhan, phu, theo_dk = _HAM[op]
        if len(o) <= max(idst + isrc):
            self.bad = op
            return
        ins = [(vai[k], self._base(o[i])) for k, i in enumerate(isrc)]
        node = self._new("FN", ins, ma=op, nhan=nhan, phu=tr(phu),
                         dich=self._ten_dich(o[idst[0]]))
        if op == "AR":
            # def_sim: AR ghi ket qua VA dat luon co dieu kien (khac 0 = dung), roi
            # KHONG xoa rung. Vi the 'AR PRM_2,0001H,Rw001 / OUT Dw014' doc duoc bit 0
            # cua tham so 2. Bo cho nay thi moi khoi dung AR mat dieu kien.
            self._ghi(o[idst[0]], node)
            self.acc = node
            self.rung = False
            return
        if theo_dk:
            node = self._dieu_kien(o[idst[0]], node)
        self._ghi(o[idst[0]], node)
        self._clear()

    def _timer(self, op, o):
        """TON / TONL: dieu kien dang tich luy chinh la chan RUN cua bo dinh thi."""
        isrc, vai, idst, nhan, phu = _TON[op]
        if len(o) <= max(idst + isrc):
            self.bad = op
            return
        ins = [("run", self.acc if self.acc is not None else "const:1")]
        ins += [(vai[k], self._base(o[i])) for k, i in enumerate(isrc)]
        node = self._new("FN", ins, ma=op, nhan=nhan, phu=tr(phu),
                         dich=self._ten_dich(o[idst[0]]))
        # Bo dinh thi ghi nhieu o cung luc (so giay da dem + bit da du gio). Ca hai deu
        # la dau ra cua CUNG mot bo nen tro chung mot nut - dung nhu mot khoi timer that.
        for i in idst:
            self._ghi(o[i], node)
        self._clear()

    def _xor(self, o):
        node = self._new("XOR", [("in", self._base(o[0])), ("in", self._base(o[1]))])
        self._ghi(o[2], node)
        self._clear()

    # ---------- chay ----------
    def chay(self, instrs):
        for op, o in instrs:
            if op in ("A", "OR"):
                self._bool(op, o)
            elif op in ("OUT", "LH") and o:
                self._out(o[0])
            elif op in ("FMV1", "MV1") and len(o) >= 2:
                self._mv(op, o)
            elif op in ("SET", "CL") and o:
                self._set_cl(op, o[0])
            elif op == "XOR" and len(o) >= 3:
                self._xor(o)
            elif op in _TON:
                self._timer(op, o)
            elif op in _HAM:
                self._ham(op, o)
            else:
                self.bad = op
            if self.bad:
                return self
        return self

    # ---------- don dep ----------
    def _gon_mux(self):
        """Chuoi chuyen mach ghi vao CUNG mot o nho -> mot hop chon nhieu duong.

        Ho tram van hanh viet 7-10 lenh FMV1 lien tiep vao cung mot o (moi lenh mot
        dieu kien): ve rieng tung cai thi ban ve dai ra 10 cot va nguoi doc phai tu lan
        nguoc moi hieu. Gop lai thi doc thang duoc 'dieu kien nao dung thi lay duong
        do'. Lenh viet SAU de len lenh viet truoc nen nhanh cang ve sau cang uu tien -
        khi gom phai dao lai de nhanh manh nhat nam tren cung."""
        dung = {}
        for b in self.nodes:
            for _r, s in b["ins"]:
                dung[s] = dung.get(s, 0) + 1
        for s in self.outs.values():
            dung[s] = dung.get(s, 0) + 1

        for b in self.nodes:
            if b["op"] != "MUX" or b.get("gop"):
                continue
            nhanh, xich = [], []
            cur = b
            while True:
                ins = dict((r, v) for r, v in cur["ins"])
                nhanh.append((ins.get("if"), ins.get("then")))
                sau = ins.get("else") or "const:0"
                nd = self.byid.get(sau)
                # Chi nuot nhanh duoi khi no CHI phuc vu cai nay - bi cho khac dung nua
                # thi no la mot gia tri rieng, gop vao la ve sai duong day.
                if nd is None or nd["op"] != "MUX" or dung.get(sau, 0) != 1:
                    break
                xich.append(nd)
                cur = nd
            if len(nhanh) < _MUX_GOP:
                continue
            for nd in xich:                         # chi danh dau khi that su co gop
                nd["gop"] = True
            ins = dict((r, v) for r, v in cur["ins"])
            mac = ins.get("else") or "const:0"
            moi = []
            for c, v in nhanh:                      # da theo thu tu uu tien giam dan
                moi.append(("if", c))
                moi.append(("then", v))
            moi.append(("else", mac))
            b["ins"] = moi
        self.nodes = [b for b in self.nodes if not b.get("gop")]
        self.byid = {b["id"]: b for b in self.nodes}

    def _noi_thang(self):
        """Moi chan ra thanh mot o 'DIRECT LINK' de ban ve khong bi trong."""
        for no in sorted(self.outs):
            src = self.outs[no]
            self.outs[no] = self._new("FN", [("in", src)], nhan="DIRECT LINK",
                                      phu=tr("output follows input"), dich="")
        self.byid = {b["id"]: b for b in self.nodes}

    def _cat_nut_chet(self):
        giu, ngan = set(), list(self.outs.values())
        while ngan:
            s = ngan.pop()
            if s in giu or s not in self.byid:
                continue
            giu.add(s)
            ngan.extend(src for _r, src in self.byid[s]["ins"])
        self.nodes = [b for b in self.nodes if b["id"] in giu]
        self.byid = {b["id"]: b for b in self.nodes}


# ---------------------------------------------------------------- API
def _rong():
    return {"ok": False, "why": "", "code": "", "nlenh": 0, "nodes": [], "outs": {},
            "pin_in": {}, "pin_out": {}}


def fbd_graph(code):
    """So do khoi chuc nang cua 1 ma khoi, hoac ly do khong ve duoc.

    -> {"ok","why","code","nlenh","nodes","outs","pin_in","pin_out"}
    Nut: {"id","op","ins":[(vai,nguon)],"nhan","phu"}; op thuoc
    AND/OR/NOT/XOR/SR/MUX/FN. Nguon: pin:N, out:N, par:N, ops:TEN, sys:TEN,
    const:X, reg:TEN, hoac id cua mot nut khac.
    """
    ket = _rong()
    ket["code"] = (code or "").upper()
    than = _than(code)
    if than is None:
        if not MD.find_all_def_files():
            ket["why"] = (tr("The vendor DEF folder was not found on this machine, so the "
                          "internal logic of this block cannot be read here."))
        else:
            ket["why"] = (tr("This macro has no logic body in the vendor DEF files, so "
                          "there is nothing to redraw."))
        return ket
    instrs = MD.parse_body(than)
    ket["nlenh"] = len(instrs)
    if not instrs:
        ket["why"] = tr("The vendor DEF holds no logic body for this macro.")
        return ket

    d = _Doc(code).chay(instrs)
    if d.bad:
        ket["why"] = (tr("The vendor logic body uses '%s', which this diagram cannot draw "
                      "faithfully yet.") % d.bad)
        return ket
    if not d.outs:
        ket["why"] = tr("The vendor logic body drives no output pin of this block.")
        return ket
    d._gon_mux()
    d._cat_nut_chet()
    if not d.nodes:
        # Than lenh chi la mot phep chep ('A D0001 / OUT D0002' hoac 'MV1 X0001,X0002').
        # Van ve, bang mot o duy nhat: cau tra loi "khoi nay chi dan thang gia tri qua"
        # la mot cau tra loi that, dang gia hon o Help trong kem dong chu chung chung.
        d._noi_thang()
    ket.update(ok=True, nodes=d.nodes, outs=d.outs,
               pin_in=d.pin_in, pin_out=d.pin_out)
    return ket


def eval_bool(g, pin_vals):
    """{id_nut: 0/1} cho phan LOGIC THUAN khi biet gia tri chan vao. {} neu thieu.

    Chi de to mau day, va chi noi ve nhung nut chac chan la 0/1: hop chuc nang (so
    thuc), chot S/R (co nho) va chuyen mach lay duong so deu tra None. Doan bua o day
    thi ban ve va cua so Simulate noi hai dang khac nhau."""
    if not g.get("ok"):
        return {}
    val, byid = {}, {b["id"]: b for b in g["nodes"]}

    def lay(src, sau):
        if src.startswith("pin:"):
            return pin_vals.get(int(src[4:]))
        if src.startswith("const:"):
            try:
                return 1 if float(src[6:]) > 0.5 else 0
            except ValueError:
                return None
        if src in sau or src not in byid:
            return None
        return tinh(src, sau | {src})

    def tinh(nid, sau):
        if nid in val:
            return val[nid]
        b = byid[nid]
        op = b["op"]
        if op in ("FN", "SR"):
            val[nid] = None                 # so thuc / co nho: khong suy ra duoc
            return None
        xs = [lay(s, sau) for _r, s in b["ins"]]
        if op == "NOT":
            r = None if xs[0] is None else (0 if xs[0] else 1)
        elif op == "AND":
            r = 0 if any(x == 0 for x in xs) else (None if any(x is None for x in xs) else 1)
        elif op == "OR":
            r = 1 if any(x == 1 for x in xs) else (None if any(x is None for x in xs) else 0)
        elif op == "XOR":
            r = None if any(x is None for x in xs) else (sum(1 for x in xs if x) % 2)
        elif op == "MUX":
            # Nhanh nao co dieu kien 1 SOM NHAT thi thang (danh sach da xep uu tien
            # giam dan). Con nhanh chua biet dieu kien nam tren no thi chua ket luan duoc.
            r = None
            cho = None
            for i in range(0, len(b["ins"]) - 1, 2):
                c = lay(b["ins"][i][1], sau)
                if c is None:
                    cho = True
                    break
                if c:
                    cho = False
                    r = lay(b["ins"][i + 1][1], sau)
                    break
            if cho is None:
                r = lay(b["ins"][-1][1], sau)
            elif cho:
                r = None
        else:
            r = None
        val[nid] = r
        return r

    for nid in byid:
        tinh(nid, {nid})
    return val


_VE_DUOC = {}


def can_draw(code):
    """Ma nay co ve duoc so do khoi chuc nang khong. Nho ket qua vi describe() goi no
    cho MOI ma khong co che do ve nao khac."""
    code = (code or "").upper()
    if code not in _VE_DUOC:
        try:
            g = fbd_graph(code)
            _VE_DUOC[code] = bool(g["ok"]) and len(g["nodes"]) <= MAX_NUT
        except Exception:
            _VE_DUOC[code] = False
    return _VE_DUOC[code]
