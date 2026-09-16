# -*- coding: utf-8 -*-
"""Dung DUONG DAC TINH (hoac BANG GIA TRI) cho khoi analog, de ve trong cua so Help.

Cach lam giong het core/block_timing.py: khong viet lai nghia cua khoi o day. Duong
cong sinh ra bang cach quet mot dau vao mau qua CHINH ham ma bo mo phong dang chay:
  - ho analog        -> core/sheet_sim._eval_analog()
  - ho so sanh so    -> core/sheet_sim._compute()   (nhanh CMP)
  - vong tre 20FB/FC -> core/sheet_dyn._step_cmp()  (nhanh kind 'C')
  - hang so digital  -> core/sheet_sim._compute()   (nhanh CONST, co doc cong tac DSW)
Nho vay hinh ve va ket qua Simulate khong the noi hai dang khac nhau.

Moi tham so (he so, muc gioi han, nguong, bang gay khuc) lay tu DUNG khoi nguoi dung
bam - hai khoi F(x) canh nhau co the co hai bang gay khuc hoan toan khac nhau.

Van ban tra ra man hinh la TIENG ANH theo yeu cau; chu thich trong code van la tieng
Viet khong dau nhu phan con lai cua du an.
"""
from __future__ import annotations

from . import sheet_sim as SS
from . import cond_tree as CT
from . import sheet_dyn as SD
from .help_i18n import tr

_N = 240        # so diem quet. Du min cho duong gay khuc, chua du nang de treo may.

# Khoi co MOT dau vao analog -> ve duoc do thi vao/ra.
XY_OPS = {"FUNC", "GAIN", "ABS", "CLAMPHI", "CLAMPLO", "CLAMPHI_P", "CLAMPLO_P",
          "CMPHI_P", "CMPLO_P", "LIMIT_P", "CMP"}
# Khoi NHIEU dau vao: khong co "duong cong" nao ca (mot dau vao chay thi cac dau kia
# dung yen, ve ra chi la mot duong thang vo nghia). Hien cong thuc that + bang gia tri.
TABLE_OPS = {"ADD", "SUB", "MUL", "DIV", "MULG", "AVG", "WSUM", "SIGNSUM",
             "MAX", "MIN", "MID"}

KIND_XY = "xy"
KIND_TABLE = "table"
KIND_VALUE = "value"

# Cau chot cua tung ho: PHAI NHIN CHO NAO tren hinh moi hieu khoi lam gi.
_GHI = {
    "FUNC": "The dots are the break points stored in the parameter table of THIS block. "
            "Outside the table the output is held flat at the first and the last point.",
    "GAIN": "A straight line through zero - the slope is the gain set on this block.",
    "ABS": "Negative inputs are folded back up, so the output never goes below zero.",
    "CLAMPHI": "Below the limit the output follows the input exactly; above it the "
               "output stops flat at the limit.",
    "CLAMPLO": "Above the limit the output follows the input exactly; below it the "
               "output stops flat at the limit.",
    "CLAMPHI_P": "Below the limit the output follows the input exactly; above it the "
                 "output stops flat at the limit.",
    "CLAMPLO_P": "Above the limit the output follows the input exactly; below it the "
                 "output stops flat at the limit.",
    "LIMIT_P": "In steady state this block passes the input straight through; the only "
               "thing left is the pair of limits that cut the top and the bottom off.",
    "CMPHI_P": "The output is a 0/1 flag, not a number.",
    "CMPLO_P": "The output is a 0/1 flag, not a number.",
    "CMP": "The output is a 0/1 flag, not a number.",
}


def _op(code):
    """Phep toan cua ma khoi, gop hai bang ngu nghia dung nhu bo mo phong: bang analog
    truoc, bang logic de len tren (40A4/40A5/4018 la hang so DIGITAL du ten giong 4052)."""
    code = (code or "").upper()
    s = dict(SS._analog_sem().get(code) or {})
    s.update(CT._sem().get(code) or {})
    return s.get("op"), s


def _num(v):
    return SS._num(v)


def _isnum(v):
    return SS._isnum(v)


def _so(v):
    """So gon de dat len nhan truc / nhan nguong."""
    if v is None:
        return "-"
    if abs(v) >= 1e5 or (v and abs(v) < 1e-3):
        return "%.4g" % v
    return "%g" % round(v, 4)


def _rec_analog(db, sheet, bid):
    """(ngo ra chinh, ngo ra co bao) cua DUNG khoi bid trong bang khoi analog that.

    Ho limiter (2103/2104/210F...) co HAI ngo ra: oidx 0 la gia tri da kep, oidx 1 la
    co bao "dang bi kep" - ve them co nay thanh vung to bong tren do thi thi nguoi doc
    thay ngay muc cai nam o dau."""
    chinh = co = None
    for n, r in SS._analog_producers(db, sheet).items():
        if r.get("bid") != bid:
            continue
        if r.get("oidx", 0) == 0 and chinh is None:
            chinh = (n, r)
        elif co is None:
            co = (n, r)
    return chinh, co


def _rec_digital(db, sheet, bid):
    """(net ra, ban ghi) cua khoi bid trong bang khoi digital that."""
    for n, p in CT._producers(db, sheet).items():
        if p.get("bid") == bid:
            return n, p
    return None


def _chon_x(ins):
    """(chan duoc quet, cac chan giu nguyen). Chan gioi han cua ho CLAMPHI/CLAMPLO
    mang ten 'L', chan tin hieu mang ten 'X' - quet nham chan L thi ra mot do thi
    nguoc hoan toan."""
    ana = [d for d in ins if d.get("ptype") != 1] or list(ins)
    if not ana:
        return None, []
    if len(ana) == 1:
        return ana[0], []
    for d in ana:
        if (d.get("name") or "").strip().upper() in ("X", "IN", "F"):
            return d, [o for o in ana if o is not d]
    return ana[0], ana[1:]


def _span(moc, x_now=None, doi_xung=False):
    """Khoang quet truc X, tinh tu cac diem DANG CHU Y cua khoi (nguong, muc gioi han,
    diem gay khuc) cong voi gia tri dang chay.

    Khoi analog cua nha may khong co thang do chuan nao: mot khoi so sanh cai 30000,
    khoi ben canh cai 0,05. Lay khoang co dinh thi mot trong hai hinh thanh duong thang
    li. Vay khoang phai bam theo chinh cac con so cua khoi, noi rong 25% de con thay
    doan bang phang hai ben nguong."""
    xs = [v for v in list(moc) + ([x_now] if _isnum(x_now) else []) if _isnum(v)]
    if not xs:
        lo, hi = -10.0, 10.0
    else:
        lo, hi = float(min(xs)), float(max(xs))
        if hi - lo < 1e-9:
            d = max(abs(lo), 1.0)
            lo, hi = lo - d, hi + d
        else:
            d = (hi - lo) * 0.25
            lo, hi = lo - d, hi + d
    if doi_xung:
        a = max(abs(lo), abs(hi))
        lo, hi = -a, a
    return lo, hi


def _luoi(lo, hi, n=_N):
    b = (hi - lo) / float(n)
    return [lo + b * k for k in range(n + 1)]


def _vung(xs, ys):
    """Cac doan lien tuc ma ys == 1 -> [(x0, x1)]. Dung to bong co bao cua limiter."""
    ra = []
    d = None
    for i, v in enumerate(ys):
        on = _isnum(v) and v >= 0.5
        if on and d is None:
            d = xs[i]
        elif not on and d is not None:
            ra.append((d, xs[i])); d = None
    if d is not None:
        ra.append((d, xs[-1]))
    return ra


# ------------------------------------------------------------------ quet that
def _quet_analog(onet, rec, xnet, giu, db, sheet, xs):
    """Cho tung gia tri x chay qua CHINH _eval_analog() cua bo mo phong."""
    ap = {onet: rec}
    ys = []
    for x in xs:
        val = dict(giu)
        val[xnet] = x
        try:
            ys.append(SS._eval_analog(onet, ap, val, db, sheet))
        except Exception:
            ys.append(None)
    return ys


def _quet_cmp_digital(onet, p, xnet, giu, thr, xs):
    """Ho so sanh so (404E/4050...) nam o duong DIGITAL: chay qua _compute()."""
    sem = CT._sem()
    prod = {onet: p}
    ys = []
    for x in xs:
        val = dict(giu)
        val[xnet] = x
        try:
            ys.append(SS._compute(onet, prod, sem, val, {onet: thr}, None))
        except Exception:
            ys.append(None)
    return ys


def _quet_tre(code, on, off, xs):
    """Vong tre 20FB/20FC: chay qua CHINH _step_cmp() cua bo mo phong dong.

    Quet HAI luot - luot len bat dau tu trang thai 0, luot xuong bat dau tu 1 - vi day
    la khoi CO NHO: mot luot khong the ve ra vong tre."""
    b = {"hi": code in SD.CMP_HI_CODES, "on": on, "off": off, "y": 0}
    len_ = []
    for x in xs:
        SD._step_cmp(b, x)
        len_.append(b["y"])
    b = {"hi": code in SD.CMP_HI_CODES, "on": on, "off": off, "y": 1}
    xuong = []
    for x in reversed(xs):
        SD._step_cmp(b, x)
        xuong.append(b["y"])
    xuong.reverse()
    return len_, xuong


# ------------------------------------------------------------------ ket qua
def _rong():
    return {"ok": False, "why": "", "op": "", "kind": "", "from_db": False, "note": "",
            "x": [], "y": [], "yb": [], "digital": False, "bpts": [], "guides": [],
            "shade": [], "xlabel": tr("Input"), "ylabel": tr("Output"),
            "x_now": None, "y_now": None, "formula": "", "rows": [], "out": None,
            "settings": []}


def curve(code, db_path=None, sheet_id=None, bid=None, values=None):
    """Duong dac tinh / bang gia tri cua DUNG khoi nay.

    -> {"ok", "why", "kind", "op", ...}  (xem _rong() cho danh sach khoa day du)
    """
    ket = _rong()
    code = (code or "").upper()
    op, sem = _op(code)
    ket["op"] = op or ""
    if not op or op not in (XY_OPS | TABLE_OPS | {"CONST"}):
        ket["why"] = (tr("This block has no input-to-output relation that can be drawn as a "
                      "curve or a table."))
        return ket
    if not (db_path and sheet_id is not None and bid is not None):
        # Khac ho timer: hinh dang cua khoi analog do CHINH tham so quyet dinh (he so,
        # muc gioi han, bang gay khuc), khong co "hinh dang chung" nao de ve tam.
        ket["why"] = (tr("The characteristic of this block is defined by its own parameters, "
                      "so Help must be opened from a block on a sheet."))
        return ket
    vals = values or {}
    try:
        if op == "CONST":
            return _lam_hang_so(ket, code, sem, db_path, sheet_id, bid)
        if op == "CMP":
            return _lam_cmp(ket, code, sem, db_path, sheet_id, bid, vals)
        if op in XY_OPS:
            return _lam_xy(ket, code, op, db_path, sheet_id, bid, vals)
        return _lam_bang(ket, code, op, db_path, sheet_id, bid, vals)
    except Exception as e:
        ket["why"] = tr("This block could not be read from the project file (%s).") % e
        return ket


def _lam_hang_so(ket, code, sem, db, sheet, bid):
    """Hang so: khong co dau vao nao het, ve do thi la vo nghia - in thang tri so."""
    ket["kind"] = KIND_VALUE
    chinh, _co = _rec_analog(db, sheet, bid)
    if chinh:
        onet, rec = chinh
        v = SS._eval_analog(onet, {onet: rec}, {}, db, sheet)
        ket.update(ok=True, out=v, from_db=v is not None,
                   formula="Y = %s" % _so(v) if v is not None else "Y = ?")
        ket["note"] = (tr("The value comes from the parameters of THIS block, so two blocks "
                       "with the same code can feed two different numbers."))
        if v is None:
            ket["note"] = (tr("The constant of this block could not be read from the project "
                           "file."))
        ket["settings"] = key_settings(db, sheet, bid, code)
        return ket
    rd = _rec_digital(db, sheet, bid)
    if not rd:
        ket["why"] = tr("This block was not found on the sheet, so its value cannot be read.")
        return ket
    onet, p = rd
    cst = {onet: SS._const_value(db, sheet, p)}
    v = SS._compute(onet, {onet: p}, CT._sem(), {}, None, cst)
    ket.update(ok=True, out=v, from_db=True, digital=True, formula="Y = %d" % int(v or 0))
    if cst[onet] is not None:
        ket["note"] = (tr("This is a hand switch: the 0 or 1 is stored on THIS block and is "
                       "the number printed inside the box on the sheet."))
    else:
        ket["note"] = (tr("A fixed 0/1 source built into the block code - it carries no "
                       "setting of its own."))
    ket["settings"] = key_settings(db, sheet, bid, code)
    return ket


def _lam_cmp(ket, code, sem, db, sheet, bid, vals):
    """Ho so sanh so. Nam o duong DIGITAL cua bo giai chu khong phai duong analog."""
    rd = _rec_digital(db, sheet, bid)
    if not rd:
        ket["why"] = tr("This block was not found on the sheet, so its setpoint cannot be read.")
        return ket
    onet, p = rd
    c = SS.cmp_blocks(db, sheet).get(onet) or {}
    thr, reset = c.get("thr"), c.get("reset")
    unit = c.get("unit") or ""
    ins = [i[0] for i in p.get("ins", [])]
    if not ins:
        ket["why"] = tr("This comparator has no input wired, so there is nothing to sweep.")
        return ket
    xnet = ins[0]
    giu = {n: vals.get(n) for n in ins[1:]}
    x_now = vals.get(xnet)
    if thr is None:
        # Bien the so sanh HAI TIN HIEU (404F/4051): nguong den tu day, khong tu tham so.
        moc = [v for v in giu.values() if _isnum(v)]
        if not moc:
            ket["why"] = (tr("This comparator takes its setpoint from a wire, and no live "
                          "value is available for it, so the switching point is not known."))
            return ket
        guides = [(moc[0], tr("setpoint from wire = %s") % _so(moc[0]))]
    else:
        guides = [(thr, "Set = %s%s" % (_so(thr), (" " + unit) if unit else ""))]
        moc = [thr]
        if reset is not None and reset != thr:
            guides.append((reset, "Reset = %s%s" % (_so(reset),
                                                    (" " + unit) if unit else "")))
            moc.append(reset)
    lo, hi = _span(moc, x_now)
    xs = _luoi(lo, hi)
    ys = _quet_cmp_digital(onet, p, xnet, giu, thr, xs)
    ket.update(ok=True, kind=KIND_XY, digital=True, from_db=thr is not None,
               x=xs, y=ys, guides=guides,
               xlabel=tr("Input") + ((" (%s)" % unit) if unit else ""),
               ylabel=tr("Output (0/1)"), x_now=x_now if _isnum(x_now) else None)
    if _isnum(x_now):
        ket["y_now"] = _quet_cmp_digital(onet, p, xnet, giu, thr, [x_now])[0]
    note = tr(_GHI["CMP"])
    if reset is not None and thr is not None and reset != thr:
        # Diem tro ve co that trong DB nhung KHONG bo mo phong nao dung toi - noi thang
        # ra con hon de nguoi doc tuong hinh nay da co vong tre.
        note += (tr(" This block also carries a RETURN point of %s in the project file. The "
                 "simulator switches on the Set point only, so the drawing shows one edge, "
                 "not a hysteresis loop.") % _so(reset))
    ket["note"] = note
    ket["settings"] = key_settings(db, sheet, bid, code)
    return ket


def _lam_xy(ket, code, op, db, sheet, bid, vals):
    """Duong dac tinh cua khoi analog mot dau vao."""
    chinh, co = _rec_analog(db, sheet, bid)
    if not chinh:
        ket["why"] = (tr("This block was not found in the analog part of the sheet, so its "
                      "characteristic cannot be traced."))
        return ket
    onet, rec = chinh
    xd, khac = _chon_x(rec.get("ins") or [])
    if xd is None or not xd.get("net"):
        ket["why"] = tr("This block has no analog input wired, so there is nothing to sweep.")
        return ket
    xnet = xd["net"]
    x_now = vals.get(xnet)
    pm = SS._params(db, sheet).get(bid, {})
    sem = SS._analog_sem().get(code, {})

    giu = {}
    thieu = []
    for d in khac:
        v = vals.get(d.get("net"))
        if _isnum(v):
            giu[d["net"]] = v
        else:
            thieu.append(d)

    moc, guides, bpts, from_db = [], [], [], True
    xlabel = tr("Input")
    ylabel = tr("Output")

    if op == "FUNC":
        fi = SS.func_info(db, sheet, bid)
        bpts = list(fi["pts"])
        if len(bpts) < 2:
            ket["why"] = (tr("The break-point table of this F(x) block is empty or has a "
                          "single point, so there is no curve to draw."))
            return ket
        moc = [bpts[0][0], bpts[-1][0]]
        if fi["xunit"]:
            xlabel = tr("Input (%s)") % fi["xunit"]
        if fi["yunit"]:
            ylabel = tr("Output (%s)") % fi["yunit"]
    elif op in ("CLAMPHI_P", "CLAMPLO_P"):
        lim = _num(pm.get(sem.get("lim", "1")))
        if lim is None:
            ket["why"] = (tr("The limit of this block is set from a controller register, not "
                          "from a parameter, so the real limit is not in the project file."))
            return ket
        moc = [lim]
        guides = [(lim, ("HL = %s" if op == "CLAMPHI_P" else "LL = %s") % _so(lim))]
    elif op in ("CMPHI_P", "CMPLO_P"):
        on = _num(pm.get(sem.get("on", "1")))
        off = _num(pm.get(sem.get("off", "2")))
        if on is None:
            ket["why"] = (tr("The setpoint of this block is set from a controller register, "
                          "not from a parameter, so it is not in the project file."))
            return ket
        if off is None:
            off = on
        moc = [on, off]
        guides = [(on, tr("ON at %s") % _so(on))]
        if off != on:
            guides.append((off, tr("OFF at %s") % _so(off)))
    elif op == "LIMIT_P":
        hl = _num(pm.get(sem.get("hl", "2")))
        ll = _num(pm.get(sem.get("ll", "3")))
        moc = [v for v in (hl, ll) if v is not None]
        if hl is not None:
            guides.append((hl, "HL = %s" % _so(hl)))
        if ll is not None:
            guides.append((ll, "LL = %s" % _so(ll)))
        if not moc:
            from_db = False
    elif op in ("CLAMPHI", "CLAMPLO"):
        # Muc gioi han den tu mot CHAN VAO (day tin hieu), khong phai tham so.
        lnet = khac[0]["net"] if khac else None
        lim = giu.get(lnet)
        if not _isnum(lim):
            ket["why"] = (tr("The limit of this block comes in on a wire and no live value is "
                          "available for it, so the switching point is not known. Run "
                          "Simulate first, then open Help again."))
            return ket
        moc = [lim]
        guides = [(lim, tr("limit = %s") % _so(lim))]
        # Muc kep khong nam trong file du an ma den tu day: doi input doi thi do thi doi
        # theo. Ha co from_db de chu thich noi ro, dung khoe la "doc tu file du an".
        from_db = False
    elif op == "GAIN":
        g = _num(pm.get("2"))
        if g is None:
            ket["why"] = tr("The gain of this block could not be read from the project file.")
            return ket
        from_db = True
    elif op == "ABS":
        pass

    if thieu and op not in ("CLAMPHI", "CLAMPLO"):
        ket["why"] = (tr("Another input of this block has no live value, so the output cannot "
                      "be traced. Run Simulate first, then open Help again."))
        return ket

    lo, hi = _span(moc, x_now, doi_xung=(op == "ABS"))
    xs = _luoi(lo, hi)
    ys = _quet_analog(onet, rec, xnet, giu, db, sheet, xs)
    if not any(_isnum(v) for v in ys):
        ket["why"] = (tr("The output of this block stays undefined over the whole sweep, so "
                      "there is no curve to draw."))
        return ket

    yb = []
    if op in ("CMPHI_P", "CMPLO_P"):
        # Lop TINH chi biet nguong BAT; vong tre that nam o lop DONG. Ve ca hai luot
        # moi dung voi cai nguoi dung se thay khi bam Run.
        on = _num(pm.get(sem.get("on", "1")))
        off = _num(pm.get(sem.get("off", "2")))
        if off is None:
            off = on
        ylen, yxuong = _quet_tre(code, on, off, xs)
        ys, yb = ylen, (yxuong if off != on else [])

    shade = []
    if co:
        cnet, crec = co
        cys = _quet_analog(cnet, crec, xnet, giu, db, sheet, xs)
        shade = [(a, b, tr("flag = 1")) for a, b in _vung(xs, cys)]

    digital = op in ("CMPHI_P", "CMPLO_P")
    y_now = None
    if _isnum(x_now):
        y_now = _quet_analog(onet, rec, xnet, giu, db, sheet, [x_now])[0]
    ket.update(ok=True, kind=KIND_XY, x=xs, y=ys, yb=yb, digital=digital, bpts=bpts,
               guides=guides, shade=shade, xlabel=xlabel, ylabel=ylabel,
               from_db=from_db, x_now=x_now if _isnum(x_now) else None, y_now=y_now)
    note = tr(_GHI.get(op, ""))
    if yb:
        note += (tr(" The block has a dead band: it switches ON at one level and back OFF at "
                 "another, so the rising and the falling path are two different lines."))
    if shade:
        note += (tr(" The shaded band is where the second output of this block - the 'being "
                 "limited' flag - is 1."))
    ket["note"] = note
    ket["settings"] = key_settings(db, sheet, bid, code)
    return ket


def _ten_chan(ins, op=""):
    """Ten hien tren cong thuc cho tung chan vao.

    Ten chan trong bang macro khong phai luc nao cung dat duoc vao cong thuc: khoi MID
    dat ten chan giua la "MID" (do la nhan VE giua than khoi, khong phai ten dau vao)
    nen de nguyen thi ra "median(X1, MID, X3)"; khoi tru dat ten hai chan la "+" va "-"
    nen ra "Y = + - -", khong ai doc noi."""
    ra = []
    for i, d in enumerate(ins):
        nm = (d.get("name") or "").strip()
        if not nm or nm.upper() == (op or "").upper():
            nm = "X%d" % (i + 1)
        elif not nm[0].isalnum():
            nm = "(%s)" % nm
        ra.append(nm)
    return ra


def _cong_thuc(op, ten, pm):
    """Cong thuc THAT cua khoi, da thay he so doc duoc tu tham so vao."""
    if op == "ADD":
        return "Y = " + " + ".join(ten)
    if op == "MUL":
        return "Y = " + " * ".join(ten)
    if op == "SUB":
        a = ten[0] if ten else "A"
        b = ten[1] if len(ten) > 1 else "B"
        return "Y = %s - %s" % (a, b)
    if op == "DIV":
        a = ten[0] if ten else "A"
        b = ten[1] if len(ten) > 1 else "B"
        return "Y = %s / %s" % (a, b)
    if op == "AVG":
        return "Y = ( %s ) / %d" % (" + ".join(ten), max(1, len(ten)))
    if op == "MAX":
        return "Y = max( %s )" % ", ".join(ten)
    if op == "MIN":
        return "Y = min( %s )" % ", ".join(ten)
    if op == "MID":
        return "Y = median( %s )" % ", ".join(ten)
    if op == "MULG":
        g = _num(pm.get("2"))
        g = 1.0 if g is None else g
        return "Y = %s * %s" % (" * ".join(ten), _so(g))
    if op == "WSUM":
        cum = []
        for i, t in enumerate(ten):
            g = _num(pm.get(str(i + 2)))
            cum.append("%s * %s" % (_so(0.0 if g is None else g), t))
        return "Y = " + " + ".join(cum)
    if op == "SIGNSUM":
        return "Y = " + " ".join(ten)
    return "Y = f( %s )" % ", ".join(ten)


def _lam_bang(ket, code, op, db, sheet, bid, vals):
    """Khoi nhieu dau vao: cong thuc that + gia tri that dang chay tren tung chan."""
    chinh, _co = _rec_analog(db, sheet, bid)
    if not chinh:
        ket["why"] = (tr("This block was not found in the analog part of the sheet, so its "
                      "inputs cannot be listed."))
        return ket
    onet, rec = chinh
    ins = rec.get("ins") or []
    if not ins:
        ket["why"] = tr("This block has no input wired, so there is nothing to show.")
        return ket
    pm = SS._params(db, sheet).get(bid, {})
    goc = _ten_chan(ins, op)
    ten = list(goc)
    if op == "SIGNSUM":
        signs = rec.get("signs") or []
        ten = ["%s%s" % ("- " if (signs[i] if i < len(signs) else "+") == "-" else
                         ("" if i == 0 else "+ "), t) for i, t in enumerate(ten)]
    rows = []
    val = {}
    for i, d in enumerate(ins):
        v = vals.get(d.get("net"))
        if _isnum(v):
            val[d["net"]] = v
        rows.append((goc[i], d.get("net") or "-",
                     _so(v) if _isnum(v) else tr("not known")))
    out = None
    if len(val) == len(ins):
        out = SS._eval_analog(onet, {onet: rec}, val, db, sheet)
    ket.update(ok=True, kind=KIND_TABLE, formula=_cong_thuc(op, ten, pm), rows=rows,
               out=out, from_db=True, ylabel=onet)
    if out is None:
        ket["note"] = (tr("This block has more than one input, so it has no single curve - "
                       "the formula above is the whole story. Run Simulate to fill the "
                       "live values in."))
    else:
        ket["note"] = (tr("This block has more than one input, so it has no single curve. "
                       "The output below is computed by the same evaluator the simulator "
                       "runs, on the values sitting on this block right now."))
    ket["settings"] = key_settings(db, sheet, bid, code)
    return ket


def key_settings(db_path, sheet_id, bid, code):
    """[(nhan, gia tri)] cai dat QUAN TRONG cua DUNG khoi analog nay, bang tieng Anh.

    Bang tham so ben duoi cua so Help van hien du moi dong, nhung dong quan trong nhat
    thuong KHONG CO TEN (macro_analog.json chi dat ten cho mot phan), vi du khoi F(x):
    param 2 la so diem, param 6 tro di moi la bang gay khuc."""
    if not (db_path and sheet_id is not None and bid is not None):
        return []
    code = (code or "").upper()
    op, _s = _op(code)
    if not op:
        return []
    try:
        pm = SS._params(db_path, sheet_id).get(bid, {})
        sem = SS._analog_sem().get(code, {})
    except Exception:
        return []
    out = []
    try:
        if op == "CONST":
            v = _num(pm.get("2"))
            if v is not None:
                out.append((tr("Constant value"), _so(v)))
        elif op == "GAIN":
            v = _num(pm.get("2"))
            if v is not None:
                out.append((tr("Gain"), _so(v)))
        elif op == "MULG":
            v = _num(pm.get("2"))
            if v is not None:
                out.append((tr("Gain"), _so(v)))
        elif op == "FUNC":
            fi = SS.func_info(db_path, sheet_id, bid)
            if fi["pts"]:
                out.append((tr("Break points"), tr("%d points") % len(fi["pts"])))
                out.append((tr("X range"), "%s .. %s%s" % (_so(fi["pts"][0][0]),
                                                       _so(fi["pts"][-1][0]),
                                                       (" " + fi["xunit"]) if fi["xunit"] else "")))
                out.append((tr("Y range"), "%s .. %s%s" % (_so(min(p[1] for p in fi["pts"])),
                                                       _so(max(p[1] for p in fi["pts"])),
                                                       (" " + fi["yunit"]) if fi["yunit"] else "")))
            if fi["name"]:
                out.append((tr("Function name"), fi["name"]))
        elif op in ("CLAMPHI_P", "CLAMPLO_P"):
            v = _num(pm.get(sem.get("lim", "1")))
            out.append((tr("Upper limit HL") if op == "CLAMPHI_P" else tr("Lower limit LL"),
                        _so(v) if v is not None
                        else tr("set from a controller register, not from a parameter")))
        elif op in ("CMPHI_P", "CMPLO_P"):
            on = _num(pm.get(sem.get("on", "1")))
            off = _num(pm.get(sem.get("off", "2")))
            out.append((tr("Setpoint (switch on)"), _so(on) if on is not None
                        else tr("set from a controller register")))
            if off is not None and on is not None and off != on:
                out.append((tr("Return point (switch off)"), _so(off)))
        elif op == "LIMIT_P":
            hl = _num(pm.get(sem.get("hl", "2")))
            ll = _num(pm.get(sem.get("ll", "3")))
            if hl is not None:
                out.append((tr("Upper limit HL"), _so(hl)))
            if ll is not None:
                out.append((tr("Lower limit LL"), _so(ll)))
        elif op == "CMP":
            c = SS.cmp_blocks(db_path, sheet_id)
            rec = None
            for _n, d in c.items():
                if d.get("bid") == bid:
                    rec = d
                    break
            if rec:
                u = (" " + rec["unit"]) if rec.get("unit") and rec["unit"] != "-" else ""
                if rec.get("thr") is not None:
                    out.append((tr("Set point"), _so(rec["thr"]) + u))
                if rec.get("reset") is not None and rec["reset"] != rec.get("thr"):
                    out.append((tr("Return point"), _so(rec["reset"]) + u))
        elif op == "WSUM":
            gs = []
            i = 2
            while pm.get(str(i)) is not None:
                g = _num(pm.get(str(i)))
                if g is None:
                    break
                gs.append(_so(g))
                i += 1
            if gs:
                out.append((tr("Coefficients"), ", ".join(gs)))
    except Exception:
        return out
    return out
