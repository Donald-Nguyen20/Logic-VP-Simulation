# -*- coding: utf-8 -*-
"""
CAY DIEU KIEN cho 1 tin hieu: "de X = 1 thi can gi", va "hien tai con thieu gi".
Chi doc DB, khong sua gi.
"""
from __future__ import annotations
import os
import json
from collections import defaultdict
from . import dbreader as D
from . import sheet_render as SR
from . import signal_graph as SG

TERM = "E0B1"
_SEM = None


def _sem():
    global _SEM
    if _SEM is None:
        p = os.path.join(os.path.dirname(__file__), "logic_sem.json")
        try:
            _SEM = json.load(open(p, encoding="utf-8"))
        except Exception:
            _SEM = {}
    return _SEM


_PROD = {}


def _producers(db, sheet):
    key = (db, sheet)
    if key in _PROD:
        return _PROD[key]
    c = D.connect(db).cursor()
    MP = SR._macro_pins()
    IODEP = SG._iodep()
    binfo = {}
    for bid, sym, code in c.execute(
            "SELECT BLOCK_ID,SYMBOL,MACROCODE FROM CAD_BLOCK WHERE ID=? ORDER BY BLOCK_ID", (sheet,)):
        binfo[bid] = (sym or "", (code or "").upper())
    pins = defaultdict(list)
    for bid, pn, sig, ns in c.execute(
            "SELECT p.BLOCK_ID,p.PINNO,p.SIGNALID,p.NOT_SIGN FROM CAD_BLOCK_PIN p "
            "JOIN CAD_BLOCK b ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=? ORDER BY p.PINNO", (sheet,)):
        pins[bid].append((pn, D._clean(sig), 1 if D._clean(ns) == "1" else 0))
    prod = {}
    for bid, pl in pins.items():
        sym, code = binfo[bid]
        if code == TERM:
            continue
        mdef = MP.get(sym)
        n = len(pl)
        ins = []; outs = []
        for idx, (pn, net, ns) in enumerate(pl):
            if SG._pin_out(mdef, pn, idx, n):
                outs.append(net)
            else:
                ins.append((net, ns))
        dep = IODEP.get(code)
        use_dep = dep and dep.get("dep") and dep.get("nin") == len(ins) and dep.get("nout") == len(outs)
        for oidx, onet in enumerate(outs):
            if not onet or onet in prod:
                continue
            if use_dep:
                sel = [ins[j] for j in dep["dep"].get(str(oidx), []) if 0 <= j < len(ins)]
            else:
                sel = ins
            prod[onet] = {"bid": bid, "code": code, "sym": sym, "ins": sel}
    _PROD[key] = prod
    return prod


def tmr_note(db, sheet, prod, s):
    """Chu thich ngan gan vao duong di khi cay di xuyen qua 1 khoi delay/xung,
    vd " (pulse 5s)". Co thoi gian cu the thi nguoi doc moi biet tin hieu nay chi
    ton tai trong choc lat chu khong duy tri."""
    from . import sheet_sim as SS
    fam = s.get("tmr")
    w = "pulse" if fam in ("PO", "TDWO") else ("oscillator" if fam == "PG" else "delay")
    t = SS.timer_secs(db, sheet, s, prod["bid"])
    return " (%s)" % w if t is None else " (%s %gs)" % (w, t)


def const_of(db, sheet, prod, s):
    """Gia tri that cua 1 khoi hang so digital: uu tien cai dat rieng cua khoi
    (param '2'), khong co thi lay hang so co dinh cua loai khoi trong logic_sem.
    Khoi DSW (4018) cai bang tay tung cai nen bat buoc phai doc theo khoi, neu
    khong thi cay giai thich se noi 'constant = 0' cho ca nhung khoi cai '1'.
    Nap muon sheet_sim vi module do da import nguoc lai cond_tree - va chi o do
    moi co gia tri nguoi dung sua tam trong cua so 'Block parameters'."""
    from . import sheet_sim as SS
    v = SS._num(SS._params(db, sheet).get(prod["bid"], {}).get("2"))
    if v is None:
        v = s.get("val", 0)
    return 1 if v else 0


def build(db, sheet, net, depth=40, cpu_paths=None, _ctr=None):
    cpu_paths = cpu_paths or {}
    R = SG._dbc(db)
    cpu = R["cpuno"]
    slbl = R["num"].get(sheet) or str(sheet)
    sem = _sem()
    counter = _ctr if _ctr is not None else [0]

    def nid():
        counter[0] += 1
        return counter[0]

    def label(nt):
        return SG._name_of(db, sheet, nt) or nt

    def leaf(net, kind, via=None, extra=None):
        nd = {"id": nid(), "type": "leaf", "net": net, "label": label(net),
              "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": (R["num"].get(sheet) or str(sheet)),
              "kind": kind, "neg": False, "via": via or []}
        if extra:
            nd.update(extra)
        return nd

    def sel_node(net, prod, s, blabel, dep, vis2, via):
        """Cong tac chuyen mach (1030/40D5): Y = X1 khi SW=1, Y = X2 khi SW=0.
        Dien giai thanh (SW VA X1) HOAC (KHONG SW VA X2) - dung nguyen nghia khoi,
        va chi dung cac kieu nut da co (gate AND/OR) nen cua so cay dieu kien lan
        Ma tran C&E khong phai sua gi de hieu duoc khoi nay."""
        pins = prod["ins"]
        swn, swns = pins[s["sw"]]
        node = {"id": nid(), "type": "gate", "op": "OR", "net": net, "label": label(net),
                "block": blabel, "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": slbl,
                "via": via, "neg": False, "children": []}
        for role, want_sw in (("x1", True), ("x2", False)):
            xn, xns = pins[s[role]]
            sw_ch = rec(swn, dep - 1, vis2, [])
            # SW=1 chon X1, SW=0 chon X2; dau cham NOT tren chan SW dao them lan nua
            sw_ch["neg"] = bool(swns) if want_sw else not bool(swns)
            x_ch = rec(xn, dep - 1, vis2, [])
            if xns:
                x_ch["neg"] = not x_ch.get("neg", False)
            node["children"].append(
                {"id": nid(), "type": "gate", "op": "AND", "net": net, "label": label(net),
                 "block": blabel, "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": slbl,
                 "via": [], "neg": False, "children": [sw_ch, x_ch]})
        return node

    def rec(net, dep, visited, via):
        if not net:
            return leaf(net, "const-empty", via)
        if dep <= 0 or net in visited:
            return leaf(net, "opaque", via, {"note": "gioi han do sau" if dep <= 0 else "vong lap"})
        prod = _producers(db, sheet).get(net)
        nm = SG._name_of(db, sheet, net)
        if not prod:
            k = "cross" if nm else "source"
            nd = leaf(net, k, via)
            if nm and any(s2 != sheet for (s2, _n2) in R["name2"].get(nm.upper(), [])):
                nd["expandable"] = True
            return nd
        code = prod["code"]; sym = prod["sym"]
        s = sem.get(code)
        blabel = D.macro_name(code, sym)
        vis2 = visited | {net}
        if s is None:
            return {"id": nid(), "type": "opaque", "net": net, "label": label(net),
                    "block": blabel, "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": slbl, "neg": False, "via": via,
                    "kind": "opaque", "code": code,
                    "in_nets": [n for (n, _ns) in prod["ins"]], "expandable": True}
        op = s["op"]
        if op == "CONST":
            cv = const_of(db, sheet, prod, s)
            return {"id": nid(), "type": "const", "val": cv,
                    "label": "%s (=%d)" % (blabel, cv), "block": blabel,
                    "net": net, "neg": False, "via": via, "kind": "const", "db": db, "sheet": sheet, "sheetlbl": slbl}
        if op == "PASS":
            insn = [n for (n, _ns) in prod["ins"] if n]
            nv = list(via) + [blabel + (" (%s)" % s["note"] if s.get("note") else "")]
            if insn:
                return rec(insn[0], dep - 1, vis2, nv)
            return leaf(net, "source", nv)
        if op == "CMP":
            return {"id": nid(), "type": "cmp", "net": net, "label": label(net),
                    "block": blabel, "rel": s.get("rel", "cmp"), "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": slbl,
                    "neg": False, "via": via, "kind": "cmp",
                    "in_nets": [n for (n, _ns) in prod["ins"]], "expandable": True}
        if op == "SELECT":
            if len(prod["ins"]) > max(s["sw"], s["x1"], s["x2"]):
                return sel_node(net, prod, s, blabel, dep, vis2, via)
            return leaf(net, "source", via)
        if op == "PULSE":
            # Xung mot nhat / mach dao dong. VAN truy nguoc qua khoi: xet ve nhan qua
            # thi nguyen nhan co toi duoc ket qua (Ma tran C&E dua tren cay nay, neu
            # chan lai thi moi chuoi di qua khoi xung deu dut). Chi ghi them thoi gian
            # xung vao duong di de doc xong biet day la tin hieu thoang qua.
            insn = [n for (n, _ns) in prod["ins"] if n]
            nv = list(via) + [blabel + tmr_note(db, sheet, prod, s)]
            if insn:
                return rec(insn[0], dep - 1, vis2, nv)
            return leaf(net, "source", nv)
        base = {"AND": "AND", "NAND": "AND", "OR": "OR", "NOR": "OR",
                "NOT": "NOT", "XOR": "XOR", "SR": "SR"}[op]
        node = {"id": nid(), "type": "gate", "op": base, "net": net, "label": label(net),
                "block": blabel, "sheet": sheet, "cpu": cpu, "db": db, "sheetlbl": slbl, "via": via,
                "neg": op in ("NAND", "NOR"), "children": []}
        if op == "SR":
            node["priority"] = s.get("priority", "reset")
        ch = []
        for (innet, ns) in prod["ins"]:
            sub = rec(innet, dep - 1, vis2, [])
            if ns:
                sub["neg"] = not sub.get("neg", False)
            ch.append(sub)
        node["children"] = ch
        return node

    return rec(net, depth, set(), [])


def evaluate(node, env):
    t = node["type"]
    if t == "const":
        v = node["val"]
    elif t in ("leaf", "cmp", "opaque"):
        v = env.get(node["id"], None)
    elif t == "gate":
        cs = [evaluate(c, env) for c in node["children"]]
        op = node["op"]
        if op == "NOT":
            v = None if cs[0] is None else 1 - cs[0]
        elif op == "XOR":
            v = None if any(x is None for x in cs) else (sum(cs) % 2)
        elif op == "SR":
            s, r = (cs + [None, None])[:2]
            if node.get("priority") == "set":
                v = 1 if s == 1 else (0 if r == 1 else None)
            else:
                v = 0 if r == 1 else (1 if s == 1 else None)
        elif op == "AND":
            if any(x == 0 for x in cs):
                v = 0
            elif any(x is None for x in cs):
                v = None
            else:
                v = 1
        else:
            if any(x == 1 for x in cs):
                v = 1
            elif any(x is None for x in cs):
                v = None
            else:
                v = 0
    else:
        v = None
    if v is not None and node.get("neg"):
        v = 1 - v
    return v


def blockers(node, env, want=1):
    raw = want ^ (1 if node.get("neg") else 0)
    t = node["type"]
    if t == "const":
        return [] if node["val"] == raw else [(node, raw)]
    if t in ("leaf", "cmp", "opaque"):
        cur = env.get(node["id"])
        return [] if cur == raw else [(node, raw)]
    if t == "gate":
        op = node["op"]; ch = node["children"]
        if op == "NOT":
            return blockers(ch[0], env, 1 - raw)
        if op == "XOR":
            out = []
            for c in ch:
                out += blockers(c, env, 1)
            return out
        if op == "SR":
            out = []
            if raw == 1:
                if evaluate(ch[0], env) != 1:
                    out += blockers(ch[0], env, 1)
                if len(ch) > 1 and evaluate(ch[1], env) != 0:
                    out += blockers(ch[1], env, 0)
            return out
        if op == "AND":
            if raw == 1:
                out = []
                for c in ch:
                    if evaluate(c, env) != 1:
                        out += blockers(c, env, 1)
                return out
            if any(evaluate(c, env) == 0 for c in ch):
                return []
            out = []
            for c in ch:
                out += blockers(c, env, 0)
            return out
        if op == "OR":
            if raw == 1:
                if any(evaluate(c, env) == 1 for c in ch):
                    return []
                out = []
                for c in ch:
                    out += blockers(c, env, 1)
                return out
            out = []
            for c in ch:
                if evaluate(c, env) != 0:
                    out += blockers(c, env, 0)
            return out
    return []


def leaves(node, acc=None):
    if acc is None:
        acc = []
    if node["type"] in ("leaf", "cmp", "opaque"):
        acc.append(node)
    elif node["type"] == "gate":
        for c in node["children"]:
            leaves(c, acc)
    return acc


def max_id(node):
    m = node.get("id", 0)
    for c in node.get("children", []):
        m = max(m, max_id(c))
    return m


def expand(node, cpu_paths=None, id_base=0, depth=30):
    """Bung 1 la: cross -> sang sheet/CPU san xuat no; opaque/cmp -> bung input.
    Tra ve node THAY THE (giu neg) hoac None."""
    cpu_paths = cpu_paths or {}
    db = node.get("db"); sheet = node.get("sheet"); net = node.get("net")
    kind = node.get("kind")
    ctr = [id_base]
    if kind == "cross":
        R = SG._dbc(db); nm = (node.get("label") or "").upper()
        for (s2, net2) in R["name2"].get(nm, []):
            if s2 != sheet and nm in SG._produced_names(db, s2):
                sub = build(db, s2, net2, depth=depth, cpu_paths=cpu_paths, _ctr=ctr)
                if node.get("neg"):
                    sub["neg"] = not sub.get("neg", False)
                return sub
        for (pdb, ps, pnet, lbl) in SG._cross_cpu(node.get("label"), db, R["cpuno"], cpu_paths):
            sub = build(pdb, ps, pnet, depth=depth, cpu_paths=cpu_paths, _ctr=ctr)
            if node.get("neg"):
                sub["neg"] = not sub.get("neg", False)
            return sub
        return None
    if kind in ("opaque", "cmp"):
        kids = [build(db, sheet, innet, depth=depth, cpu_paths=cpu_paths, _ctr=ctr)
                for innet in node.get("in_nets", []) if innet]
        nn = dict(node); nn["children"] = kids; nn["expanded"] = True
        return nn
    return None


def sheet_io(tree):
    """Gom cac node theo (cpu, sheet): dau VAO (la cross/source) va dau RA
    (tin hieu co ten sinh ra tren sheet do). Giu thu tu xuat hien.
    Tra ve list [(cpu, sheetlbl, {'in':[labels], 'out':[labels]})]."""
    from collections import OrderedDict
    groups = OrderedDict()

    def named(n):
        lb = n.get("label")
        return bool(lb) and lb != n.get("net")

    def g(n):
        k = (n.get("cpu"), n.get("sheet"), n.get("sheetlbl"))
        if k not in groups:
            groups[k] = {"in": [], "out": [], "si": set(), "so": set(), "db": n.get("db")}
        return k, groups[k]

    def walk(n, psheet):
        k, gg = g(n)
        if n["type"] == "leaf" and n.get("kind") in ("cross", "source"):
            lb = n["label"]
            if lb not in gg["si"]:
                gg["si"].add(lb); gg["in"].append(lb)
        if (psheet is None or n.get("sheet") != psheet) and named(n):
            lb = n["label"]
            if lb not in gg["so"]:
                gg["so"].add(lb); gg["out"].append(lb)
        for c in n.get("children", []):
            walk(c, n.get("sheet"))

    walk(tree, None)
    out = []
    for (cpu, sheet, slbl), v in groups.items():
        if not v["in"] and not v["out"]:
            continue
        out.append({"cpu": cpu, "sheet": sheet, "sheetlbl": slbl, "db": v.get("db"),
                    "in": v["in"], "out": v["out"]})
    return out


# ---- tin hieu nay co Y NGHIA boolean (nhan qua) hay khong ----
def is_boolean_signal(db, sheet, net):
    """True neu tin hieu NAY co the dung Cay dieu kien (nguyen nhan/he qua) mot
    cach co y nghia: hoac la 1 tin hieu NGUON (chua tim thay khoi tao ra no trong
    sheet - van la 1 "la" boolean hop le), hoac khoi tao ra no la 1 phep logic/so
    sanh (AND/OR/NOT/XOR/SR/CONST/PASS/CMP - co trong logic_sem.json).
    False CHI khi khoi tao ra no la 1 khoi TINH TOAN ANALOG thuan tuy (SUM/DIF/
    TRAN-BMP/FNG/selector...) khong co trong logic_sem - luc do cay se chi co 1
    la "opaque" duy nhat, khong co gi de xem nen KHONG co y nghia mo cay."""
    prod = _producers(db, sheet).get(net)
    if not prod:
        return True   # tin hieu nguon (tu ben ngoai / chua ro) - van cho phep xem
    return _sem().get(prod["code"]) is not None


# ---- cong thuc 1 dong cho 1 tin hieu (de nhung vao so do node) ----
def SS_secs(db, sheet, s, bid):
    """Goi tat sang sheet_sim.timer_secs - nap muon vi sheet_sim import nguoc lai
    module nay (xem ghi chu trong const_of)."""
    from . import sheet_sim as SS
    return SS.timer_secs(db, sheet, s, bid)


def formula(db, sheet, net):
    """Tra ve (text, opword): tin hieu = phep(cac dau vao). '' neu la nguon."""
    sem = _sem()
    prod = _producers(db, sheet).get(net)
    psheet = sheet
    if not prod:
        nm = SG._name_of(db, sheet, net)
        if nm:
            for (s2, n2) in SG._dbc(db)["name2"].get(nm.upper(), []):
                if s2 != sheet and nm.upper() in SG._produced_names(db, s2):
                    p2 = _producers(db, s2).get(n2)
                    if p2:
                        prod = p2; psheet = s2; net = n2; break
    if not prod:
        return ("", "")
    code = prod["code"]; sym = prod["sym"]; ins = prod["ins"]
    s = sem.get(code)

    def rname(innet, guard):
        nm = SG._name_of(db, psheet, innet)
        if nm:
            return nm
        if innet in guard or len(guard) > 6:
            return innet
        p = _producers(db, psheet).get(innet)
        if not p:
            return innet
        ps = sem.get(p["code"])
        if ps and ps["op"] in ("PASS", "PULSE"):
            inn = [x for (x, _n) in p["ins"] if x]
            return rname(inn[0], guard | {innet}) if inn else innet
        return "(%s)" % D.macro_name(p["code"], p["sym"])

    labels = [(("/" if ns else "") + rname(innet, {net})) for (innet, ns) in ins if innet]
    if s is None:
        b = D.macro_name(code, sym)
        return ("through %s" % b, b)
    op = s["op"]
    if op == "AND":
        return ("AND( %s )" % ", ".join(labels), "AND")
    if op == "NAND":
        return ("NAND( %s )" % ", ".join(labels), "NAND")
    if op == "OR":
        return ("OR( %s )" % ", ".join(labels), "OR")
    if op == "NOR":
        return ("NOR( %s )" % ", ".join(labels), "NOR")
    if op == "NOT":
        return ("NOT( %s )" % (labels[0] if labels else ""), "NOT")
    if op == "XOR":
        return ("XOR( %s )" % ", ".join(labels), "XOR")
    if op == "SR":
        L = labels + ["?", "?"]
        return ("SR latch: SET=%s, RESET=%s" % (L[0], L[1]), "SR latch")
    if op == "PULSE":
        fam = s.get("tmr")
        w = "oscillator" if fam == "PG" else "pulse"
        t = SS_secs(db, psheet, s, prod["bid"])
        lb = labels[0] if labels else ""
        return ("%s (%s%s)" % (lb, w, "" if t is None else " %gs" % t), w)
    if op == "PASS":
        nt = s.get("note", "")
        w = "delay" if "timer" in nt else "buffer"
        return ("%s (%s)" % ((labels[0] if labels else ""), w), w)
    if op == "CMP":
        rel = {">=": ">= setpoint", "<=": "<= setpoint"}.get(s.get("rel"), "compare")
        return ("%s %s" % ((labels[0] if labels else ""), rel), "compare")
    if op == "CONST":
        return ("constant = %d" % const_of(db, psheet, prod, s), "constant")
    if op == "SELECT":
        if len(ins) > max(s["sw"], s["x1"], s["x2"]):
            L = [rname(ins[s[k]][0], {net}) for k in ("sw", "x1", "x2")]
            return ("switch %s: 1 -> %s, 0 -> %s" % tuple(L), "switch")
        return ("switch", "switch")
    b = D.macro_name(code, sym)
    return ("through %s" % b, b)
