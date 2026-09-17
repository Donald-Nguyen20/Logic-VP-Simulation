# -*- coding: utf-8 -*-
"""To mau TEN TIN HIEU THAT trong cau tra loi cua Explain.

Cau tra loi la van xuoi nen ten tin hieu chim giua cau, doc xong khong biet dua vao
dau ma tra lai ban ve. O day to mau chung.

Chi to ten TRA DUOC trong CSDL du an (bang name2 cua signal_graph), khong to theo hinh
dang chu: neu doan theo kieu "cu viet hoa la ten" thi DCS, CPU A, MFT trong mot cau
giai thich cung bi to, mau mat nghia ngay.
"""
import re

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument

MAU = "#0B5F58"          # xanh mong ket: khong dung mau nao cua tieu de (#0F172A/#1D4ED8)

# mot doan chu viet HOA lien mach - ung vien cho ten tin hieu
_DOAN = re.compile(r"[A-Z0-9][-A-Z0-9 &/.'#+()]*")
_CO_CHU = re.compile(r"[A-Z]")
_RIA = " \t.,;:!?\"'"    # ky tu o ria co the bo khi thu khop
_NHO = {}                # (db, cpu...) -> tap ten


def ten_du_an(db, cpu_paths=None):
    """Tap ten tin hieu (viet HOA) co that trong db hien tai va cac CPU khac."""
    from core import signal_graph as SG
    ds = tuple([db] + [p for p in (cpu_paths or []) if p and p != db])
    if ds in _NHO:
        return _NHO[ds]
    ra = set()
    for p in ds:
        try:
            ra |= set(SG._dbc(p)["name2"].keys())
        except Exception:
            pass
    _NHO[ds] = ra
    return ra


def ten_trong_chu(text, ten):
    """Cac ten tin hieu that xuat hien trong `text`, giu nguyen cach viet o text."""
    ra = set()
    for m in _DOAN.finditer(text):
        for phan in m.group(0).split(","):
            _khop(phan, ten, ra)
    return ra


def _khop(phan, ten, ra):
    """Khop tham nhat trong mot doan chu hoa: lay ten dai nhat, roi tim tiep phia sau.

    Can tham vi 'CWP 1 RUN' va 'CWP 1 RUN PERM' co the cung ton tai; to nham ten ngan
    thi nua ten con lai mat mau, nhin ra thanh hai thu khac nhau."""
    tu = phan.split()
    i = 0
    while i < len(tu):
        for cuoi in range(len(tu), i, -1):
            s = _co(" ".join(tu[i:cuoi]), ten)
            if s:
                ra.add(s)
                i = cuoi
                break
        else:
            i += 1


def _co(s, ten):
    """Doan chu nay co dung la mot ten khong. Tra ve dung phan chu la ten, hoac ''."""
    for x in _bien_the(s.strip(_RIA)):
        if len(x) >= 3 and _CO_CHU.search(x) and x.upper() in ten:
            return x
    return ""


def _bien_the(s):
    """Ban than s va cac ban da go ngoac don o hai dau.

    Ten hay nam trong ngoac don cua cau - '(PULV A TRIP)' - va neu chu dung truoc cung
    viet hoa ('tren DCS (CWP 1 RUN)') thi dau '(' dinh luon vao cum. Nhung cung co ten
    mang san ngoac 'BT-102 MFT(2)', nen khong the cat ngoac vo tu: thu ban nguyen truoc."""
    ra = [s]
    if s.startswith("("):
        ra.append(s[1:].strip(_RIA))
    if s.endswith(")"):
        ra.append(s[:-1].strip(_RIA))
        if s.startswith("("):
            ra.append(s[1:-1].strip(_RIA))
    return [x for i, x in enumerate(ra) if x and x not in ra[:i]]


def to_mau(edit, db, cpu_paths=None):
    """To mau moi ten tin hieu that trong o tra loi. Tra ve so cho da to."""
    doc = edit.document()
    ten = ten_du_an(db, cpu_paths)
    if not ten:
        return 0
    cf = QTextCharFormat()
    cf.setForeground(QColor(MAU))     # chi doi mau: dat them do dam se lam nhat chu
    n = 0                             # o tieu de (tieu de dang 700, merge 600 la tut xuong)
    for s in sorted(ten_trong_chu(doc.toPlainText(), ten), key=len, reverse=True):
        cur = QTextCursor(doc)
        while True:
            cur = doc.find(s, cur, QTextDocument.FindFlag.FindCaseSensitively)
            if cur.isNull():
                break
            cur.mergeCharFormat(cf)
            n += 1
    return n
