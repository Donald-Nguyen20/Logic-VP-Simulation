# -*- coding: utf-8 -*-
"""Chon KY HIEU cua hang cho tung ma lenh THEO HO KY HIEU MA CHINH DB DO DANG DUNG.

Bo ky hieu TOSMAP co nhieu THE HE cung ve mot phep tinh: hau to "_T" la doi cu (macro
00xx), "_TS" la doi giua (1xxx/2xxx, gom ca ho "(H)" quet nhanh cua HCNT), "_I" la doi
dang dung (4xxx/5xxx). Dem tren 21 db that: 174.045 khoi ho "_I", 2.231 ho "_TS",
798 ho "_T".

Con so tong khong du de chon: cong tac chuyen mach trong "01 UCS.db" la F_TRA2_I
(127 lan) con trong "21 EHC MC.db" la F_TRA1_I (1.442 lan), va ca ho ASW/DSW/XFR chi
ton tai o "21 EHC MC.db" - 20 db con lai khong co lay mot khoi nao. Ve o ASW trong cua
so Help cua mot khoi thuoc UCS la bat nguoi doc hoc mot hinh ho chua he gap.

Cach chon: moi ma lenh giu mot DANH SACH UNG VIEN xep san theo thu tu uu tien; khi mo
Help thi dem xem ung vien nao thuc su co mat trong db dang mo va dua ung vien duoc dung
NHIEU NHAT len dau. Db khong co ung vien nao (hoac khong doc duoc) thi giu nguyen thu
tu san - van la ky hieu doi "_I" pho bien nhat.
"""
from __future__ import annotations

import os
import sqlite3

# Ma lenh TODEN (hoac op rieng cua ban ve) -> cac ky hieu cua hang ve duoc no.
#
# Moi ung vien la (ten ky hieu, thu tu chan). "Thu tu chan" can khi ky hieu xep chan
# theo NGHIA con than lenh xep theo thu tu toan hang: phan tu thu i la chi so cong vao
# cua ky hieu danh cho day thu i cua nut. None = trung khop san.
#
# Thu tu chan doi chieu voi core/macro_pins.json (bang chan chinh thuc cua hang):
#   406C F_INL1_I  chan 1 = SW (Upside), chan 2 = X, chan 3 = day duoi  -> (x, run, Ti)
#   405A F_RAL4_I  chan 1 = SW, chan 2 = muc dat, chan 3/4 = doc len/xuong
#   4048 F_TRA1_I  chan 1 = cong tac, chan 2 = duong 1, chan 3 = duong 2
#   4049 F_TRA2_I  chan 1 = cong tac, chan 2 = duong 1 (day DUOI), chan 3 = duong 2
_UNG = {
    # --- so hoc: hai dau vao ---
    "F+":   (("F_SUM1_I", None), ("F_SUM2_I", None), ("F_ADD_T", None)),
    "F-":   (("F_DIF1_I", None), ("F_SUB_T", None)),
    "F*":   (("F_MUL1_I", None), ("F_MUL2_I", None), ("F_MLT_T", None)),
    "F/":   (("F_DIV1_I", None), ("DIV_T", None)),
    # --- so hoc: mot dau vao ---
    "FABS": (("F_ABS_I", None), ("F_ABS_T", None)),
    "FNEG": (("F_NEG_I", None),),
    "CFB":  (("40D1_I", None), ("CFB_TS", None)),
    "CBF":  (("40D2_I", None), ("CBF_TS", None)),
    # --- chan tren / chan duoi ---
    "FUL":  (("F_HIL2_I", None), ("F_HIL1_I", None), ("F_FUL_TS", None), ("UL_TS", None)),
    "FLL":  (("F_LOL2_I", None), ("F_LOL1_I", None), ("F_FLL_TS", None), ("LL_TS", None)),
    "AR":   (("40BC_I", None), ("AR_TS", None)),
    # --- so sanh nguong ---
    "FCP+": (("F_SHI2_I", None), ("F_SHI1_I", None), ("F_CPPH_TS", None), ("F_CPP_T", None)),
    "FCP-": (("F_SLO2_I", None), ("F_SLO1_I", None), ("F_CPMH_TS", None), ("F_CPM_T", None)),
    # --- doc / tre / tich phan ---
    "FDLM": (("F_RAL4_I", (1, 0, 2, 3)), ("F_RAL1_I", None), ("F_RAL3_I", None),
             ("F_DLM_T", None)),
    "FDT":  (("F_DTM1_I", None), ("F_DTM2_I", None), ("F_DTM3_I", None), ("DT_T", None)),
    "FITG": (("F_INL1_I", (1, 0, 2)), ("F_IH_TS", (1, 0, 2)), ("F_INL3_I", None)),
    # --- bo tre thoi gian ---
    "TON":  (("DI_I", None), ("DI2_I", None), ("TON_T", None)),
    "TONL": (("DIL_I", None), ("DIL2_I", None), ("TONL_TS", None)),
    # --- chot S/R: hai ho rieng theo uu tien, khong the thay nhau ---
    "SR:S": (("FLIP2_I", None), ("40BB_I", None), ("FFS_TS", None), ("FFSH_TS", None)),
    "SR:R": (("FLIP1_I", None), ("FLIP3_I", None)),
    # --- chuyen mach ---
    "MUX":  (("F_TRA1_I", None), ("F_TRA2_I", (0, 2, 1)),
             ("TRA1_I", None), ("TRA2_I", (0, 2, 1)),
             ("F_ASW_T", None), ("ASW_T", None), ("DSW_TS", None), ("40D5_I", None)),
}

# Ky hieu tu in san so 1 / so 2 trong than: khong can ghi them ten vai tro ben ngoai.
CO_SO_SAN = frozenset(("F_ASW_T", "ASW_T", "DSW_TS"))

_DEM = {}       # nho so lieu theo duong dan db - moi db chi quet CAD_BLOCK mot lan


def dem(db):
    """{ten ky hieu: so khoi} thuc su co trong db. Loi/khong co db -> {}."""
    if not db:
        return {}
    khoa = os.path.normcase(os.path.abspath(db))
    if khoa in _DEM:
        return _DEM[khoa]
    d = {}
    try:
        cn = sqlite3.connect("file:%s?mode=ro" % db.replace("?", "%3f"), uri=True)
        try:
            cn.text_factory = lambda b: b.decode("latin-1", "replace")
            for s, n in cn.execute("SELECT SYMBOL, COUNT(*) FROM CAD_BLOCK "
                                   "WHERE SYMBOL IS NOT NULL GROUP BY SYMBOL"):
                s = (s or "").strip().upper()
                if s:
                    d[s] = d.get(s, 0) + int(n)
        finally:
            cn.close()
    except Exception:
        # Db hong / khoa / thieu cot SYMBOL: van phai ve duoc ban ve, chi la khong biet
        # ho ky hieu nen quay ve thu tu uu tien san.
        d = {}
    _DEM[khoa] = d
    return d


def ung_vien(khoa, db=None):
    """Danh sach [(ten ky hieu, thu tu chan)] cho mot ma lenh, cai HOP VOI DB DI TRUOC.

    Xep theo (so khoi trong db giam dan, thu tu uu tien san). Nguoi goi duyet tu dau
    va lay ky hieu dau tien ma bo hinh ve duoc."""
    ds = _UNG.get(khoa or "")
    if not ds:
        return []
    d = dem(db)
    return [uv for _k, uv in
            sorted(((-d.get(uv[0], 0), i), uv) for i, uv in enumerate(ds))]
