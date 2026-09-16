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
import sqlite3

_DEF_DIRS = ("TYPE_A_CPUW01", "TYPE_A_CPUW02", "TYPE_A_CPUW11", "TYPE_A_CPUW12",
             "TYPE_A_CPUX02", "TYPE_B_CPUX01", "type_a_prcl01",
             "type_b_cpuL01-DCS", "type_b_cpuL01-EHC")

# Loai CPU cua file .db dang mo. None = chua biet -> giu nguyen thu tu _DEF_DIRS.
_CPU_TYPE = None
# {duong_dan_db: CPUTYPE} - sheet_dyn.run() goi lai hang tram lan moi phien,
# khong mo lai sqlite moi lan.
_CPU_CACHE = {}
# Tang moi lan doi CPU: ben ngoai (def_sim) so voi ban ghi rieng de tu xoa cache.
_GEN = 0


def _ma_cpu(ten_thu_muc):
    """'type_b_cpuL01-DCS' -> 'CPUL01-DCS', dung dang voi CAD_CPU.CPUTYPE trong .db."""
    return re.sub(r"^TYPE_[AB]_", "", ten_thu_muc, flags=re.I).upper()


def cpu_type_of_db(db):
    """CAD_CPU.CPUTYPE cua mot file .db, vd 'CPUL01-DCS'. None neu khong doc duoc.

    Do tren 21 file .db cua du an: 18 CPU CPUL01-DCS, 2 PRCL01, 1 CPUL01-EHC.
    Ca ba deu KHONG nam trong 6 thu muc ma _DEF_DIRS liet ke truoc day, tuc ung dung
    dang doc than lenh cua loai CPU khong he duoc dung o day."""
    if db in _CPU_CACHE:
        return _CPU_CACHE[db]
    try:
        cx = sqlite3.connect(db)
    except Exception:
        _CPU_CACHE[db] = None
        return None
    try:
        cx.text_factory = bytes
        r = cx.execute("SELECT CPUTYPE FROM CAD_CPU LIMIT 1").fetchone()
    except Exception:
        return None
    finally:
        cx.close()
    v = r[0] if r else None
    if isinstance(v, bytes):
        v = v.decode("latin-1")
    v = str(v or "").strip().upper() or None
    _CPU_CACHE[db] = v
    return v


def set_cpu_type(ct):
    """Dat loai CPU dang mo. Thu muc DEF khop se duoc UU TIEN khi gop than lenh.

    Vi sao can uu tien chu khong chi gop them: doi chieu tung than lenh giua bo thu muc
    dung (theo CPUTYPE) va bo dang doc thay 34 ten LECH NOI DUNG, tat ca deu la ho
    dinh thi trong TODEN.DEF - DI_I, DT_I, PO_I, DIL_I, TDWO_I va cac bien the 2/3/4.
    Vi du DT_I: CPU that chay 'TOFR D0001,X0004,Rs001,D0002,Rf001' (mot lenh timer co
    nho, 5 toan hang), con ban dang doc ghep 9 dong bang TOF + '*' + '/' + CFB. Gop mu
    thi ban nao thang la do thu tu liet ke, khong phai do dung CPU.

    TAG_MCR.DEF thi gop the nao cung duoc: 145 ten tren ca 9 thu muc, 0 ten lech."""
    global _CPU_TYPE, _GEN, _TAG_BODIES
    ct = (ct or "").strip().upper() or None
    if ct == _CPU_TYPE:
        return
    _CPU_TYPE = ct
    _GEN += 1
    _TAG_BODIES = None
    _TODEN_BODIES.clear()
    _PIN_FIX.clear()


def dung_db(db):
    """Bao cho module biet dang lam viec voi file .db nao -> chon dung bo than lenh."""
    set_cpu_type(cpu_type_of_db(db))


def _thu_tu_dirs():
    """_DEF_DIRS voi thu muc khop CPU dang mo dua len dau."""
    if not _CPU_TYPE:
        return list(_DEF_DIRS)
    khop = [d for d in _DEF_DIRS if _ma_cpu(d) == _CPU_TYPE]
    return khop + [d for d in _DEF_DIRS if d not in khop]


def find_all_def_files(root=None):
    """[(tag_mcr_path, toden_path)] cua MOI thu muc TYPE_* co that, theo thu tu _DEF_DIRS.

    Vi sao can ca 6 thu muc chu khong dung thu muc dau tien: moi thu muc la bo macro
    cua MOT loai CPU, va chung KHONG bao ham nhau. Do tren 21 file .db cua du an:
    82FD (DDL1, 1.898 khoi) va 82FE (DALM1, 222 khoi) CHI co than lenh trong
    TYPE_B_CPUX01, trong khi TYPE_A_CPUW01 - thu muc khop dau tien - lai khong co.
    Dung mot thu muc thi 2.152 khoi mat than lenh goc va phai chay mo hinh chep tay.

    Gop lai co an toan khong: doi chieu md5 tung than lenh qua ca 6 thu muc thay
    TAG_MCR.DEF co 129 ten, KHONG mot ten nao lech noi dung. (TODEN.DEF thi khac:
    20 ten ho timer - DI_I, DIL_I, DT_I, PO_I, TDWO_I va cac bien the 2/3/4 - lech
    that, vi CPUX01 dung lenh TONR mot dong con CPUW01 phai ghep 10 dong. Nen ben
    goi PHAI tu quyet lay ban nao, dung merge mu.)"""
    if root is None:
        # ...\T_Designer\T_Designer_Lite\core -> ...\T_Designer
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (os.path.join(root, "DEF", "SR21E"), os.path.join(root, "T_Designer", "DEF", "SR21E")):
        ra = []
        for d in _thu_tu_dirs():
            p = os.path.join(base, d, "TAG_MCR.DEF")
            q = os.path.join(base, d, "TODEN.DEF")
            # Gate theo CA HAI file: type_a_prcl01 co TAG_MCR.DEF rong 0 byte nhung
            # TODEN.DEF 21 KB. Neu chi xet TAG_MCR thi thu muc cua 2 CPU PRCL01
            # (AVR MC A/B) van lot, nhung mot thu muc chi co TODEN se bi bo qua oan.
            if os.path.exists(p) or os.path.exists(q):
                ra.append((p if os.path.exists(p) else None,
                           q if os.path.exists(q) else None))
        if ra:
            return ra                 # base dau tien co hang la base dung
    return []


def find_def_files(root=None):
    """Tra ve (tag_mcr_path, toden_path) cua thu muc TYPE_* KHOP DAU TIEN.

    Chi con dung cho cho nao that su can mot cap duong dan (vd bao cao duong dan cho
    nguoi dung). Muon DU than lenh thi goi find_all_def_files()."""
    ra = find_all_def_files(root)
    return ra[0] if ra else (None, None)


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


_TAG_BODIES = None
_TODEN_BODIES = {}
_PIN_FIX = {}


def merged_tag_bodies():
    """{symbol: [dong lenh]} gop TAG_MCR.DEF cua CA 6 thu muc TYPE_*, co nho ket qua.

    setdefault chu khong update: thu muc dung TRUOC trong _DEF_DIRS thang. Voi
    TAG_MCR.DEF hai cach cho ket qua y het nhau - da doi chieu md5 tung than lenh qua
    ca 6 thu muc, 129 ten khong ten nao lech - nhung giu setdefault de ket qua mo phong
    cua 12.871 khoi cu KHONG doi mot ly nao, du sau nay hang cap nhat lam hai ban lech.
    (TODEN.DEF thi lech that o ho timer nen KHONG gop kieu nay - xem find_all_def_files.)"""
    global _TAG_BODIES
    if _TAG_BODIES is None:
        _TAG_BODIES = {}
        for tag, _toden in find_all_def_files():
            if not tag:
                continue
            for sym, body in read_bodies(tag).items():
                _TAG_BODIES.setdefault(sym, body)
    return _TAG_BODIES


def merged_toden_bodies():
    """{symbol: [dong lenh]} tu TODEN.DEF, thu muc khop CPU dang mo duoc uu tien.

    Tach rieng khoi merged_tag_bodies vi hai file khong giao nhau MOT ten nao (145 ten
    TAG_MCR vs 833 ten TODEN) va do tin cay khac han: TAG_MCR giong nhau tren ca 9 thu
    muc, con TODEN co 34 ten lech noi dung giua cac loai CPU (xem set_cpu_type).

    Chua duoc def_sim dung lam nguon mac dinh: nap vao la doi hanh vi cua 152.164 khoi
    (79,1% du an) dang chay mo hinh chep tay. Phai co bo doi chieu chay xong da."""
    key = _CPU_TYPE or ""
    if key not in _TODEN_BODIES:
        m = {}
        for _tag, toden in find_all_def_files():
            if not toden:
                continue
            for sym, body in read_bodies(toden).items():
                m.setdefault(sym, body)
        _TODEN_BODIES[key] = m
    return _TODEN_BODIES[key]


def _bo_tien_to(sym):
    """'F_411E_I' -> '411E_I'. Ten trong macro_pins.json co tien to, ten trong DEF thi khong.

    Do duoc: 1.019 symbol trong macro_pins.json, 467 cai bat dau bang 'F_'; 978 ten
    trong cac file DEF, KHONG cai nao bat dau bang 'F_'. Khop tuyet doi duoc 549, bo
    tien to thi len 1.012 - tang 463 ten. Ca 463 ten do deu roi vao TODEN.DEF (0 cai
    roi vao TAG_MCR), ung voi 56.041 khoi cua du an."""
    return sym[2:] if sym and sym.startswith("F_") else sym


def body_of(sym, toden=False):
    """Than lenh cua mot symbol, chap nhan ca dang co va khong co tien to 'F_'."""
    if not sym:
        return None
    bodies = merged_toden_bodies() if toden else merged_tag_bodies()
    return bodies.get(sym) or bodies.get(_bo_tien_to(sym))


def _nguon_chan_ra(sym):
    """{so_chan_ra: so_chan_vao} suy TU THAN LENH GOC - chan ra nao duoc noi THANG tu
    mot chan vao. Chi nhan hai dang ma hang dung de truyen thang:
        FMV1  CNT_IN1(1),CNT_OUT1(3)      (analog)
        A     CNT_IN1(1)  ->  OUT CNT_OUT1(3)   (digital)"""
    ra = {}
    body = body_of(sym)
    if not body:
        return ra
    ins = parse_body(body)
    _CI = re.compile(r"^CNT_IN\d*\((\d+)\)$")
    _CO = re.compile(r"^CNT_OUT\d*\((\d+)\)$")
    for i, (op, o) in enumerate(ins):
        if op == "FMV1" and len(o) == 2:
            a, b = _CI.match(o[0]), _CO.match(o[1])
            if a and b:
                ra.setdefault(int(b.group(1)), int(a.group(1)))
        elif op == "OUT" and len(o) == 1 and i:
            b = _CO.match(o[0])
            pre_op, pre_o = ins[i - 1]
            if b and pre_op == "A" and len(pre_o) == 1:
                a = _CI.match(pre_o[0])
                if a:
                    ra.setdefault(int(b.group(1)), int(a.group(1)))
    return ra


def pin_defs(sym):
    """{'<so chan>': {'name':..., 'side':...}} cua mot SYMBOL, DA DIEN TEN CHAN RA THIEU.

    Vi sao phai dien: MacroDef.db cua hang KHONG luu ten chan, no chi luu toa do
    (DEF_MACRO_PIN co dung X,Y). Ten chan trong macro_pins.json la lay tu sach, ma
    sach thi khong ghi nhan cho chan ra "di thang" - vd 82FD_TG chan 1 'DDL1' o x=0
    va chan 3 khong ten o x=16 CUNG MOT HANG y=-4, tuc chan 3 chinh la dau kia cua
    duong day do.

    Hau qua khi de trong, dem tren 21 file .db cua du an (437.212 khoi): 12.476 khoi
    thuoc 12 ma (822E DALM 4.143, 8227 ADL 3.681, 82FD DDL1 1.898, 822F DDL 1.692,
    822A ALM2F 422, 82FE DALM1 222, 8228 189, 82D5 136, 8229 44, 822B 43, 822C 3,
    822D 3) van mo phong duoc, nhung gia tri tinh ra bi VUT DI - ca DefSim._put lan cho
    dung out_nets o sheet_dyn deu bo qua chan khong ten, nen tin hieu KHONG chay tiep
    xuong khoi sau. Nhin tren man hinh thi khoi "co chay", chi la dau ra mai bang rong.

    KHONG dinh toi 147 symbol ho _I (409D DTD 44.536 khoi, 409E ATA 20.476, 4010 NOT
    10.315 ...) cung de trong chan ra: chung co can_simulate=False nen di duong giai
    tinh logic_sem/analog_sem, cho do khop chan theo SO chan chu khong theo ten.

    Ten dien vao KHONG phai tu bia: lay ten cua chan VAO ma than lenh goc noi thang
    sang (xem _nguon_chan_ra). Chan ra nao than lenh khong ghi thi de nguyen trong -
    vd 8240 chan 16/17, 8242 chan 10..17, chung that su khong duoc ghi.

    Chi sua ban DOC RA, khong dong vao macro_pins.json: file do la ban dump nguyen goc.
    Khong dung o cho VE (sheet_render._macro_pins) - tren ban ve hang de trong that."""
    if sym in _PIN_FIX:
        return _PIN_FIX[sym]
    p = os.path.join(os.path.dirname(__file__), "macro_pins.json")
    try:
        raw = json.load(open(p, encoding="utf-8"))
    except Exception:
        raw = {}
    goc = (raw.get(sym) or {}).get("pins", {})
    out = {k: dict(v) for k, v in goc.items()}
    thieu = [k for k, v in out.items()
             if v.get("side") == "out" and not (v.get("name") or "").strip()]
    if thieu:
        nguon = _nguon_chan_ra(sym)
        for k in thieu:
            v = goc.get(str(nguon.get(int(k), "")))
            ten = (v or {}).get("name") or ""
            if ten.strip():
                out[k]["name"] = ten.strip()
    _PIN_FIX[sym] = out
    return out


def pin_wire_keys(pdef):
    """pin_defs -> {'<so chan>': khoa noi day}. Khoa DUY NHAT trong tung ben cua khoi.

    Vi sao can khoa rieng thay vi dung thang ten chan:

    1. Than lenh trong TODEN.DEF tro toi chan bang SO ('D0001' = chan 1), con sheet_dyn
       va DefSim khop chan bang TEN - ma macro_pins.json de TRONG ten cua rat nhieu chan
       VAO. Vi du 4000 AND2_I: 'A D0001,D0002 / OUT D0003', chan 1 va 2 khong ten nen bi
       loai khoi in_nets, khoi chay voi 0 dau vao va tra ve 0. Do la nguyen nhan 567 net
       bi keo ve 0 o lan chay dau tien cua bo doi chieu.
    2. Hang con dat TRUNG ten: 4008 OR3_I dat 'OR' cho CA HAI chan 2 va 3, 400A OR5_I
       cho chan 3 va 4. Khop theo ten thi hai chan do dam vao lam mot, chan sau de len
       chan truoc - bang chan tri sai dung 1 to hop tren 8 (va 1 tren 32). Do la hai ma
       duy nhat lech trong 27 ma so da doi chieu day du.

    Chi chong trung TRONG CUNG MOT BEN. Ten trung giua ben vao va ben ra la co y: 82FD
    DDL1 co chan ra 3 duoc pin_defs dien ten cua chan vao 1 (chan "di thang"), hai ben
    nam o hai dict khac nhau nen khong dam nhau."""
    dem = {"in": {}, "out": {}}
    for k, v in pdef.items():
        ten = (v.get("name") or "").strip()
        if ten:
            d = dem.setdefault(v.get("side", "in"), {})
            d[ten] = d.get(ten, 0) + 1
    ra = {}
    for k, v in pdef.items():
        ten = (v.get("name") or "").strip()
        ben = v.get("side", "in")
        ra[str(k)] = ten if ten and dem.get(ben, {}).get(ten) == 1 else ("#%s" % k)
    return ra


def pins_of(code, khoa=False):
    """{'in': {so_chan: ten}, 'out': {...}} tu core/macro_pins.json theo macrocode.

    khoa=True: thay ten bang KHOA NOI DAY duy nhat (xem pin_wire_keys) - dung cho duong
    chay than lenh TODEN, noi chan duoc tro toi bang so chu khong bang ten."""
    sym = symbol_of(code)
    if not sym:
        return {}
    pd = pin_defs(sym)
    kh = pin_wire_keys(pd) if khoa else None
    out = {"in": {}, "out": {}}
    for k, pin in pd.items():
        ten = kh[str(k)] if kh else (pin.get("name") or "")
        out[pin.get("side", "in")][int(k)] = ten
    return out


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
    sym = symbol_of(code)
    # quet CA 6 thu muc TYPE_*: 82FD/82FE chi co than lenh trong TYPE_B_CPUX01, neu
    # chi doc thu muc khop dau tien thi ban ve logic noi cua chung se trong tron.
    duong = [q for cap in find_all_def_files(root) for q in cap]
    for path in duong:
        if not path:
            continue
        bodies = read_bodies(path)
        body = (bodies.get(sym) or bodies.get(_bo_tien_to(sym))) if sym else None
        if body:
            instrs = parse_body(body)
            tr = Translator(code, pins_of(code)).run(instrs).finalize()
            return tr.to_netlist("%s (%s) - logic noi goc" % (code, sym)), len(instrs)
    return None, 0
