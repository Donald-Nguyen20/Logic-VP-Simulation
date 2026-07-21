# -*- coding: utf-8 -*-
"""Gom NGU CANH co cau truc cho 1 tin hieu de dua cho AI giai thich.
App lo phan SU THAT + MOI NOI (chinh xac tu DB); AI chi dien giai.
Khong goi mang o day - chi tao van ban ngu canh."""
from __future__ import annotations
from . import cond_tree as CT
from . import signal_graph as SG
from . import dbreader as D
try:
    from . import project_index as PI
except Exception:
    PI = None

_BLOCKS = None    # gom (code -> block name) de lam glossary


def _innames(node):
    """Ten cac tin hieu dau vao cua 1 khoi opaque/cmp (analog...)."""
    db = node.get("db"); sh = node.get("sheet")
    names = []
    for n in node.get("in_nets", []) or []:
        if not n:
            continue
        names.append(SG._name_of(db, sh, n) or n)
    return names


def _cross_note(name):
    """Neu tin hieu do CPU/sheet khac san xuat -> ghi chu (dung index)."""
    if not PI or not name:
        return ""
    try:
        locs = PI.locate(name)
    except Exception:
        locs = []
    seen = []
    for cpuname, cpuno, slbl, db, sheet in locs:
        tag = "%s/%s" % (cpuname or ("CPU%s" % cpuno), slbl)
        if tag not in seen:
            seen.append(tag)
    return ("  (also on: %s)" % ", ".join(seen[:6])) if seen else ""


def _find_source(name, cur_db, cur_sheet):
    """Tim noi tin hieu ten `name` DUOC SINH RA (co khoi xuat ra no) o sheet/CPU khac.
    Tra (db2, sheet2, sigid2, cpuname2, slbl2) hoac None."""
    if not PI or not name:
        return None
    try:
        cands = PI.locate_full(name)
    except Exception:
        cands = []
    for cpuname, cpuno, slbl, db2, sheet2, sigid2 in cands:
        if db2 == cur_db and sheet2 == cur_sheet:
            continue
        try:
            if CT._producers(db2, sheet2).get(sigid2):     # sheet nay THUC SU sinh ra no
                return (db2, sheet2, sigid2, cpuname or ("CPU%s" % cpuno), slbl)
        except Exception:
            continue
    return None


_MAX_LINES = 220     # gioi han so dong (tin hieu cuc ket noi -> cat bot)


def _expand(db, sheet, net, depth, seen, out, ind=1, negpfx="", xhops=3):
    """Truy nguoc XUYEN MOI KHOI + XUYEN SHEET/CPU. Khi gap tin hieu nhan tu noi khac,
    tu nhay sang sheet/CPU SINH RA no va trace tiep (gioi han xhops buoc nhay)."""
    if len(out) >= _MAX_LINES:
        if len(out) == _MAX_LINES:
            out.append("  ... (chain truncated - signal is highly connected)")
        return
    pad = "  " * ind
    name = SG._name_of(db, sheet, net)
    label = negpfx + (name or net)
    key = (db, sheet, net)
    if not net or depth <= 0:
        out.append("%s%s ..." % (pad, label))
        return
    if key in seen:
        out.append("%s%s  (see above)" % (pad, label))
        return
    seen.add(key)
    prod = CT._producers(db, sheet).get(net)
    if not prod:
        # tin hieu nhan tu noi khac -> nhay sang nguon roi trace tiep
        if name and xhops > 0:
            src = _find_source(name, db, sheet)
            if src:
                db2, sheet2, sigid2, cpu2, slbl2 = src
                out.append("%s%s  (produced on %s / sheet %s):" % (pad, label, cpu2, slbl2))
                _expand(db2, sheet2, sigid2, depth - 1, seen, out, ind + 1, "", xhops - 1)
                return
        note = _cross_note(name) if name else ""
        kind = "external/cross input" if name else "internal source"
        out.append("%s%s  (%s)%s" % (pad, label, kind, note))
        return
    code = prod["code"]; sym = prod["sym"]; blk = D.macro_name(code, sym)
    if _BLOCKS is not None:
        _BLOCKS[code] = blk
    out.append("%s%s  <= %s of:" % (pad, label, blk))
    for (innet, ns) in prod["ins"]:
        if not innet:
            continue
        _expand(db, sheet, innet, depth - 1, seen, out, ind + 1,
                "NOT " if ns else "", xhops)


def _render(node, depth=0, out=None):
    if out is None:
        out = []
    ind = "  " * depth
    neg = "NOT " if node.get("neg") else ""
    t = node.get("type")
    lbl = node.get("label", node.get("net", ""))
    if node.get("block") and _BLOCKS is not None and node.get("code"):
        _BLOCKS[node["code"]] = node["block"]
    if t == "gate":
        op = node.get("op", "?")
        via = (" [through %s]" % ", ".join(node["via"])) if node.get("via") else ""
        pr = (" priority=%s" % node["priority"]) if node.get("priority") else ""
        out.append("%s%s%s = %s%s%s of:" % (ind, neg, lbl, op, pr, via))
        for ch in node.get("children", []):
            _render(ch, depth + 1, out)
    elif t in ("opaque", "cmp"):
        blk = node.get("block", "block")
        ins = _innames(node)
        if t == "cmp":
            out.append("%s%s%s  <block %s: analog compare %s threshold; inputs: %s>"
                       % (ind, neg, lbl, blk, node.get("rel", ""), ", ".join(ins) or "?"))
        else:
            out.append("%s%s%s  <through block %s; upstream inputs: %s>"
                       % (ind, neg, lbl, blk, ", ".join(ins) or "?"))
    else:
        extra = ""
        if t == "const":
            extra = "  (constant)"
        elif node.get("kind") == "cross":
            extra = "  (cross-sheet/CPU signal)" + _cross_note(lbl)
        elif node.get("kind") == "source":
            extra = "  (source input)"
        out.append("%s%s%s%s" % (ind, neg, lbl, extra))
    return out


def build_signal_context(db, sheet, net, cpu_paths=None):
    """Tra ve (title, context_text) cho 1 tin hieu."""
    R = SG._dbc(db)
    name = SG._name_of(db, sheet, net) or net
    sysn = SG.sys_name(db, sheet)
    slbl = R["num"].get(sheet) or str(sheet)
    try:
        ftext, opword = CT.formula(db, sheet, net)
    except Exception:
        ftext = ""
    global _BLOCKS
    _BLOCKS = {}
    try:
        chain = []
        _expand(db, sheet, net, 12, set(), chain, ind=1)
        chain_txt = "\n".join(chain)
    except Exception as e:
        chain_txt = "(could not trace: %s)" % e

    lines = []
    lines.append("SIGNAL: %s" % name)
    lines.append("CPU: %s    SHEET: %s" % (sysn, slbl))
    if ftext:
        lines.append("ONE-LINE FORMULA: %s" % ftext)
    lines.append("")
    lines.append("HOW THIS SIGNAL IS FORMED (traced upstream through every block; "
                 "'X <= BLOCK of: ...' means block feeds X; NOT = inverted input; "
                 "(cross-sheet/CPU input) with (also on: ...) points to where else it appears):")
    lines.append("  %s" % name)
    lines.append(chain_txt)
    if _BLOCKS:
        lines.append("")
        lines.append("FUNCTION BLOCKS USED (code: meaning):")
        for code, bname in sorted(_BLOCKS.items()):
            lines.append("  %s: %s" % (code, bname))
    return name, "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a controls engineer assistant for a Toshiba DCS (power plant). "
    "You are given a signal's condition logic already extracted from the project "
    "database. Explain, in clear language, HOW this signal works: what conditions "
    "drive it, the role of each function block, and the overall purpose. "
    "IMPORTANT RULES: use ONLY the facts in the provided context. Do NOT invent "
    "signals, values, or connections. If something is marked 'block not modeled' or "
    "unknown, say so instead of guessing. Keep numbers/thresholds exactly as given. "
    "If tools are available, use get_source(name) to fetch the upstream logic of any "
    "signal you need to go deeper on, and block_function(code) for a block's meaning - "
    "do NOT ask the user for more context; fetch it yourself with the tools."
)


_CAT = None


def _catalog():
    global _CAT
    if _CAT is None:
        import os, json
        try:
            p = os.path.join(os.path.dirname(__file__), "macro_catalog.json")
            _CAT = {m["code"].upper(): m for m in json.load(open(p, encoding="utf-8"))["macros"]}
        except Exception:
            _CAT = {}
    return _CAT


def block_function(code):
    """Mo ta chuc nang 1 macrocode (cho tool)."""
    m = _catalog().get((code or "").upper())
    if not m:
        return "Unknown block code %s" % code
    return "%s (%s): %s | inputs=%s outputs=%s params=%s" % (
        code, m.get("short", ""), m.get("name", ""), m.get("inputs"),
        m.get("outputs"), m.get("params"))


def trace_by_name(name):
    """Gom ngu canh (chuoi thuong nguon) cho 1 tin hieu theo TEN (cho tool get_source)."""
    if not PI:
        return "Index not available."
    locs = PI.locate_full(name)
    if not locs:
        return "Signal '%s' not found in any imported DB." % name
    # uu tien vi tri THUC SU sinh ra tin hieu (co khoi xuat ra no)
    chosen = None
    for cpuname, cpuno, slbl, db, sheet, sigid in locs:
        try:
            if CT._producers(db, sheet).get(sigid):
                chosen = (db, sheet, sigid); break
        except Exception:
            continue
    if not chosen:
        cpuname, cpuno, slbl, db, sheet, sigid = locs[0]
        chosen = (db, sheet, sigid)
    _, ctx = build_signal_context(chosen[0], chosen[1], chosen[2])
    return ctx


def locate_text(name):
    """Danh sach CPU/sheet co tin hieu ten `name` (cho tool find_signal)."""
    if not PI:
        return "Index not available."
    rows = PI.find(name)
    seen = []; lines = []
    for r in rows:
        tag = (r[1] or ("CPU%s" % r[2]), r[3], r[0])
        if tag in seen:
            continue
        seen.append(tag)
        lines.append("%s | sheet %s | %s" % tag)
        if len(lines) >= 60:
            break
    return "\n".join(lines) if lines else "No signal matching '%s'." % name


def build_prompt(name, context, question=None, lang="en"):
    q = question or ("Explain how the signal '%s' works and what it is for." % name)
    langline = ("Answer in Vietnamese." if lang == "vi" else "Answer in English.")
    return "%s\n%s\n\n--- SIGNAL CONTEXT ---\n%s\n--- END CONTEXT ---\n\n%s" % (
        SYSTEM_PROMPT, langline, context, q)
