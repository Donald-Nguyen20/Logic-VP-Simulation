# -*- coding: utf-8 -*-
"""Doc THAN LENH GOC cua hang thanh mot do thi cong logic DE VE trong cua so Help.

Vi sao khong dung thang core/macro_def.netlist_for():
  - Netlist do khong danh dau duoc ngo ra voi macro kieu TODEN (than lenh viet chan la
    'D0003' chu khong phai 'CNT_OUT(3)'), nen finalize() khong cat duoc nut chet. Do
    tren 300 ma dang dung: nhan them dang 'D000n' se cat 351 nut chet o 113 ma - nhung
    dong thoi doi netlist cua 127.764 khoi trong tinh nang "Draw internal logic" dang
    chay, nen KHONG sua ben do.
  - Netlist do dich MV1 thanh PASS, nen ca ho chuyen mach (TRANS1/2/3, TRAN-BMP: 8.283
    khoi) rut lai thanh mot day thang, mat sach phan chon nhanh.
Module nay chi phuc vu VE. Khong bo mo phong nao goi den no.

Ma chan trong than lenh: CHU CAI la kieu du lieu (D = so, X/R = thuc), 4 chu so la SO
THU TU CHAN - 'D0001' va 'X0001' deu la chan 1. Thanh ghi trung gian co chu thuong ngay
sau chu cai dau ('Dw001', 'Rf005', 'Rw002') nen khong the lan voi chan.

Ngu nghia lay tu chinh bo chay that core/def_sim.py:
  A/OR    : tich luy dieu kien (rung)
  OUT z   : z = acc, ket thuc dieu kien. Rung co tu tham chieu z -> CHOT S/R.
  LH z    : nhu OUT nhung than lenh luon viet kem vong hoi tiep -> cung ra chot S/R.
  XO b    : acc = acc XOR b
  FF/S s,r,q : chot S/R uu tien SET
  MV1/FMV1 s,d : d = s khi acc dung -> CHUYEN MACH
"""
from __future__ import annotations
import re

from . import macro_def as MD
from .help_i18n import tr

# 'D0001' -> chan 1. Chu thuong o vi tri thu hai ('Dw001') khong khop nen thanh ghi
# trung gian bi loai ngay tu day.
_PIN = re.compile(r"^([A-Z])(\d{3,4})$")
_CNT = re.compile(r"^CNT_(IN|OUT)\d*\((\d+)\)$")

# Lenh ve duoc. Gap bat ky lenh nao ngoai danh sach nay la bo ca ban ve - tha khong ve
# con hon ve mot nua roi de nguoi doc tuong la day du.
_VE_DUOC = {"A", "OR", "OUT", "LH", "XO", "MV1", "FMV1", "FF/S"}

# Than lenh dai hon nguong nay khong phai "logic noi de hieu" nua ma la ca mot chuong
# trinh (ho 82xx_TG cua tram van hanh: 85-112 lenh) - ve ra khong ai doc noi.
MAX_LENH = 14
MAX_NUT = 9


def _than(code):
    """[dong lenh] cua macro, hoac None. Thu ca ten da bo tien to nhu netlist_for lam:
    ho chuyen mach nam duoi ten 'TRA2_I' chu khong phai 'F_TRA2_I'."""
    sym = MD.symbol_of(code)
    if not sym:
        return None
    for tag, toden in MD.find_all_def_files():
        for f in (tag, toden):
            if not f:
                continue
            b = MD.read_bodies(f)
            r = b.get(sym) or b.get(MD._bo_tien_to(sym))
            if r:
                return r
    return None


class _Doc:
    """Chay than lenh mot luot, sinh do thi thay vi sinh gia tri."""

    def __init__(self, code):
        self.code = code
        pins = MD.pins_of(code) or {}
        self.pin_in = pins.get("in") or {}
        self.pin_out = pins.get("out") or {}
        self.nodes = []          # [{id, op, ins:[(vai, nguon)], prio}]
        self.byid = {}
        self.alias = {}          # ten thanh ghi -> nguon dang giu gia tri
        self.outs = {}           # so chan ra -> nguon
        self.acc = None
        self.rung = False
        self.raw = []            # (op, [token goc]) cua rung dang mo
        self.n = 0
        self.bad = None

    # ---------- tien ich ----------
    def _new(self, op, ins, **kw):
        self.n += 1
        nid = "%s%d" % (op.lower().replace("/", ""), self.n)
        nd = {"id": nid, "op": op, "ins": list(ins)}
        nd.update(kw)
        self.nodes.append(nd)
        self.byid[nid] = nd
        return nid

    def _pin_no(self, tok):
        m = _CNT.match(tok) or _PIN.match(tok)
        if not m:
            return None
        return int(m.group(2))

    def _base(self, tok):
        """Token (khong dau am) -> ten nguon de noi day."""
        n = self._pin_no(tok)
        if n is not None:
            return "pin:%d" % n
        if tok in self.alias:
            return self.alias[tok]
        return "reg:%s" % tok

    def _res(self, tok):
        tok = tok.strip()
        neg = tok.startswith("-")
        if neg:
            tok = tok[1:]
        src = self._base(tok)
        return self._new("NOT", [("in", src)]) if neg else src

    def _clear(self):
        self.acc = None
        self.rung = False
        self.raw = []

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
        else:
            self.acc = self._new(kind, [("in", self.acc)] + [("in", s) for s in srcs])

    def _xo(self, toks):
        srcs = [self._res(t) for t in toks]
        self.acc = self._new("XOR", [("in", self.acc or "const:0")]
                             + [("in", s) for s in srcs])

    def _uu_tien(self, target):
        """Chot tu giu uu tien SET hay RESET: doc theo BUOC CUOI cua rung.

        4011 FLIP1 viet 'OR Dw001,D0001 / A -D0002 / OUT Dw001' - xoa dat sau cung nen
        RESET thang; 40BB FLIP2 viet 'A -D0002,Dw001 / OR D0001 / LH Dw001' - dat sau
        cung nen SET thang. Dung thu tu nay chu khong doan theo ten khoi."""
        for op, toks in reversed(self.raw):
            con = [t for t in toks if t.lstrip("-") != target]
            if not con:
                continue
            if op == "OR" and any(not t.startswith("-") for t in con):
                return "S"
            if op == "A" and all(t.startswith("-") for t in con):
                return "R"
            return "S" if op == "OR" else "R"
        return "R"

    def _out(self, target):
        tu_giu = any(t.lstrip("-") == target
                     for _op, toks in self.raw for t in toks)
        if tu_giu:
            dat, xoa = [], []
            for _op, toks in self.raw:
                for t in toks:
                    b = t[1:] if t.startswith("-") else t
                    if b == target:
                        continue          # nhanh hoi tiep, khong phai dau vao that
                    (xoa if t.startswith("-") else dat).append(b)
            node = self._new("SR",
                             [("S", self._base(s)) for s in dat]
                             + [("R", self._base(r)) for r in xoa],
                             prio=self._uu_tien(target))
        else:
            node = self.acc if self.acc is not None else "const:0"
        self.alias[target] = node
        p = self._pin_no(target)
        if p is not None and p in self.pin_out:
            self.outs[p] = node
        self._clear()

    def _ff_s(self, o):
        if len(o) < 3:
            self.bad = "FF/S"
            return
        node = self._new("SR", [("S", self._base(o[0])), ("R", self._base(o[1]))],
                         prio="S")
        self.alias[o[2]] = node
        p = self._pin_no(o[2])
        if p is not None and p in self.pin_out:
            self.outs[p] = node
        self._clear()

    def _move(self, o):
        """MV1/FMV1 s,d: d = s KHI acc dung. Gom cac nhanh cung dich thanh 1 chuyen mach."""
        if len(o) < 2:
            self.bad = "MV1"
            return
        val, dst = self._base(o[0]), o[1]
        cond = self.acc
        cur = self.byid.get(self.alias.get(dst, ""))
        if cur is not None and cur["op"] == "SELECT":
            cur["nhanh"].append((cond, val))
            node = cur["id"]
        else:
            node = self._new("SELECT", [], nhanh=[(cond, val)])
        self.alias[dst] = node
        p = self._pin_no(dst)
        if p is not None and p in self.pin_out:
            self.outs[p] = node
        self._clear()

    # ---------- chay ----------
    def chay(self, instrs):
        for op, o in instrs:
            if op not in _VE_DUOC:
                self.bad = op
                return self
            if op in ("A", "OR"):
                self._bool(op, o)
            elif op == "XO":
                self._xo(o)
            elif op in ("OUT", "LH"):
                if o:
                    self._out(o[0])
            elif op == "FF/S":
                self._ff_s(o)
            else:
                self._move(o)
            if self.bad:
                return self
        return self

    # ---------- don dep ----------
    def _gon_select(self):
        """Chuyen mach 2 nhanh voi dieu kien nguoc nhau -> mot khoa 2 vi tri doc duoc.

        Ho TRANS viet 'A D0001 / MV1 X0002,R0004 / A -D0001 / MV1 X0003,R0004': nhanh
        thu hai dieu kien la NOT cua nhanh dau. Nhan ra cap nay thi ve duoc dung mot cai
        khoa co chan chon; khong nhan ra thi thanh 2 nut roi rac, vo nghia."""
        for nd in self.nodes:
            if nd["op"] != "SELECT":
                continue
            nh = nd.get("nhanh") or []
            if len(nh) != 2:
                self.bad = self.bad or "SELECT %d nhanh" % len(nh)
                return
            (c1, v1), (c2, v2) = nh
            n2 = self.byid.get(c2 or "")
            if not (c1 and n2 and n2["op"] == "NOT" and n2["ins"][0][1] == c1):
                self.bad = self.bad or "SELECT khong doi xung"
                return
            nd["ins"] = [("sel", c1), ("1", v1), ("0", v2)]

    def _cat_nut_chet(self):
        giu, ngan = set(), [s for s in self.outs.values()]
        while ngan:
            s = ngan.pop()
            if s in giu or s not in self.byid:
                continue
            giu.add(s)
            ngan.extend(src for _r, src in self.byid[s]["ins"])
        self.nodes = [b for b in self.nodes if b["id"] in giu]
        self.byid = {b["id"]: b for b in self.nodes}


def gate_graph(code):
    """Do thi cong logic noi cua 1 ma khoi, hoac ly do khong ve duoc.

    -> {"ok", "why", "nodes", "outs", "pin_in", "pin_out", "nlenh"}
    """
    ket = {"ok": False, "why": "", "nodes": [], "outs": {},
           "pin_in": {}, "pin_out": {}, "nlenh": 0}
    than = _than(code)
    if than is None:
        # Hai truong hop rat khac nhau: may khong co thu muc DEF, hay co DEF nhung macro
        # nay khong co trong do. Gop chung mot cau thi nguoi doc di tim file vo ich.
        if not MD.find_all_def_files():
            ket["why"] = (tr("The vendor DEF folder was not found on this machine, so the "
                          "internal logic of this block cannot be read here."))
        else:
            ket["why"] = (tr("This macro has no logic body in the vendor DEF files, so there "
                          "is nothing to redraw."))
        return ket
    instrs = MD.parse_body(than)
    ket["nlenh"] = len(instrs)
    if not instrs:
        ket["why"] = tr("The vendor DEF holds no logic body for this macro.")
        return ket
    if len(instrs) > MAX_LENH:
        ket["why"] = (tr("The vendor logic body of this block is %d instructions long - too "
                      "much to redraw as a readable gate diagram.") % len(instrs))
        return ket

    d = _Doc(code).chay(instrs)
    if not d.bad:
        d._gon_select()
    if d.bad:
        ket["why"] = (tr("The vendor logic body uses '%s', which this diagram cannot draw "
                      "faithfully yet.") % d.bad)
        return ket
    if not d.outs:
        ket["why"] = tr("The vendor logic body drives no output pin of this block.")
        return ket
    d._cat_nut_chet()
    if not d.nodes:
        ket["why"] = tr("The output of this block is wired straight through, with no gate.")
        return ket
    if len(d.nodes) > MAX_NUT:
        ket["why"] = (tr("This block expands to %d gates - too many to redraw readably here.")
                      % len(d.nodes))
        return ket
    ket.update(ok=True, nodes=d.nodes, outs=d.outs,
               pin_in=d.pin_in, pin_out=d.pin_out)
    return ket


def eval_graph(g, pin_vals):
    """Gia tri 0/1 tai tung nut khi biet gia tri cac chan vao. {} khi khong du du lieu.

    Chi de TO MAU day dang song tren ban ve. Khoi co chot S/R thi trang thai phu thuoc
    qua khu nen bo qua - khong doan bua."""
    if not g.get("ok"):
        return {}
    val, byid = {}, {b["id"]: b for b in g["nodes"]}

    def lay(src, sau):
        if src.startswith("pin:"):
            return pin_vals.get(int(src[4:]))
        if src.startswith("const:"):
            return int(src[6:])
        if src in sau or src not in byid:
            return None
        return tinh(src, sau | {src})

    def tinh(nid, sau):
        if nid in val:
            return val[nid]
        b = byid[nid]
        xs = [lay(s, sau) for _r, s in b["ins"]]
        op = b["op"]
        if op == "NOT":
            r = None if xs[0] is None else (0 if xs[0] else 1)
        elif op == "AND":
            r = 0 if any(x == 0 for x in xs) else (None if any(x is None for x in xs) else 1)
        elif op == "OR":
            r = 1 if any(x == 1 for x in xs) else (None if any(x is None for x in xs) else 0)
        elif op == "XOR":
            r = None if any(x is None for x in xs) else (sum(1 for x in xs if x) % 2)
        elif op == "SELECT":
            m = dict(zip([v for v, _s in b["ins"]], xs))
            s = m.get("sel")
            r = None if s is None else m.get("1" if s else "0")
        else:                       # SR: trang thai co nho, khong suy ra tu dau vao
            r = None
        val[nid] = r
        return r

    for nid in byid:
        tinh(nid, {nid})
    return val
