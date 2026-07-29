# -*- coding: utf-8 -*-
"""Doc THAN LOGIC GOC cua macro tu file DEF cua phan mem T-Designer
(DEF/SR21E/TYPE_A_*/TAG_MCR.DEF cho macro TAG/station, TODEN.DEF cho macro thuong)
va dich sang NETLIST de dung so do logic noi.

Day la nguon CHUAN (chinh la thu nap xuong controller), khong phai doc tu hinh ve.

Ngu nghia tap lenh (dang thanh ghi tich luy - accumulator):
  A  a,b,..   : acc = (acc va) a AND b ...      ('-x' = NOT x)
  OR a,b,..   : acc = (acc hoac) a OR b ...
  OUT z       : z = acc   (acc VAN GIU de dieu kien cho lenh sau)
  FMV1 s,d    : NEU acc dung THI d = s   -> chuyen mach (SELECT)
  MV1  s,d    : d = s
  F+ a,b,c    : c = a+b     F- a,b,c : c = a-b
  F* a,b,c    : c = a*b     F/ a,b,c : c = a/b
  FUL x,h,y   : y = min(x,h)  (chan tren)     FLL x,l,y : y = max(x,l) (chan duoi)
                FUL+FLL lien tiep -> gop thanh 1 khoi CLAMP (giong manual)
  FITG x,hold,dt,y : y = tich phan x
  TON  T,w,q  : q = 1 khi acc giu 1 du T
  FABS/FNEG/XOR/CFB/AR/LH... : cac lenh khac (giu nguyen ten de xem)
Chan/tham so:
  CNT_IN n(n) / CNT_OUT n(n) : chan vao/ra thu n cua khoi (khop macro_pins)
  PRM_n      : tham so thu n     OPS_IN/OPS_OUT/OS_* : lenh & hien thi tu tram van hanh
  Dw/Rw/Rf   : thanh ghi trung gian (bit / word / so thuc)
"""
from __future__ import annotations
import os
import re
import json

_DEF_DIRS = ("TYPE_A_CPUW01", "TYPE_A_CPUW02", "TYPE_A_CPUW11", "TYPE_A_CPUW12",
             "TYPE_A_CPUX02", "TYPE_B_CPUX01")


def find_def_files(root=None):
    """Tra ve (tag_mcr_path, toden_path) neu tim thay trong thu muc DEF cua T-Designer."""
    if root is None:
        # ...\T_Designer\T_Designer_Lite\core -> ...\T_Designer
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (os.path.join(root, "DEF", "SR21E"), os.path.join(root, "T_Designer", "DEF", "SR21E")):
        for d in _DEF_DIRS:
            p = os.path.join(base, d, "TAG_MCR.DEF")
            if os.path.exists(p):
                return p, os.path.join(base, d, "TODEN.DEF")
    return None, None


def read_bodies(path):
    """{symbol: [dong lenh]} cho moi .DEF ... .DEFEND trong file."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    cur, body = None, []
    for raw in open(path, encoding="latin-1", errors="ignore"):
        line = raw.rstrip("\n").rstrip()
        if not line.strip():
            continue
        if line.startswith(".DEFEND"):        # phai kiem TRUOC .DEF (cung tien to)
            if cur:
                out[cur] = body
            cur, body = None, []
        elif line.startswith(".DEF"):
            parts = line.split()
            cur = parts[1] if len(parts) > 1 else None
            body = []
        elif cur:
            body.append(line.strip())
    return out


def _split_ops(rest):
    """'Dw001,-Dw024' -> ['Dw001','-Dw024'] (bo phan (n) trong CNT_IN3(3))."""
    return [t.strip() for t in rest.split(",") if t.strip()]


def parse_body(lines):
    """[(lenh, [toan hang])] - da bo chu thich."""
    out = []
    for ln in lines:
        ln = ln.split(";")[0].strip()
        if not ln:
            continue
        m = re.match(r"^(\S+)\s*(.*)$", ln)
        if not m:
            continue
        out.append((m.group(1).upper(), _split_ops(m.group(2))))
    return out


class Translator:
    """Dich than lenh cua 1 macro sang danh sach khoi (netlist)."""

    def __init__(self, code, pins=None):
        self.code = code
        self.pins = pins or {}        # {'in': {n: ten}, 'out': {n: ten}}
        self.blocks = []              # [{name, op, inputs:[(role,src)], params:{}}]
        self.alias = {}               # thanh ghi -> ten khoi tao ra gia tri hien tai
        self.out_map = {}             # ten chan ra -> ten khoi
        self.acc = None               # ten khoi bool dang giu (dieu kien cho FMV1/TON)
        self.rung_open = False        # dang trong 1 rung bool (A/OR noi tiep nhau)
        self.rung_raw = []            # (op, [token goc]) cua rung hien tai - de bat chot tu giu
        self.n = 0

    # --- tien ich ---
    def _nm(self, prefix):
        self.n += 1
        return "%s%d" % (prefix, self.n)

    def _emit(self, name, op, inputs, params=None):
        self.blocks.append({"name": name, "op": op, "inputs": inputs, "params": params or {}})
        return name

    def _res(self, tok):
        """Toan hang -> ten nguon de noi day (ten chan / ten khoi / hang so)."""
        tok = tok.strip()
        neg = tok.startswith("-")
        if neg:
            tok = tok[1:]
        m = re.match(r"^CNT_(IN|OUT)\d*\((\d+)\)$", tok)
        if m:
            side = "in" if m.group(1) == "IN" else "out"
            nm = self.pins.get(side, {}).get(int(m.group(2)))
            src = nm or tok
        elif tok in self.alias:
            src = self.alias[tok]
        else:
            src = tok
        if neg:
            nb = self._emit(self._nm("not"), "NOT", [("in", src)])
            return nb
        return src

    # --- xu ly rung bool ---
    def _bool_step(self, op, ops):
        if not self.rung_open:            # bat dau rung moi
            self.acc = None
            self.rung_raw = []
            self.rung_open = True
        self.rung_raw.append((op, list(ops)))
        srcs = [self._res(t) for t in ops]
        if self.acc is None:
            if len(srcs) == 1:
                self.acc = srcs[0]
            else:
                self.acc = self._emit(self._nm("or" if op == "OR" else "and"),
                                      "OR" if op == "OR" else "AND",
                                      [("in", s) for s in srcs])
        else:
            self.acc = self._emit(self._nm("or" if op == "OR" else "and"),
                                  "OR" if op == "OR" else "AND",
                                  [("in", self.acc)] + [("in", s) for s in srcs])

    def _self_hold(self, target):
        """Rung co tu tham chieu target -> chot tu giu. Tra (set_srcs, reset_srcs)."""
        sets, resets = [], []
        for op, toks in self.rung_raw:
            for t in toks:
                base = t[1:] if t.startswith("-") else t
                if base == target:
                    continue          # nhanh tu giu
                if t.startswith("-"):
                    resets.append(base)
                else:
                    sets.append(base)
        return sets, resets

    def _do_out(self, target):
        """OUT z: neu rung tu tham chieu z -> CHOT TU GIU (SRLATCH s/r) giong ky hieu
        trong ban ve manual; nguoc lai chi gan bi danh cho khoi dang giu."""
        selfref = any(t.lstrip("-") == target for _op, toks in self.rung_raw for t in toks)
        if selfref:
            sets, resets = self._self_hold(target)
            s_src = (self._res(sets[0]) if len(sets) == 1
                     else self._emit(self._nm("or"), "OR", [("in", self._res(x)) for x in sets])
                     if sets else None)
            r_src = (self._res(resets[0]) if len(resets) == 1
                     else self._emit(self._nm("or"), "OR", [("in", self._res(x)) for x in resets])
                     if resets else None)
            ins = []
            if s_src:
                ins.append(("s", s_src))
            if r_src:
                ins.append(("r", r_src))
            nb = self._emit(self._nm("latch"), "SRLATCH", ins)
            self.alias[target] = nb
            self.acc = nb
            self._mark_out(target, nb)
            return
        src = self.acc
        if src is None:
            return
        self.alias[target] = src
        self._mark_out(target, src)

    # --- chuong trinh chinh ---
    def run(self, instrs):
        i = 0
        while i < len(instrs):
            op, ops = instrs[i]

            if op in ("A", "OR"):
                self._bool_step(op, ops)

            elif op == "OUT" and ops:
                # OUT gan gia tri VA ket thuc han dieu kien: lenh FMV1 ngay sau OUT chay
                # KHONG dieu kien (da kiem chung: 'A Dw025 / OUT OPS_OUT6 / FMV1 Rf008,
                # CNT_OUT2(15)' - ngo ra MV phai cap nhat moi vong quet, khong chi khi Dw025=1)
                self._do_out(ops[0])
                self._clear_acc()

            elif op == "FMV1" and len(ops) >= 2:
                src, dst = self._res(ops[0]), ops[1]
                prev = self.alias.get(dst)
                if self.acc is None:
                    # gan khong dieu kien
                    if prev is None:
                        nb = self._emit(self._nm("set"), "PASS", [("in", src)])
                    else:
                        nb = self._emit(self._nm("set"), "PASS", [("in", src)])
                    self.alias[dst] = nb
                else:
                    # co dieu kien -> chuyen mach: acc=1 lay src, nguoc lai giu gia tri cu
                    ins = [("sel", self.acc), ("a", src)]
                    if prev is not None:
                        ins.append(("b", prev))
                    nb = self._emit(self._nm("sel"), "SELECT", ins)
                    self.alias[dst] = nb
                self._mark_out(dst, self.alias[dst])
                self._clear_acc()

            elif op == "MV1" and len(ops) >= 2:
                nb = self._emit(self._nm("mv"), "PASS", [("in", self._res(ops[0]))])
                self.alias[ops[1]] = nb
                self._mark_out(ops[1], nb)
                self._clear_acc()

            elif op == "FUL" and len(ops) >= 3:
                # gop FUL + FLL lien tiep thanh 1 khoi CLAMP (giong ky hieu manual)
                nxt = instrs[i + 1] if i + 1 < len(instrs) else (None, [])
                if nxt[0] == "FLL" and len(nxt[1]) >= 3 and nxt[1][0] == ops[2]:
                    nb = self._emit(self._nm("clamp"), "CLAMP",
                                    [("in", self._res(ops[0])), ("hi", self._res(ops[1])),
                                     ("lo", self._res(nxt[1][1]))])
                    self.alias[nxt[1][2]] = nb
                    self._mark_out(nxt[1][2], nb)
                    i += 2
                    self._clear_acc()
                    continue
                nb = self._emit(self._nm("clamp"), "CLAMP",
                                [("in", self._res(ops[0])), ("hi", self._res(ops[1]))])
                self.alias[ops[2]] = nb
                self._mark_out(ops[2], nb)
                self._clear_acc()

            elif op == "FLL" and len(ops) >= 3:
                nb = self._emit(self._nm("clamp"), "CLAMP",
                                [("in", self._res(ops[0])), ("lo", self._res(ops[1]))])
                self.alias[ops[2]] = nb
                self._mark_out(ops[2], nb)
                self._clear_acc()

            elif op == "FITG" and len(ops) >= 4:
                nb = self._emit(self._nm("integ"), "INTEG", [("in", self._res(ops[0]))],
                                {"ti": 1.0})
                self.alias[ops[3]] = nb
                self._mark_out(ops[3], nb)
                self._clear_acc()

            elif op == "TON" and len(ops) >= 3:
                ins = [("in", self.acc)] if self.acc else []
                nb = self._emit(self._nm("ton"), "TON", ins)
                self.alias[ops[2]] = nb
                self._clear_acc()

            elif op in ("F+", "F-", "F*", "F/") and len(ops) >= 3:
                kind = {"F+": "ADD", "F-": "SUB", "F*": "MUL", "F/": "DIV"}[op]
                if kind in ("SUB", "DIV"):
                    ins = [("a", self._res(ops[0])), ("b", self._res(ops[1]))]
                else:
                    ins = [("in", self._res(ops[0])), ("in", self._res(ops[1]))]
                nb = self._emit(self._nm(kind.lower()), kind, ins)
                self.alias[ops[2]] = nb
                self._mark_out(ops[2], nb)
                self._clear_acc()

            elif op in ("FABS", "FNEG") and len(ops) >= 2:
                nb = self._emit(self._nm("abs"), "ABS" if op == "FABS" else "NEG",
                                [("in", self._res(ops[0]))])
                self.alias[ops[1]] = nb
                self._clear_acc()

            elif op == "XOR" and len(ops) >= 3:
                nb = self._emit(self._nm("xor"), "XOR",
                                [("in", self._res(ops[0])), ("in", self._res(ops[1]))])
                self.alias[ops[2]] = nb
                self._clear_acc()

            elif op in ("CFB", "CL", "LH", "AR", "SET", "FDLM", "TONL", "FCP+", "FCP-"):
                # lenh phu tro: giu lai de khong mat mach (1 khoi ghi ro ten lenh)
                if ops:
                    ins = [("in", self._res(t)) for t in ops[:-1]] or []
                    nb = self._emit(self._nm(op.lower().replace("+", "p").replace("-", "m")),
                                    op, ins)
                    self.alias[ops[-1]] = nb
                self._clear_acc()

            i += 1
        return self

    def _clear_acc(self):
        """Lenh du lieu (F*, FUL, FMV1, TON...) chay KHONG dieu kien va ket thuc dieu
        kien dang giu -> xoa acc de lenh sau khong bi gan nham dieu kien cu."""
        self.acc = None
        self.rung_open = False
        self.rung_raw = []


    def _mark_out(self, target, blockname):
        m = re.match(r"^CNT_OUT\d*\((\d+)\)$", target)
        if m:
            nm = self.pins.get("out", {}).get(int(m.group(1)))
            if nm:
                self.out_map[nm] = blockname

    # --- don dep sau khi dich ---
    def finalize(self):
        """1) Giai cac tham chieu TIEN (thanh ghi duoc dung truoc khi gan - vong quet truoc)
        2) Bo cac khoi CHET (khong dan toi ngo ra nao) - VD cac khoi rung tam sinh ra
        truoc khi phat hien chot tu giu."""
        byname = {b["name"]: b for b in self.blocks}
        for b in self.blocks:
            b["inputs"] = [(r, self.alias.get(s, s) if (s not in byname and s in self.alias) else s)
                           for r, s in b["inputs"]]
        keep, stack = set(), list(self.out_map.values())
        while stack:
            nm = stack.pop()
            if nm in keep or nm not in byname:
                continue
            keep.add(nm)
            stack.extend(s for _r, s in byname[nm]["inputs"])
        if keep:
            self.blocks = [b for b in self.blocks if b["name"] in keep]
        return self

    # --- xuat netlist van ban ---
    def to_netlist(self, title=""):
        lines = []
        if title:
            lines.append("# %s" % title)
        lines.append("# Sinh TU DONG tu than logic goc trong TAG_MCR.DEF (nguon chuan cua phan mem).")
        lines.append("")
        for b in self.blocks:
            ins = ", ".join("%s=%s" % (r, s) for r, s in b["inputs"])
            prm = ", ".join("%s=%s" % (k, v) for k, v in b["params"].items())
            line = "%-10s : %-7s : %s" % (b["name"], b["op"], ins)
            if prm:
                line += " : " + prm
            lines.append(line)
        if self.out_map:
            lines.append("")
            lines.append("OUT: " + ", ".join("%s=%s" % (k, v) for k, v in self.out_map.items()))
        return "\n".join(lines) + "\n"


def pins_of(code):
    """{'in': {so_chan: ten}, 'out': {...}} tu core/macro_pins.json theo macrocode."""
    p = os.path.join(os.path.dirname(__file__), "macro_pins.json")
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}
    for _sym, v in raw.items():
        if str(v.get("macrocode", "")).upper() == str(code).upper():
            out = {"in": {}, "out": {}}
            for k, pin in v.get("pins", {}).items():
                out[pin.get("side", "in")][int(k)] = pin.get("name") or ""
            return out
    return {}


def symbol_of(code):
    """macrocode -> SYMBOL_REAL (ten dung trong TAG_MCR.DEF), tra tu macro_pins.json."""
    p = os.path.join(os.path.dirname(__file__), "macro_pins.json")
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    for sym, v in raw.items():
        if str(v.get("macrocode", "")).upper() == str(code).upper():
            return sym
    return None


def netlist_for(code, root=None):
    """macrocode -> (netlist_text, so_lenh) hoac (None, 0) neu khong tim thay than logic."""
    tag_path, toden_path = find_def_files(root)
    sym = symbol_of(code)
    for path in (tag_path, toden_path):
        if not path:
            continue
        bodies = read_bodies(path)
        body = bodies.get(sym) if sym else None
        if body:
            instrs = parse_body(body)
            tr = Translator(code, pins_of(code)).run(instrs).finalize()
            return tr.to_netlist("%s (%s) - logic noi goc" % (code, sym)), len(instrs)
    return None, 0
