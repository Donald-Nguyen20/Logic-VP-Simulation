# -*- coding: utf-8 -*-
"""Chia LAN DOC cho day trong hanh lang giua hai cot khoi.

Truoc day moi day di kieu Z voi doan doc dat dung giua nguon va dich (xm = trung diem
cua a.x va b.x). Hai day co CUNG cap (x nguon, x dich) thi xm bang nhau nen hai doan
doc nam de khit len nhau, doc ra thanh mot net. Do tren ca 62 ma MODE_FBD: 1.869 doan
doc thi co 1.934 CAP de len nhau qua 4px, va 427 doan doc cat thang qua than mot khoi
khac (day nhay hai cot dat doan doc vao dung giua, tuc trong long cot o giua).

Cach chua: doan doc cua mot day khong dat o trung diem nua ma dat trong hanh lang NGAY
BEN TRAI cot dich, o mot "lan" rieng. Hai loi:
  - hanh lang la khoang trong giua hai cot nen doan doc khong con xuyen qua than khoi,
  - hai day co khoang y giao nhau thi bi day sang hai lan khac nhau.

Day di ra tu CUNG mot nguon vao cung mot cot thi dung CHUNG mot lan: do la mot than day
re nhanh that su, ban ve cua hang cung ve nhu vay va cham mot cham tron o cho re.
"""
from __future__ import annotations

LE = 8.0            # lan trong cung cach mep trai cot dich bao nhieu px
BUOC = 7.0          # khoang cach giua hai lan ke nhau
TOI_DA = 18         # nhieu hon thi dung lai lan cu: noi ban ve them nua khong con dang


def xep(yeucau):
    """yeucau: list (cot, nguon, y0, y1) -> ({(cot, nguon): so lan}, {cot: tong so lan}).

    Gop theo (cot, nguon) truoc, roi to mau do thi khoang: duyet theo y0 tang dan, moi
    khoang lay lan RONG co so nho nhat. Voi do thi khoang cach tham lam nay cho ra dung
    so lan it nhat co the, khong can thu tat ca.
    """
    khoang = {}
    for cot, ng, y0, y1 in yeucau:
        k = (cot, ng)
        c = khoang.get(k)
        khoang[k] = (min(c[0], y0), max(c[1], y1)) if c else (float(y0), float(y1))

    theocot = {}
    for (cot, ng), (y0, y1) in khoang.items():
        theocot.setdefault(cot, []).append((y0, y1, ng))

    lan, dem = {}, {}
    for cot, ds in theocot.items():
        ds.sort(key=lambda t: (t[0], t[1]))
        cuoi = []                       # cuoi[j] = y duoi cung dang bi lan j chiem
        for y0, y1, ng in ds:
            j = None
            for t, c in enumerate(cuoi):
                if c <= y0 + 0.5:       # lan nay da het viec truoc khi khoang moi bat dau
                    j = t
                    break
            if j is None:
                if len(cuoi) < TOI_DA:
                    j = len(cuoi)
                    cuoi.append(y1)
                else:
                    # Het cho: nhet vao lan dang ranh nhat. Van co the de len nhau mot
                    # doan, nhung it hon nhieu so voi don het ve mot cho nhu truoc.
                    j = min(range(len(cuoi)), key=lambda t: cuoi[t])
                    cuoi[j] = max(cuoi[j], y1)
            else:
                cuoi[j] = y1
            lan[(cot, ng)] = j
        dem[cot] = len(cuoi)
    return lan, dem


def be_rong(so_lan):
    """Be ngang toi thieu hanh lang phai co de chua du so_lan lan doc."""
    if so_lan <= 1:
        return 0.0
    return LE + (so_lan - 1) * BUOC + 8.0
