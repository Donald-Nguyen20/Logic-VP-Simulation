# -*- coding: utf-8 -*-
"""DIEM VAO/RA HIEN TRUONG (field I/O): tra ma KKS, mo ta, he thong dau kia, kieu
tin hieu va DAI DO cho mot TEN tin hieu.

Bang logic chi noi "FURN PRS LO LO gay MFT". Ra hien truong nguoi ta con phai biet
diem do do nam o dau - ma KKS ghi tren ban ve va tren tu dau day - va dai do bao
nhieu. Nhung thu do da nam san trong DB, o cac khoi DAU CUOI I/O, nhung app chua
doc bao gio.

Bo khoi dung o day (dem tren ca 24 file DB cua du an):
    40E2 Digital Input  5620      40E3 Digital Output 1604
    40E4 Analog Input   3124      40E5 Analog Output   220     -> 10568 khoi
100% so khoi nay co tham so 3 la ma KKS (10567/10568 dung dang KKS chuan). Bo cuc
tham so dong nhat, khong mot khoi nao lech:
    p2 = tag I/O (IOAI-1)         p3 = ma KKS (10CBP10EA001XQ00)
    p4 = mo ta   (GEN FREQ 1)     p5 = he thong dau kia (GCP, BPS, LOCAL, FIELD)
    p6 = kieu tin hieu (4-20mA)   p7 = dai do (45-55Hz)   -- chi khoi analog
CO Y KHONG lay 40E6/40E7: chung la giao dien bus thiet bi, tham so 3 la 'BIF-1'
chu khong phai KKS - gop vao chi de ra 412 dong rac.

Ten tin hieu cua khoi I/O nam trong CAD_SIGNAL, tra theo SYSTEMLINE (dia chi phan
cung, vd 'AI1004'), KHONG nam trong CAD_ID nhu cac khoi khac - join qua CAD_ID
khong ra gi ca.

Chi doc DB, khong sua gi.
"""
from __future__ import annotations
import os
import sqlite3
from . import dbreader as D

# macrocode -> loai diem. Chan 1 la gia tri, chan 2 (neu co) la bit chat luong.
IO_CODES = {"40E2": "DI", "40E4": "AI", "40E3": "DO", "40E5": "AO"}
VAO = ("DI", "AI")                      # diem VAO: nguyen nhan tu hien truong di len
_MA = ", ".join("'%s'" % c for c in IO_CODES)

_SQL_PIN = """SELECT b.MACROCODE, b.BLOCK_ID, b.ID, pn.SIGNALID, s.LINENAME, s.EUVUNIT
FROM CAD_BLOCK b
JOIN CAD_BLOCK_PIN pn ON pn.BLOCK_ID = b.BLOCK_ID AND pn.PINNO = 1
JOIN CAD_SIGNAL s ON s.SYSTEMLINE = pn.SIGNALID
WHERE b.MACROCODE IN (%s)""" % _MA

_SQL_PARAM = """SELECT pm.BLOCK_ID, pm.PARAMNO, pm.PARAMVALUE
FROM CAD_BLOCK_PARAM pm JOIN CAD_BLOCK b ON b.BLOCK_ID = pm.BLOCK_ID
WHERE b.MACROCODE IN (%s) AND pm.PARAMNO BETWEEN 2 AND 7""" % _MA

_TRONG = ("", "-", "--", "0")            # o tham so bo trong duoc dien bang cac ky tu nay
_CACHE = {}                              # path -> (mtime, {TEN_UPPER: [diem, ...]})


def _gia_tri(pm, no):
    v = D._clean(pm.get(str(no)))
    return "" if v.lower() in _TRONG else v


def _quet(path):
    """Doc het khoi dau cuoi I/O cua 1 file DB -> {TEN_VIET_HOA: [diem, ...]}.

    Mot ten co the ung voi NHIEU diem that (do tren 24 DB: 10149 ten, 252 ten tro
    toi >1 diem va ca 252 deu mang KKS KHAC nhau - vd 1 lenh duoc dua ra 3 diem ra
    khac nhau). Nen giu ca list chu khong chon bua 1 cai."""
    pm_all = {}
    con = D.connect(path)
    for bid, no, val in con.execute(_SQL_PARAM):
        pm_all.setdefault(bid, {})[str(no).strip()] = val
    out = {}
    for code, bid, sheet, addr, name, unit in con.execute(_SQL_PIN):
        ten = D._clean(name)
        if not ten:
            continue
        pm = pm_all.get(bid, {})
        loai = IO_CODES.get(D._clean(code).upper(), "")
        out.setdefault(ten.upper(), []).append({
            "name": ten, "kind": loai, "kks": _gia_tri(pm, 3), "tag": _gia_tri(pm, 2),
            "desc": _gia_tri(pm, 4), "partner": _gia_tri(pm, 5),
            "sigtype": _gia_tri(pm, 6), "range": _gia_tri(pm, 7),
            "unit": D._clean(unit), "addr": D._clean(addr), "db": path,
            "sheet": sheet, "bid": bid})
    return out


def points(path):
    """{TEN: [diem,...]} cua 1 DB, co cache theo thoi diem sua file."""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return {}
    got = _CACHE.get(path)
    if got and got[0] == mt:
        return got[1]
    try:
        idx = _quet(path)
    except sqlite3.Error:
        # co file DB rong hoan toan trong du an ('03 BPS_A.db', 0 bang) - khong phai
        # loi doc ma la file chua co noi dung; cac loi khac van nem len tren.
        idx = {}
    _CACHE[path] = (mt, idx)
    return idx


def _khoa(label):
    """Cac ten co the tra ra tu 1 NHAN cua ma tran nhan qua.

    Nhan trong ma tran khong phai luc nao cung la ten tin hieu tran: co the co
    'NOT ' dang truoc, co phan '  [dieu kien]' cua khoi so sanh gan sau, hoac hau
    to '(BMS CTLR A)' chi CPU nhin thay no."""
    s = (label or "").strip()
    if s.upper().startswith("NOT "):
        s = s[4:].strip()
    s = s.split("  [")[0].strip()
    ds = [s]
    import re
    ngan = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
    if ngan and ngan != s:
        ds.append(ngan)
    return [d.upper() for d in ds if d]


def find(label, db_paths, uu_tien_db=None):
    """Tim diem I/O hien truong cho 1 nhan. Tra list diem, diem VAO xep truoc.

    uu_tien_db: doc DB nay truoc (thuong la DB chua chinh nguyen nhan do) - ten
    trung nhau giua cac CPU thi lay dung diem cua CPU dang xet."""
    ds = list(db_paths or [])
    if uu_tien_db and uu_tien_db in ds:
        ds.remove(uu_tien_db)
        ds.insert(0, uu_tien_db)
    elif uu_tien_db:
        ds.insert(0, uu_tien_db)
    khoa = _khoa(label)
    for p in ds:
        idx = points(p)
        for k in khoa:
            got = idx.get(k)
            if got:
                return sorted(got, key=lambda d: 0 if d["kind"] in VAO else 1)
    return []


def ma_kks(pts, toi_da=3):
    """Ma KKS de dien vao 1 o bang. Nhieu diem thi ghi het (toi da 3) + so con lai."""
    ma = [p["kks"] for p in (pts or []) if p.get("kks")]
    if not ma:
        return ""
    if len(ma) <= toi_da:
        return " / ".join(ma)
    return "%s / +%d" % (" / ".join(ma[:toi_da]), len(ma) - toi_da)


def mo_ta(pts):
    """Mot dong gon cho o bang / cot cay: 'AI · 45-55Hz · 4-20mA · GCP'."""
    if not pts:
        return ""
    p = pts[0]
    phan = [p.get("kind") or "", p.get("range") or "", p.get("sigtype") or "",
            p.get("partner") or ""]
    return " · ".join(x for x in phan if x)


def chu_thich(pts):
    """Khoi chu thich day du (tooltip trong app / comment trong file Excel)."""
    if not pts:
        return ""
    dong = ["Diem vao/ra hien truong:"]
    for p in pts[:4]:
        dong.append("  KKS      : %s" % (p.get("kks") or "(khong ghi)"))
        dong.append("  Loai     : %s%s" % (p.get("kind") or "?",
                    ("  " + p["sigtype"]) if p.get("sigtype") else ""))
        if p.get("range"):
            dong.append("  Dai do   : %s" % p["range"])
        if p.get("desc"):
            dong.append("  Mo ta    : %s" % p["desc"])
        if p.get("partner"):
            dong.append("  Dau kia  : %s" % p["partner"])
        dong.append("  Tag I/O  : %s   dia chi %s" % (p.get("tag") or "-",
                                                      p.get("addr") or "-"))
        dong.append("")
    if len(pts) > 4:
        dong.append("  ... va %d diem nua cung ten" % (len(pts) - 4))
    return "\n".join(dong).rstrip()
