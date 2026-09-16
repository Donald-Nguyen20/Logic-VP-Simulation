# -*- coding: utf-8 -*-
"""Dung DANG SONG cho khoi delay/xung, de ve trong cua so Help.

Khong tu viet lai nghia cua tung ho timer o day. Sóng duoc sinh bang cach cho mot dau
vao mau chay qua CHINH ham core/sheet_dyn._step_timer() - ham ma bo mo phong dang chay -
nen ban ve va ket qua mo phong khong bao gio noi hai dang khac nhau.

Thoi gian T lay tu DUNG khoi nguoi dung bam (CAD_BLOCK_PARAM qua SS.timer_secs), khong
phai gia tri mac dinh cua ma khoi: hai khoi DI canh nhau co the cai 3 giay va 600 giay.
Khi khong mo duoc file .db thi van ve, nhung danh dau ro la vi du (from_db = False).
"""
from __future__ import annotations

from . import sheet_dyn as SD
from .help_i18n import tr

# Dau vao mau, tinh theo boi so cua T. Xung thu hai [4.2u, 4.7u] co CHU Y: no ngan hon
# T, la cho phan biet ro nhat giua cac ho - DI nuot luon, PO van phat du xung, TDWO cat
# giua chung. Thieu doan nay thi ba ho ve ra giong het nhau.
# Cac khoang NGHI deu dai hon T (1.8u va 1.5u): ho off-delay (DT) giu dau ra them dung T
# sau khi dau vao tat, nghi ngan hon T thi dau ra khong bao gio kip ha - do da do: voi
# khoang nghi 0.8u thi ca 8 ma DT ve ra mot duong thang li khong noi len duoc gi.
_KICH = ((0.0, 0), (0.6, 1), (2.4, 0), (4.2, 1), (4.7, 0), (6.2, None))
_NBUOC = 320

# Khong doc duoc T thi van phai ve duoc hinh dang - ghi ro day la vi du. So 10 tinh
# theo DON VI CUA KHOI: ho DIL cai bang phut nen phai la 10 phut, neu de 10 giay thi
# nhan tren truc thanh "T = 0,166667 min".
_T_MAU = 10.0
_OFF_MAU = 10.0


def _muc(mocs, t):
    """Gia tri dau vao mau tai thoi diem t."""
    v = 0
    for m, x in mocs:
        if x is None:
            break
        if t + 1e-12 >= m:
            v = x
    return v


def _khoi(fam, T, toff, tunit):
    """Dict trang thai dung hinh dang ma sheet_dyn._timer_block() sinh ra."""
    return {"bid": None, "code": "", "kind": "T", "out": None, "x": None, "tnet": None,
            "tmr": fam, "tunit": tunit, "T": T, "toff": toff,
            "y": 0, "acc": 0.0, "xp": None}


def _chay(fam, T, toff, tunit, mocs, tong, n):
    """Cho dau vao mau chay qua bo dem THAT -> (t[], x[], y[])."""
    dt = tong / float(n)
    b = _khoi(fam, T, toff, tunit)
    ts, xs, ys = [], [], []
    for k in range(n + 1):
        t = k * dt
        x = _muc(mocs, t)
        SD._step_timer(b, x, {}, dt)
        ts.append(t); xs.append(x); ys.append(b["y"])
    return ts, xs, ys


def _suon(a, len_=True):
    """Chi so cac buoc ma 'a' doi tu 0 len 1 (len_=True) hoac tu 1 ve 0."""
    r = []
    for i in range(1, len(a)):
        if len_ and a[i] and not a[i - 1]:
            r.append(i)
        elif not len_ and a[i - 1] and not a[i]:
            r.append(i)
    return r


def _nhan_t(T, tunit):
    if tunit == "min":
        return "T = %g min" % (T / 60.0)
    return "T = %g s" % T


def _danh_dau(fam, ts, xs, ys, T, toff, tunit):
    """[(t_dau, t_cuoi, nhan, hang)] - doan thoi gian dang chu y tren truc.

    hang: 0 = ve giua hai duong (do tre giua vao va ra), 1 = ve duoi duong ra (be rong
    xung). Danh dau dat DUNG doan ma T co tac dung, de nguoi doc thay so 60 s tren ban
    ve chinh la so dang nam trong bang tham so ben duoi.
    """
    xl, yl, yx = _suon(xs), _suon(ys), _suon(ys, False)
    lab = _nhan_t(T, tunit)
    if fam in ("DI", "DIL"):
        if xl and yl:
            return [(ts[xl[0]], ts[yl[0]], lab, 0)]
    elif fam == "DT":
        xf = _suon(xs, False)
        if xf and yx:
            return [(ts[xf[0]], ts[yx[0]], lab, 0)]
    elif fam in ("PO", "TDWO"):
        if yl and yx and yx[0] > yl[0]:
            return [(ts[yl[0]], ts[yx[0]], lab, 1)]
    elif fam == "PG":
        if len(yl) >= 2 and yx:
            r = [(ts[yl[0]], ts[yx[0]], tr("ON %g s") % T, 1)]
            r.append((ts[yx[0]], ts[yl[1]], tr("OFF %g s") % (toff or 0.0), 1))
            return r
    elif fam in ("1SH1", "1SH2"):
        if yl and yx and yx[0] > yl[0]:
            return [(ts[yl[0]], ts[yx[0]], tr("1 CPU cycle"), 1)]
    return []


# Cau chot cua tung ho: cho biet PHAI NHIN CHO NAO tren hinh moi thay khac biet.
_GHI = {
    "DI":   "The second input pulse is shorter than T, so the output never comes on. "
            "The delay restarts from zero every time the input drops.",
    "DIL":  "Same as DI but the setting is in minutes. The second input pulse is shorter "
            "than T, so the output never comes on.",
    "DT":   "The output follows the input immediately when it comes on, and only the "
            "falling edge is delayed by T.",
    "PO":   "The pulse always lasts the full T once started - dropping the input early "
            "does not cut it short. Only a rising edge can start a new pulse.",
    "TDWO": "Like PO, but dropping the input wipes the pulse out at once - see the "
            "second, shorter input.",
    "1SH1": "The pulse lasts exactly one controller cycle, whatever the input does "
            "afterwards. There is no time setting on this block.",
    "1SH2": "The pulse lasts exactly one controller cycle and is fired by the FALLING "
            "edge of the input. There is no time setting on this block.",
    "PG":   "While the input is on, the output keeps square-waving: T on, then the OFF "
            "time, over and over. Dropping the input stops it and resets the phase.",
}


def timing_wave(code, db_path=None, sheet_id=None, bid=None):
    """Dang song cua DUNG khoi nay.

    -> {"ok", "why", "fam", "T", "toff", "tunit", "from_db", "t", "x", "y", "marks",
        "note"}
    """
    ket = {"ok": False, "why": "", "fam": "", "T": None, "toff": None, "tunit": "s",
           "from_db": False, "t": [], "x": [], "y": [], "marks": [], "note": ""}
    code = (code or "").upper()
    try:
        from .cond_tree import _sem
        sem = (_sem() or {}).get(code) or {}
    except Exception:
        sem = {}
    fam = sem.get("tmr")
    if not fam:
        ket["why"] = tr("This block is not a timer, so there is no waveform to draw.")
        return ket
    ket["fam"] = fam
    tunit = sem.get("tunit") or "s"
    ket["tunit"] = tunit

    T = toff = None
    if db_path and sheet_id is not None and bid is not None:
        try:
            import core.sheet_sim as SS
            T = SS.timer_secs(db_path, sheet_id, sem, bid)
            if sem.get("toff"):
                toff = SS._num(SS._params(db_path, sheet_id).get(bid, {}).get(sem["toff"]))
        except Exception:
            T = toff = None
    ket["from_db"] = T is not None
    if T is None or T <= 0:
        # Bien the "T:input" (thoi gian den tu day noi vao chan T) cung roi vao day: chua
        # chay mo phong thi khong biet so, nhung HINH DANG van dung nen cu ve.
        T = _T_MAU * (60.0 if tunit == "min" else 1.0)
    if fam == "PG" and (toff is None or toff <= 0):
        toff = _OFF_MAU if not ket["from_db"] else T
    ket["T"], ket["toff"] = T, toff

    if fam in ("1SH1", "1SH2"):
        # Khong co tham so thoi gian. Xung rong DUNG mot buoc, nen phai lay buoc that
        # tho thi mat moi nhin thay - 40 buoc cho ca khung hinh.
        tong, n = 10.0, 40
        mocs = ((0.0, 0), (2.0, 1), (6.0, 0), (10.0, None))
    elif fam == "PG":
        per = T + (toff or 0.0)
        tong, n = per * 3.5, _NBUOC
        mocs = ((0.0, 0), (per * 0.5, 1), (per * 3.2, 0), (tong, None))
    else:
        tong, n = T * 6.2, _NBUOC
        mocs = tuple((m * T, x) for m, x in _KICH)

    ts, xs, ys = _chay(fam, T, toff, tunit, mocs, tong, n)
    if not any(ys):
        # Ve mot duong ra phang li khong noi len duoc gi ma con de bi hieu la khoi hong.
        ket["why"] = (tr("The output of this block never changes with the sample input, so "
                      "there is no waveform worth drawing."))
        return ket
    if fam in ("1SH1", "1SH2"):
        # Hai ho nay khong co tham so thoi gian nao - de nguyen T mac dinh thi cua so
        # Help se in ra mot con so khong he ton tai trong khoi.
        ket["T"] = None
    ket.update(ok=True, t=ts, x=xs, y=ys,
               marks=_danh_dau(fam, ts, xs, ys, T, toff, tunit),
               note=tr(_GHI.get(fam, "")))
    return ket
