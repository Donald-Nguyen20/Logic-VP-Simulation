# -*- coding: utf-8 -*-
"""Gom NGU CANH co cau truc cho 1 tin hieu de dua cho AI giai thich.
App lo phan SU THAT + MOI NOI (chinh xac tu DB); AI chi dien giai.
Khong goi mang o day - chi tao van ban ngu canh."""
from __future__ import annotations
from . import cond_tree as CT
from . import signal_graph as SG
from . import sheet_render as SR
from . import dbreader as D
try:
    from . import project_index as PI
except Exception:
    PI = None

_BLOCKS = None    # gom (code -> block name) de lam glossary
_BEHAV = None     # gom (code, tham so) de rut ra TINH CHAT VAN HANH


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


_MEAS = {}


def _bparams(db, bid):
    """Tri dat RIENG cua khoi: nguong bao dong, thoi gian tre, don vi...
    PARAMNO 1 chi la nhan ve tren so do ('H-1', 'DI-1') nen bo; tu 2 tro di moi la so
    that. Day la thu tra loi cau 'cao la bao nhieu' - truoc day khong he gui cho AI."""
    if not bid:
        return ""
    try:
        c = D.connect(db).cursor()
        vals = [D._clean(v) for (n, v) in c.execute(
            "SELECT PARAMNO,PARAMVALUE FROM CAD_BLOCK_PARAM WHERE BLOCK_ID=? "
            "ORDER BY CAST(PARAMNO AS INTEGER)", (bid,)) if str(n).strip() != "1"]
        out = ", ".join(v for v in vals if v and v != "-")
        # khoi bao dong analog co the co ca chuc tri 999999/-999999 (nguong bi vo hieu);
        # giu dau danh sach vi tri co nghia nam o do, cat duoi de khong phinh ngu canh
        return out if len(out) <= 96 else (out[:96] + " ...")
    except Exception:
        return ""


def _meas(db, name):
    """Dai do + don vi cua 1 diem do ngoai hien truong (CAD_ID.SENSOR / CAD_SIGNAL).
    Khong co dai do thi 'cao-cao' chi la chu suong, AI khong noi duoc y nghia."""
    key = (db, name)
    if key in _MEAS:
        return _MEAS[key]
    out = ""
    try:
        c = D.connect(db).cursor()
        r = c.execute("SELECT SENSOR,LOCALTAGNO FROM CAD_ID WHERE LINENAME=? AND "
                      "SENSOR IS NOT NULL AND TRIM(SENSOR)<>'' LIMIT 1", (name,)).fetchone()
        u = c.execute("SELECT EUVUNIT FROM CAD_SIGNAL WHERE LINENAME=? AND EUVUNIT IS "
                      "NOT NULL AND TRIM(EUVUNIT)<>'' LIMIT 1", (name,)).fetchone()
        bits = []
        if r and D._clean(r[0]):
            bits.append("range %s" % D._clean(r[0]))
        elif u and D._clean(u[0]):
            bits.append("unit %s" % D._clean(u[0]))
        if r and D._clean(r[1]):
            bits.append("tag %s" % D._clean(r[1]))
        out = ", ".join(bits)
    except Exception:
        out = ""
    _MEAS[key] = out
    return out


def _glossary():
    """Chu giai khoi. Ten ngan MOT MINH la nguon doc sai lon nhat: 'DI' trong DCS thuong
    duoc hieu la Digital Input, o day lai la Delay Initiation (tre khi len); 'TRANS2' de bi
    doc thanh transmitter trong khi no la cong tac chon analog. Kem mo ta thi het doan."""
    out = []
    for code, bname in sorted(_BLOCKS.items()):
        _sh, desc, cat = D.macro_info(code)
        if desc and desc.upper() != (bname or "").upper():
            out.append("  %s: %s = %s%s" % (code, bname, desc,
                                            ("  [%s]" % cat) if cat else ""))
        else:
            out.append("  %s: %s" % (code, bname))
    return out


# tinh chat van hanh doc ra tu ten khoi trong macro_catalog: (mau tim trong ten, nhan, loi
# giai theo goc nguoi van hanh). Bam theo TEN chu khong bam theo ma so, de con them macro
# moi thi van chay.
_BEHAV_RULES = [
    ("two out of three", "vote",
     "2-out-of-3 voting: two channels must agree before the signal comes up, so one failed "
     "or drifting transmitter neither trips the plant nor blinds the protection"),
    ("signal monitor (high)", "hi",
     "high-limit monitor: comes up when the measured value rises above the set point, drops "
     "again only after it falls back to the reset point"),
    ("signal monitor (low)", "lo",
     "low-limit monitor: comes up when the measured value falls below the set point, drops "
     "again only after it rises back to the reset point"),
    ("delay initiation", "ondly",
     "ON-delay: the condition must stay true for the whole delay time before the signal "
     "comes up; a short spike is ignored"),
    ("on delay timer", "ondly",
     "ON-delay: the condition must stay true for the whole delay time before the signal "
     "comes up; a short spike is ignored"),
    ("delay termination", "offdly",
     "OFF-delay: once up, the signal is held for the delay time after the condition clears "
     "(used to stretch a short pulse so it is recorded and acted on)"),
    ("off delay timer", "offdly",
     "OFF-delay: once up, the signal is held for the delay time after the condition clears"),
    ("one shot", "pulse",
     "one-shot: gives a fixed-length pulse, not a steady state"),
    ("flip flop (reset priority", "ffr",
     "latching relay, RESET wins: once set it stays up on its own until a reset arrives, and "
     "if set and reset are present together the signal goes down"),
    ("flip flop (set priority", "ffs",
     "latching relay, SET wins: once set it stays up on its own until a reset arrives, and if "
     "set and reset are present together the signal stays up"),
    ("self hold", "sh",
     "self-holding drive command: the command keeps itself up after the pushbutton is "
     "released, so the operator must give the opposite command to clear it"),
    ("analog switch", "xfer",
     "transfer switch: picks between two measured values, so which source is in use depends "
     "on the switching condition (usually a channel-health or selection signal)"),
    ("digital output", "do",
     "physical output card: the signal leaves the DCS on real wiring to a relay/solenoid"),
    ("analog input", "ai",
     "physical input card: the value comes from a real transmitter on the plant"),
    ("digital input", "di",
     "physical input card: the state comes from a real contact on the plant"),
]


def _num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def _hyst(vals):
    """Nguong + diem nha + vung chet. Vung chet moi la thu nguoi van hanh can: dat 3.0 nha
    2.5 nghia la tin hieu khong rung khi ap suat dao dong quanh 3.0."""
    out = []
    for v in vals[:4]:
        parts = [x.strip() for x in v.split(",")]
        a = _num(parts[0]) if parts else None
        b = _num(parts[1]) if len(parts) > 1 else None
        unit = parts[2] if len(parts) > 2 and _num(parts[2]) is None else ""
        if a is None or b is None or (a == 0 and b == 0):
            continue                     # 0/0 la cho trong, khong phai nguong that
        d = abs(a - b)
        u = (" " + unit) if unit else ""
        # dat = nha thi khong co vung chet: tin hieu nha ngay khi gia tri lui khoi nguong,
        # nen de rung neu do dao dong. Noi ro thay vi in "deadband 0" kho hieu
        out.append(("set %g / reset %g%s -> deadband %g%s" % (a, b, u, d, u)) if d
                   else ("set %g / reset %g%s -> no deadband" % (a, b, u)))
    return ("  [%s]" % "; ".join(out)) if out else ""


def _behaviour():
    """Rut tinh chat VAN HANH ra khoi chuoi logic. Ban than chuoi chi noi 'noi vao dau';
    phan nay noi 'no cu xu the nao' - bo phieu 2/3, tre bao nhieu giay, tu giu hay khong,
    vung chet cua nguong. Tinh san o day de AI khong phai suy dien (va suy sai)."""
    if not _BEHAV:
        return []
    got, order = {}, []
    for code, pv in _BEHAV:
        _sh, desc, _cat = D.macro_info(code)
        low = (desc or "").lower()
        for pat, tag, text in _BEHAV_RULES:
            if pat not in low:
                continue
            if tag not in got:
                got[tag] = {"text": text, "vals": []}
                order.append(tag)
            if pv and pv not in got[tag]["vals"]:
                got[tag]["vals"].append(pv)
            break
    if not got:
        return []
    # xep theo muc quan trong voi nguoi van hanh, khong theo thu tu gap trong chuoi
    rank = {"hi": 0, "lo": 1, "vote": 2, "ondly": 3, "offdly": 4, "pulse": 5,
            "ffr": 6, "ffs": 7, "sh": 8, "xfer": 9, "ai": 10, "di": 11, "do": 12}
    order.sort(key=lambda t: rank.get(t, 99))
    lines = ["", "OPERATING BEHAVIOUR (worked out from the blocks above - the answer must "
                 "say this in plain words):"]
    for tag in order:
        g = got[tag]
        extra = ""
        if tag in ("hi", "lo"):
            extra = _hyst(g["vals"])
        elif tag in ("ondly", "offdly", "pulse") and g["vals"]:
            extra = "  [times found: %s]" % "; ".join(g["vals"][:4])
        lines.append("  - %s%s" % (g["text"], extra))
    return lines


def _where(db, sheet):
    """Ten ban ve + ten loop + chu thich. Ngu canh cu chi ghi 'SHEET: 101-12' nen AI
    khong biet do la mach gi; ten that ('BT-102 MFT(2)', loop 'MFT CIRCUIT') co du
    trong 100% ban ghi ma lai khong duoc dung."""
    try:
        c = D.connect(db).cursor()
        r = c.execute("SELECT SHEETNAME,COMMENT1,COMMENT2,COMMENT3,LOOPNO FROM "
                      "CAD_DATA WHERE ID=?", (sheet,)).fetchone()
    except Exception:
        return ""
    if not r:
        return ""
    bits = []
    if D._clean(r[0]):
        bits.append("drawing '%s'" % D._clean(r[0]))
    if r[4] is not None:
        try:
            ln = c.execute("SELECT LOOPNAME FROM CAD_LOOP WHERE LOOPNO=?",
                           (r[4],)).fetchone()
        except Exception:
            ln = None
        if ln and D._clean(ln[0]):
            bits.append("loop '%s'" % D._clean(ln[0]))
    cm = [D._clean(x) for x in r[1:4] if D._clean(x)]
    if cm:
        bits.append("notes: %s" % " / ".join(cm))
    return "   |   ".join(bits)


_CONS = {}


def _consumers(db, sheet):
    """net -> [khoi nhan net do lam DAU VAO]. Ban doi cua CT._producers. Can no vi diem den
    that su cua 1 tin hieu bao ve thuong la card ra so (IO_DO) hoac may ghi su kien (SOE),
    ma nhung khoi do KHONG sinh ra net nao nen khong bao gio xuat hien trong _producers."""
    key = (db, sheet)
    if key in _CONS:
        return _CONS[key]
    out = {}
    try:
        c = D.connect(db).cursor()
        MP = SR._macro_pins()
        binfo = {}
        for bid, sym, code in c.execute(
                "SELECT BLOCK_ID,SYMBOL,MACROCODE FROM CAD_BLOCK WHERE ID=?", (sheet,)):
            binfo[bid] = (sym or "", (code or "").upper())
        pins = {}
        for bid, pn, sig in c.execute(
                "SELECT p.BLOCK_ID,p.PINNO,p.SIGNALID FROM CAD_BLOCK_PIN p JOIN CAD_BLOCK b "
                "ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=? ORDER BY p.PINNO", (sheet,)):
            pins.setdefault(bid, []).append((pn, D._clean(sig)))
        for bid, pl in pins.items():
            sym, code = binfo.get(bid, ("", ""))
            mdef = MP.get(sym)
            n = len(pl)
            for idx, (pn, nt) in enumerate(pl):
                if not nt or SG._pin_out(mdef, pn, idx, n):
                    continue
                out.setdefault(nt, []).append({"bid": bid, "code": code, "sym": sym})
    except Exception:
        out = {}
    _CONS[key] = out
    return out


def _dest_block(n):
    """Mo ta khoi o DAU NHAN. Vi du that: FURN PRS HI HI ket thuc o IO_DO
    [IODO-5, 10CHA30EA044YB00, FURN PRS HI HI, SOE] - tuc di ra card ra so, dau day
    10CHA30EA044YB00, phuc vu may ghi su kien. Do moi la 'no lam gi'."""
    db, sheet = n.get("db"), n.get("sheet")
    if not db or sheet is None:
        return ""
    bits = []
    for cb in _consumers(db, sheet).get(n.get("net") or "", [])[:3]:
        blk = D.macro_name(cb["code"], cb["sym"])
        _sh, desc, _cat = D.macro_info(cb["code"])
        pv = _bparams(db, cb["bid"])
        t = blk + (" (%s)" % desc if desc else "")
        if pv:
            t += "  [%s]" % pv
        bits.append(t)
    return "  into %s" % " + ".join(bits) if bits else ""


def _drives(db, sheet, net, name, cpu_paths=None, limit=16):
    """Tin hieu nay DIEU KHIEN cai gi (truy XUOI). Chuoi o tren chi tra loi 'vi sao no
    len'; phan nay moi la CHUC NANG cua no.

    Ban cu bo qua moi diem den TRUNG TEN voi chinh tin hieu - ma o mach bao ve thi gan nhu
    diem den nao cung trung ten (cung 1 ten di sang CPU khac, sang sheet khac, ra card).
    Ket qua la muc nay gan nhu rong. Nay di theo CANH: moi noi tin hieu duoc dung deu duoc
    ke ra, kem khoi nhan no."""
    try:
        nodes, edges, _t = SG.trace_project(db, sheet, net, direction="down", depth=5,
                                            cpu_paths=cpu_paths)
    except Exception:
        return []
    byid = {n["id"]: n for n in nodes}
    root = None
    for n in nodes:
        if n.get("db") == db and n.get("sheet") == sheet and n.get("net") == net:
            root = n["id"]
            break
    up = (name or "").strip().upper()
    hits, cpus, seen = [], set(), set()
    for n in nodes:
        if n.get("cpu") is not None:
            cpus.add(n["cpu"])
        if n["id"] == root:
            continue
        lbl = (n.get("label") or "").strip()
        key = (n.get("cpu"), n.get("sheetlbl"), n.get("net"))
        if key in seen or len(hits) >= limit:
            continue
        seen.add(key)
        # cung ten = ban sao cua chinh no o noi khac; khac ten = tin hieu MOI sinh ra tu no
        same = lbl.upper() == up
        where = "CPU %s / sheet %s" % (n.get("cpu"), n.get("sheetlbl") or "?")
        head = ("  -> %s (%s, as `%s`)" % (lbl, where, n.get("net"))) if same else \
               ("  -> %s   (%s)" % (lbl, where))
        hits.append(head + _dest_block(n))
    if not hits:
        return []
    lines = ["", "WHAT THIS SIGNAL DRIVES (traced downstream - what actually happens when "
                 "it comes up; 'into <BLOCK>' is the block that receives it, and an I/O "
                 "block's parameters carry the real terminal/KKS tag):"]
    lines += hits
    if len(cpus) > 1:
        lines.append("  broadcast over C-NET to CPU %s"
                     % ", ".join(str(x) for x in sorted(cpus)))
    return lines


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
    if name:
        # gan o DAY chu khong o nhanh 'external input': _expand thuong nhay thang sang
        # sheet sinh ra tin hieu nen nhanh do gan nhu khong bao gio chay
        _m = _meas(db, name)
        if _m:
            label += "  [field measurement: %s]" % _m
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
    pv = _bparams(db, prod.get("bid"))
    if _BEHAV is not None:
        _BEHAV.append((code, pv))
    out.append("%s%s  <= %s%s of:"
               % (pad, label, blk, ("  [settings: %s]" % pv) if pv else ""))
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
        if _BEHAV is not None:
            _BEHAV.append((node["code"], ""))
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
    global _BLOCKS, _BEHAV
    _BLOCKS = {}
    _BEHAV = []
    try:
        chain = []
        _expand(db, sheet, net, 12, set(), chain, ind=1)
        chain_txt = "\n".join(chain)
    except Exception as e:
        chain_txt = "(could not trace: %s)" % e

    lines = []
    lines.append("SIGNAL: %s" % name)
    lines.append("CPU: %s    SHEET: %s" % (sysn, slbl))
    wh = _where(db, sheet)
    if wh:
        lines.append("LOCATION: %s" % wh)
    ms = _meas(db, name)
    if ms:
        lines.append("MEASUREMENT: %s" % ms)
    if ftext:
        lines.append("ONE-LINE FORMULA: %s" % ftext)
    lines.append("")
    lines.append("HOW THIS SIGNAL IS FORMED (traced upstream through every block; "
                 "'X <= BLOCK of: ...' means block feeds X; NOT = inverted input; "
                 "(cross-sheet/CPU input) with (also on: ...) points to where else it appears):")
    lines.append("  %s" % name)
    lines.append(chain_txt)
    lines += _drives(db, sheet, net, name, cpu_paths)
    lines += _behaviour()
    if _BLOCKS:
        lines.append("")
        lines.append("FUNCTION BLOCKS USED (code: short name = what the block does):")
        lines += _glossary()
    return name, "\n".join(lines)


def _loop_sheets(db, loopno):
    """[(sheet_id, so_sheet_trong_loop, ten_sheet)] cua 1 Loop, theo dung thu tu ban ve."""
    c = D.connect(db).cursor()
    rows = []
    try:
        for sid, sno, nm in c.execute(
                "SELECT ID,SHEETNO,SHEETNAME FROM CAD_DATA WHERE LOOPNO=?", (loopno,)):
            rows.append((sid, sno, D._clean(nm)))
    except Exception:
        return []
    rows.sort(key=lambda r: (r[1] if r[1] is not None else 0, r[0]))
    # chi giu sheet co khoi (sheet rong khong co gi de giai thich)
    try:
        have = {r[0] for r in c.execute("SELECT DISTINCT ID FROM CAD_BLOCK")}
        rows = [r for r in rows if r[0] in have]
    except Exception:
        pass
    return rows


_LOOP_MAX_BLOCKS = 40      # so khoi toi da mo ta cho 1 sheet (sheet rat lon -> cat bot)


def build_loop_context(db, loopno, max_sheets=12):
    """(title, context_text) cho CA MOT LOOP (mach dieu khien) thay vi 1 tin hieu.
    Mo ta: ten loop, tung sheet trong loop, cac khoi theo THU TU THUC THI kem nghia
    macro + tham so that, va TIN HIEU BIEN (vao tu ngoai loop / ra ngoai loop) - day
    la thu cho biet loop nay nhan gi va dieu khien cai gi."""
    from . import sheet_render as SR
    from . import sheet_sim as SS
    lname = ""
    try:
        lname = D.loop_names(db).get(loopno, "") or ""
    except Exception:
        pass
    sysn = ""
    try:
        meta = D.db_meta(db)
        sysn = meta.get("cpuname") or ("CPU%s" % meta.get("cpuno"))
    except Exception:
        pass
    sheets = _loop_sheets(db, loopno)[:max_sheets]
    title = "Loop %s %s" % (loopno, lname) if lname else "Loop %s" % loopno

    global _BLOCKS, _BEHAV
    _BLOCKS = {}
    _BEHAV = []
    MP = SR._macro_pins()
    lines = []
    lines.append("CONTROL LOOP: %s" % title)
    lines.append("CPU: %s    SHEETS IN THIS LOOP: %d" % (sysn, len(sheets)))
    lines.append("")

    loop_sids = {s[0] for s in sheets}
    ext_in, ext_out = [], []
    for sid, sno, snm in sheets:
        lines.append("--- SHEET %s: %s ---" % (sno, snm))
        c = D.connect(db).cursor()
        blocks = list(c.execute(
            "SELECT BLOCK_ID,SYMBOL,MACROCODE,EXEORDER FROM CAD_BLOCK WHERE ID=? "
            "ORDER BY CASE WHEN EXEORDER IS NULL OR EXEORDER<0 THEN 99999 ELSE EXEORDER END,"
            "BLOCK_ID", (sid,)))
        try:
            params = SS._params(db, sid)
        except Exception:
            params = {}
        pins = {}
        for bid, pn, sig in c.execute(
                "SELECT p.BLOCK_ID,p.PINNO,p.SIGNALID FROM CAD_BLOCK_PIN p "
                "JOIN CAD_BLOCK b ON p.BLOCK_ID=b.BLOCK_ID WHERE b.ID=? ORDER BY p.PINNO", (sid,)):
            pins.setdefault(bid, []).append((pn, D._clean(sig)))
        n = 0
        for bid, sym, code, exo in blocks:
            code = (code or "").upper()
            if code == "E0B1":                       # terminal - xu ly rieng o duoi
                continue
            n += 1
            if n > _LOOP_MAX_BLOCKS:
                lines.append("  ... (sheet has more blocks - truncated)")
                break
            blk = D.macro_name(code, sym)
            _BLOCKS[code] = blk
            if _BEHAV is not None:
                _BEHAV.append((code, _bparams(db, bid)))
            pdef = (MP.get(sym) or {}).get("pins", {})
            ins, outs = [], []
            for pn, sig in pins.get(bid, []):
                if not sig:
                    continue
                side = pdef.get(str(pn), {}).get("side")
                nm = SG._name_of(db, sid, sig) or sig
                pname = pdef.get(str(pn), {}).get("name") or ""
                item = ("%s=%s" % (pname, nm)) if pname else nm
                (outs if side == "out" else ins).append(item)
            pm = params.get(bid, {})
            pmtxt = ""
            if pm:
                vals = ", ".join("P%s=%s" % (k, v) for k, v in sorted(pm.items())[:6] if str(v).strip())
                if vals:
                    pmtxt = "  [params: %s]" % vals
            lines.append("  step %-5s %-14s in(%s) -> out(%s)%s"
                         % (exo if (exo is not None and exo >= 0) else "-", blk,
                            ", ".join(ins) or "-", ", ".join(outs) or "-", pmtxt))
        # tin hieu bien cua loop: lay tu terminal 2 ben sheet
        try:
            sh = SR.build_sheet(db, sid)
        except Exception:
            sh = None
        if sh is not None:
            for t in sh.terms:
                if not t.linename:
                    continue
                tgt_out = [s for s, _l in (t.targets or []) if s not in loop_sids]
                if t.side == "L" and tgt_out and t.linename not in ext_in:
                    ext_in.append(t.linename)
                elif t.side == "R" and tgt_out and t.linename not in ext_out:
                    ext_out.append(t.linename)
        lines.append("")

    if ext_in:
        lines.append("SIGNALS COMING IN FROM OUTSIDE THIS LOOP (%d):" % len(ext_in))
        for s in ext_in[:40]:
            lines.append("  <- %s" % s)
        lines.append("")
    if ext_out:
        lines.append("SIGNALS THIS LOOP SENDS OUT (%d):" % len(ext_out))
        for s in ext_out[:40]:
            lines.append("  -> %s" % s)
        lines.append("")
    lines += _behaviour()
    if _BLOCKS:
        lines.append("")
        lines.append("FUNCTION BLOCKS USED (code: short name = what the block does):")
        lines += _glossary()
    return title, "\n".join(lines)


LOOP_SYSTEM_PROMPT = (
    "You are a controls engineer assistant for a Toshiba DCS (power plant). "
    "You are given the complete contents of ONE control loop, extracted from the "
    "project database: every sheet, every function block in execution order with its "
    "real parameters, and the signals crossing the loop boundary. Explain the CONTROL "
    "PRINCIPLE of this loop: what process it controls, what it measures, how the "
    "control action is computed, what interlocks/protections/mode switching exist, and "
    "what it commands. Structure the answer as: (1) Purpose, (2) Inputs and what they "
    "mean, (3) How the control works step by step, (4) Interlocks and protections, "
    "(5) Outputs.\n"
    "WRITE IT FOR SOMEONE WHO DOES NOT HAVE THE DRAWING: never put an internal net label "
    "(a2, b0, c5) or a block code (210F, 401A) in the answer -- say what the thing does "
    "instead, e.g. 'the low-value selector' or 'the on-delay'. Never copy the context "
    "notation ('<=', arrows, '[settings: ...]'). One idea per sentence, no stacked "
    "parentheses. Bold each number with its unit and say what it means in operation. No "
    "glossary of blocks, and no remarks about the data or your own tools.\n"
    "IMPORTANT RULES: use ONLY the facts in the provided context. Do NOT "
    "invent signals, values or connections. Keep numbers/thresholds exactly as given. "
    "Where the database does not say WHY something is designed that way, say it is not "
    "in the data rather than guessing. If tools are available, use get_source(name) for "
    "the upstream logic of a signal and block_function(code) for a block's meaning."
)


def build_loop_prompt(title, context, question=None, lang="en"):
    q = question or ("Explain the control principle of '%s'." % title)
    langline = ("Answer in Vietnamese." if lang == "vi" else "Answer in English.")
    return "%s\n%s\n\n--- LOOP CONTEXT ---\n%s\n--- END CONTEXT ---\n\n%s" % (
        LOOP_SYSTEM_PROMPT, langline, context, q)


SYSTEM_PROMPT = (
    "You are a controls engineer assistant for a Toshiba DCS (power plant). "
    "You are given ONE signal's condition logic, already extracted from the project "
    "database. The context is a starting point, NOT the whole answer.\n"
    "\n"
    "HOW TO READ THE CONTEXT\n"
    "- 'X <= BLOCK of: ...' means that block drives X. 'NOT' means the input is inverted.\n"
    "- '[settings: 3.0, 2.5, kPa]' after a block are THAT block's own parameters, in order. "
    "For a high/low signal monitor they are set point, reset point, unit; for a timer, "
    "seconds. These are the real trip values -- quote them, never round or invent them.\n"
    "- '[field measurement: range -10 10 kPa, tag ...]' marks a real transmitter and its "
    "span. Use it to say what the threshold means physically (e.g. 3.0 kPa on a -10..10 kPa "
    "furnace pressure transmitter).\n"
    "- 'LOCATION' gives the drawing and loop the signal belongs to; say which system it is "
    "part of.\n"
    "- 'WHAT THIS SIGNAL DRIVES' lists what it commands. The cause chain says WHY the signal "
    "comes up; that section says WHAT HAPPENS when it does. An answer that omits it has not "
    "explained the signal's function.\n"
    "- In that section, 'into <BLOCK>' is the block at the receiving end. IO_DO / IO_DI / "
    "IO_AI mean the signal leaves or enters the DCS on real wiring -- their parameters give "
    "the card position and the KKS terminal tag, so say the signal is hardwired out and to "
    "what. An SOE block means the point is recorded by the sequence-of-events recorder, "
    "which is how the operator finds the first cause after a trip. The same name appearing "
    "on CPU A and CPU B is the redundant pair, not two different signals.\n"
    "- 'OPERATING BEHAVIOUR' is already worked out from the blocks; restate it in plain "
    "operating language and tie it to the numbers (how long it must persist, how far the "
    "value must fall before it releases, whether it holds itself in).\n"
    "- Block names in 'FUNCTION BLOCKS USED' are given with their full meaning. Use that "
    "meaning, never the short name's everyday sense: DI here is Delay Initiation (an "
    "ON-delay), not a digital input; TRANS is an analog transfer switch, not a "
    "transmitter.\n"
    "- A line ending in '...' is a branch that was CUT at the trace depth limit. What is "
    "behind it is unknown to you until you go and fetch it.\n"
    "\n"
    "WHAT YOU MUST DO BEFORE ANSWERING\n"
    "1. List every line ending in '...'.\n"
    "2. For each one whose label is a real signal name (has spaces or plant wording, e.g. "
    "'CWP 1 RUN', 'CWP-1 O/L HOV CLS'), call get_source on it. Interlocks and trip "
    "conditions live in exactly these cut branches -- an answer that skips them is wrong.\n"
    "3. Do NOT call get_source on short lowercase labels like a9, b5, a4. Those are "
    "sheet-local scratch nets, not signals; the tool cannot find them. Never guess what "
    "is behind them -- and never list them in the answer either, because a list of "
    "unreachable labels tells the reader nothing. Mention an unresolved branch only when "
    "it changes the meaning of the signal, and then in one sentence, by its real name.\n"
    "4. Call block_function for every block code you intend to explain. Do not describe a "
    "block from its name alone.\n"
    "5. Spend your turns on the branches that gate the signal (interlocks, permissives, "
    "trips), not on ones you already understand.\n"
    "\n"
    "OUTPUT STYLE -- WRITE FOR SOMEONE WHO DOES NOT HAVE THE DRAWING IN FRONT OF THEM\n"
    "The context you were given is working material. The answer is not a transcript of "
    "it. Everything you write has to stand on its own, in plain operating language.\n"
    "- Open the reply DIRECTLY with the title line: '# <SIGNAL NAME> - <what it means in "
    "plain words>'. Do not narrate what you are about to do, do not say 'I'll fetch' or "
    "'let me check'. The reader sees only the finished answer.\n"
    "- Use '## ' for each of the four sections below, in order, with their numbers.\n"
    "- NEVER put an internal net label (a2, b0, c5, EVER[0], DO1035) or a block code "
    "(210F, 401A, 4075, 4013) in the answer. They mean nothing to the reader. Say what "
    "the thing DOES instead -- 'the low-value selector', 'the upper limiter', 'the "
    "on-delay'. If a branch carries no real signal name, call it an internal line on the "
    "drawing and move on.\n"
    "- NEVER copy the context notation into the answer: no '<=', no arrows, no 'BLOCK "
    "of:', no '[settings: ...]'. Write sentences, not netlists.\n"
    "- One idea per sentence. No stacked parentheses. If a sentence needs two brackets "
    "to be understood, split it in two.\n"
    "- Bold every number that matters together with its unit, and immediately say what "
    "it means in operation -- a number on its own explains nothing.\n"
    "- Use a Markdown table ONLY in section (4), and only if there are at least two rows "
    "and every cell has a real value. A table with blank or '-' cells is harder to read "
    "than bullets, so use bullets then.\n"
    "- Never include a glossary of blocks or block codes. That is working material.\n"
    "- Never comment on the data, on the trace, on what was cut off, or on your own "
    "tools. The reader wants the plant, not the software.\n"
    "- Aim for under 600 words. A shorter answer the reader finishes beats a complete "
    "one they give up on.\n"
    "\n"
    "ANSWER FORMAT -- four sections, nothing more\n"
    "(1) WHAT IT IS -- three to five plain sentences. What it represents physically "
    "(measured variable and span, the set point with its unit, or the plant state it "
    "latches), which system it belongs to, and what it commands -- name the real "
    "downstream users from 'WHAT THIS SIGNAL DRIVES'. Finish with one sentence saying "
    "whether this is a protection/trip path, an alarm-only path, or a continuous control "
    "command. Write this section even when the cause chain is huge; it is what the reader "
    "needs most.\n"
    "(2) WHAT MAKES IT ACT -- the conditions that form it, grouped by meaning (all the "
    "pressure conditions together, all the load-limit ones together), one short bullet "
    "each. For each: what has to happen, with its number and unit, and whether it acts on "
    "its own or only together with others. Put the interlocks, permissives and bypasses "
    "here too -- say what blocks the signal and when. Give the RESULT of the internal "
    "arithmetic, not the arithmetic itself.\n"
    "(3) HOW IT BEHAVES IN OPERATION -- walk it in the order the operator would see it: "
    "the normal state; what has to happen for it to change, including how long the "
    "condition must persist and how many channels must agree; whether it holds itself in "
    "once it acts; what makes it release again -- reset point, reset command, or by "
    "itself -- and what the deadband means in practice; what changes in the plant the "
    "moment it acts. Say plainly whether one faulty instrument could raise it alone.\n"
    "(4) THE NUMBERS -- every set point, reset point, delay and limit in one place, each "
    "with its unit and a few words on what it means. Table if the rows really share the "
    "same columns, bullets otherwise. Nothing else goes in this section.\n"
    "\n"
    "RULES: use ONLY facts from the context or from tool results. Never invent a signal, "
    "a value or a connection. Keep numbers and thresholds exactly as given. Do not ask the "
    "user for more context -- fetch it yourself."
)

# Ban dung khi chay O CHE DO KHONG CO TOOL (vd lan goi dau bi treo nen thu lai khong
# bat may chu MCP). Neu van dua prompt goc thi AI se co goi get_source va bao loi/di
# vong; o day noi ro la khong co tool, va van BAT BUOC liet ke nhanh chua giai duoc.
NO_TOOL_NOTE = (
    "\n\nIMPORTANT - NO TOOLS ARE AVAILABLE IN THIS RUN. Do not attempt to call "
    "get_source or block_function. Answer from the given context only. Keep the same "
    "four sections and the same plain language; simply leave out what the context does "
    "not tell you, instead of listing what is missing."
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


def build_prompt(name, context, question=None, lang="en", use_tools=True):
    q = question or ("Explain how the signal '%s' works and what it is for." % name)
    langline = ("Answer in Vietnamese." if lang == "vi" else "Answer in English.")
    head = SYSTEM_PROMPT if use_tools else (SYSTEM_PROMPT + NO_TOOL_NOTE)
    return "%s\n%s\n\n--- SIGNAL CONTEXT ---\n%s\n--- END CONTEXT ---\n\n%s" % (
        head, langline, context, q)
