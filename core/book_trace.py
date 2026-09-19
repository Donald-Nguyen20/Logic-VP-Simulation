# -*- coding: utf-8 -*-
"""Do duong day tren ban ve so tay: bam mot chan -> sang ca duong di qua cac cong.

Ban ve tach tu PDF (manual_drawing.py) chi la net thang, khong co danh sach day noi.
O day dung lai day noi tu hinh hoc:
  - Hai net noi nhau khi MUT cua net nay nam tren net kia (goc gap, re nhanh chu T,
    cham noi). Hai net chi cat ngang qua nhau thi KHONG noi - dung quy uoc ban ve.
  - Mui ten (tam giac to xanh) chi huong tin hieu. Tai dau mui, day di toi bi CAT khoi
    moi thu khac: thanh vao cua cong cham moi chan vao, khong cat thi bam mot chan
    sang luon cac chan vao kia.
  - Thanh vao + hop cong + day ra van lien nhau, nen "nhom net" nam truoc dau mui chinh
    la dau ra cua cong: di xuoi = nhay qua mui ten sang nhom phia truoc; di nguoc = tu
    nhom phia truoc lui ve day di toi.
  - Vong tron dao (NOT) va e-lip chan la net kin: day cham vao la noi, nen di xuyen qua.
Cham noi day, tam giac mui ten va khung vien lon khong tinh la net: khung vien ma tinh
thi moi day cham khung se noi het voi nhau.
"""
from __future__ import annotations

import math
import re

_CHAM = 0.08        # mut cach net khac duoi muc nay coi la cham nhau (pt)
_DAU_TOI = 0.3      # tam cham noi / e-lip chan: dung sai vi tri
_DAU_VAO = 0.5      # mut day di toi cach dau mui toi da: hang ve le vuot / hut ~0.4pt
_XUYEN = 0.25       # dau mui nam tren day di toi (day chay lo qua dau mui)
_CHEO = 0.3         # net lech ca ngang lan doc qua muc nay la net cheo
_THANG = 0.05       # net lech duoi muc nay la net ngang / doc
_MUI_XA = 1.0       # dau mui cach thanh vao toi da: cong 4 chan hang ve le ~0.7pt
_SAU = -0.15        # diem lui sau dau mui qua muc nay (theo huong mui) la phia day toi
_CHAM_NOI = 2.5     # hinh kin nho hon (pt) la cham noi day / vien mui ten
_VIEN = 0.5         # hinh kin rong hon ti le nay cua khung ban ve la khung vien
_CHU_XA = 4.0       # chu dat cach dau mui / mut day toi da (pt)
_CHU_LECH = 1.5     # lech doc toi da giua day va giua dong chu
_NHAN_NOI = re.compile(r"\(\w{1,2}\)")     # nhan noi trong trang: (A), (B)...
_NHAN_TRANG = re.compile(r"([A-Z]{2}\d+-\d+):\s*(\S.*)")    # noi sang trang: "AA224-2: X"
_O = 5.0            # co o luoi tra cuu nhanh (pt)
_XUOI = ("vao", "ops", "hop_sau")      # o neo la nguon tin hieu -> di xuoi


# ---------------------------------------------------------------- dung ban do
def ban_do(ve):
    """Ban do day noi cua mot ban ve. -> {"doan": [(x0,y0,x1,y1)], "nhom": [so nhom cua
    tung doan], "mui": [{"dau": (x,y), "vao": {nhom day toi}, "toi": {nhom phia truoc},
    "nhan": chu ngay truoc dau mui (ten tin hieu / nhan noi) hoac None}]}"""
    t = _tach(ve)
    t = dict(t, doan=_cat_xuyen_mui(t["doan"], t["hinh"], t["mui"]))
    doan = t["doan"]
    luoi = _luoi(doan)
    t = dict(t, mui=t["mui"] + _mui_goc_hop(doan, t["hinh"], luoi))
    ds_mui = [_mot_mui(doan, luoi, dau, huong) for dau, huong in t["mui"]]
    nhom = _gom_nhom(t, luoi, ds_mui)
    nhan = _nhan_noi(ve["chu"], doan, luoi,
                     [(k, dh) for k, (dh, m) in enumerate(zip(t["mui"], ds_mui)) if not m["toi"]])
    ra = []
    for k, m in enumerate(ds_mui):
        chu, nguon = nhan.get(k, (None, ()))
        ra.append({"dau": m["dau"], "vao": {nhom[i] for i in m["vao"]},
                   "toi": {nhom[i] for i in m["toi"]} | {nhom[i] for i in nguon},
                   "nhan": chu})
    return {"doan": doan, "nhom": nhom, "mui": ra}


def _tach(ve):
    """-> {"doan", "hinh": so hinh kin cua tung doan (-1 = net ho), "mui": [((x,y) dau
    mui, (dx,dy) huong)], "cham": [tam cham noi]}."""
    w, h = ve["khung"]
    ra = {"doan": [], "hinh": [], "mui": [], "cham": []}
    for n in ve["net"]:
        for d in n["d"]:
            p = list(zip(d[1::2], d[2::2]))
            if n.get("f") and not n.get("s"):
                m = _dau_mui(p)
                if m is not None:
                    ra["mui"].append(m)
            elif n.get("s"):
                _them_net(ra, d[0], p, w, h)
    return ra


def _them_net(ra, kin, p, w, h):
    """Mot duong cua net ve -> doan (kem so hinh kin), hoac tam cham noi, hoac bo."""
    loai = _loai_kin(p, w, h) if kin else "net"
    if loai == "cham":
        tam = _tam(p)
        if all(math.dist(tam, c) > _DAU_TOI for c in ra["cham"]):
            ra["cham"].append(tam)
        return
    if loai == "bo":
        return
    so = -1
    if kin:
        so = max(ra["hinh"], default=-1) + 1
        if len(p) > 2:
            p = p + [p[0]]
    for a, b in zip(p, p[1:]):
        if a != b:
            ra["doan"].append((a[0], a[1], b[0], b[1]))
            ra["hinh"].append(so)


def _tam(p):
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _loai_kin(p, w, h):
    """Hinh kin: "cham" noi day, "bo" (vien mui ten, khung vien ban ve) hay "net"."""
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    rong, cao = max(xs) - min(xs), max(ys) - min(ys)
    if len(p) <= 5 and len(_dinh(p)) == 3 and max(rong, cao) < 5:
        return "bo"
    if max(rong, cao) < _CHAM_NOI:
        return "cham"
    return "bo" if rong > w * _VIEN or cao > h * _VIEN else "net"


def _dinh(p):
    """Cac dinh khac nhau cua duong gap (bo diem lap, ke ca diem khep kin)."""
    ra = []
    for q in p:
        if not any(abs(q[0] - r[0]) < 0.01 and abs(q[1] - r[1]) < 0.01 for r in ra):
            ra.append(q)
    return ra


def _dau_mui(p):
    """Tam giac -> (dau mui, huong): dau mui la dinh xa trung diem canh doi dien nhat."""
    dinh = _dinh(p)
    if len(dinh) != 3:
        return None
    tot = None
    for i in range(3):
        b, c = [dinh[j] for j in range(3) if j != i]
        m = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        dai = math.dist(dinh[i], m)
        if tot is None or dai > tot[0]:
            tot = (dai, dinh[i], m)
    dai, a, m = tot
    if dai <= 0:
        return None
    return a, ((a[0] - m[0]) / dai, (a[1] - m[1]) / dai)


def _luoi(doan):
    """{(cot, hang): [chi so doan]} - moi doan ghi vao moi o no di qua (theo khung bao)."""
    o = {}
    for i, (x0, y0, x1, y1) in enumerate(doan):
        for cx in range(int(min(x0, x1) // _O), int(max(x0, x1) // _O) + 1):
            for cy in range(int(min(y0, y1) // _O), int(max(y0, y1) // _O) + 1):
                o.setdefault((cx, cy), []).append(i)
    return o


def _gan(doan, luoi, x, y, tam):
    """Chi so cac doan cach diem (x, y) khong qua tam."""
    thay = set()
    for cx in range(int((x - tam) // _O), int((x + tam) // _O) + 1):
        for cy in range(int((y - tam) // _O), int((y + tam) // _O) + 1):
            thay.update(luoi.get((cx, cy), ()))
    return [i for i in thay if _kc(x, y, doan[i])[0] <= tam]


def _kc(x, y, s):
    """(khoang cach, x, y diem gan nhat tren doan s) tu diem (x, y)."""
    x0, y0, x1, y1 = s
    dx, dy = x1 - x0, y1 - y0
    dai2 = dx * dx + dy * dy
    t = 0.0 if dai2 == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / dai2))
    cx, cy = x0 + t * dx, y0 + t * dy
    return math.hypot(x - cx, y - cy), cx, cy


def _cat_xuyen_mui(doan, hinh, mui):
    """Day di toi ma chay LO qua dau mui (hang ve de len canh hop cong) -> cat tai dau
    mui. Khong cat thi day toi dinh vao hop cong o goc xa, di nguoc duoc vao chan khac."""
    ra = list(doan)
    luoi = _luoi(doan)
    for (tx, ty), (dx, dy) in mui:
        for i in _gan(doan, luoi, tx, ty, _XUYEN):
            x0, y0, x1, y1 = ra[i]
            if hinh[i] >= 0:
                continue
            dai = math.hypot(x1 - x0, y1 - y0)
            if dai == 0 or abs((x1 - x0) * dy - (y1 - y0) * dx) / dai > 0.1:
                continue
            t0 = (x0 - tx) * dx + (y0 - ty) * dy
            t1 = (x1 - tx) * dx + (y1 - ty) * dy
            if t0 < _SAU and t1 > 0.05:
                ra[i] = (x0, y0, tx, ty)
            elif t1 < _SAU and t0 > 0.05:
                ra[i] = (tx, ty, x1, y1)
    return ra


def _mui_goc_hop(doan, hinh, luoi):
    """Mui ten ngam: hop chuyen mach T nhan dau vao thu hai bang mot net CHEO cham dung
    goc hop, khong ve mui ten. Goc hop = mot canh ngang + mot canh doc cung dung o do,
    dau kia cua net cheo nam ngoai hop. -> [(goc, huong tu dau kia vao goc)]."""
    ra = []
    for i, (x0, y0, x1, y1) in enumerate(doan):
        if hinh[i] >= 0 or abs(x1 - x0) < _CHEO or abs(y1 - y0) < _CHEO:
            continue
        for (mx, my), (ox, oy) in (((x1, y1), (x0, y0)), ((x0, y0), (x1, y1))):
            canh = [doan[j] for j in _gan(doan, luoi, mx, my, _CHAM) if j != i]
            ngang = [c for c in canh if abs(c[3] - c[1]) < _THANG]
            doc = [c for c in canh if abs(c[2] - c[0]) < _THANG]
            if len(canh) != 2 or len(ngang) != 1 or len(doc) != 1:
                continue
            hx = (ngang[0][0] + ngang[0][2]) / 2 - mx
            vy = (doc[0][1] + doc[0][3]) / 2 - my
            if (ox - mx) * hx < 0 or (oy - my) * vy < 0:
                dai = math.hypot(mx - ox, my - oy)
                ra.append(((mx, my), ((mx - ox) / dai, (my - oy) / dai)))
    return ra


# ---------------------------------------------------------------- mui ten
def _mot_mui(doan, luoi, dau, huong):
    """-> {"dau", "vao": {doan day toi}, "toi": {doan phia truoc gan dau mui nhat}}."""
    tx, ty = dau
    dx, dy = huong
    vao, truoc = set(), []
    for i in _gan(doan, luoi, tx, ty, _MUI_XA):
        x0, y0, x1, y1 = doan[i]
        if _la_day_toi((x0, y0), (x1, y1), dau, huong) or \
                _la_day_toi((x1, y1), (x0, y0), dau, huong):
            vao.add(i)
            continue
        kc, cx, cy = _kc(tx, ty, doan[i])
        if (cx - tx) * dx + (cy - ty) * dy > _SAU:
            truoc.append((kc, i))
    gan_nhat = min((kc for kc, _ in truoc), default=0.0)
    return {"dau": dau, "vao": vao,
            "toi": {i for kc, i in truoc if kc <= gan_nhat + 0.15}}


def _la_day_toi(mut, dau_kia, dau, huong):
    """Doan co mot mut o dau mui va dau kia nam phia sau mui ten."""
    if math.dist(mut, dau) > _DAU_VAO:
        return False
    return (dau_kia[0] - dau[0]) * huong[0] + (dau_kia[1] - dau[1]) * huong[1] < _SAU


# ---------------------------------------------------------------- gom nhom net
def _gom_nhom(t, luoi, ds_mui):
    """Nhom net lien nhau (union-find). Tai dau mui, day di toi khong noi voi gi; hai
    hinh kin khac nhau cham vien (e-lip chan xep sat nhau) khong noi; o cham noi thi
    moi day di qua deu noi, ke ca hai day cung xuyen qua (nga tu co cham)."""
    doan, hinh = t["doan"], t["hinh"]
    cha = list(range(len(doan)))

    def goc(i):
        while cha[i] != i:
            cha[i] = cha[cha[i]]
            i = cha[i]
        return i

    cat = _day_bi_cat(ds_mui)
    for i, s in enumerate(doan):
        for mx, my in ((s[0], s[1]), (s[2], s[3])):
            chan = cat.get((round(mx / _DAU_VAO), round(my / _DAU_VAO)), ())
            chan = {j for dau, ds in chan if math.dist(dau, (mx, my)) <= _DAU_VAO for j in ds}
            if i in chan:
                continue
            for j in _gan(doan, luoi, mx, my, _CHAM):
                if j not in chan and (hinh[i] < 0 or hinh[j] < 0 or hinh[i] == hinh[j]):
                    cha[goc(j)] = goc(i)
    for cx, cy in t["cham"]:
        qua = [j for j in _gan(doan, luoi, cx, cy, _DAU_TOI) if hinh[j] < 0]
        for j in qua[1:]:
            cha[goc(j)] = goc(qua[0])
    return [goc(i) for i in range(len(doan))]


def _day_bi_cat(ds_mui):
    """{o luoi nho quanh dau mui: [(dau mui, {doan day toi})]} de tra nhanh."""
    ra = {}
    for m in ds_mui:
        kx, ky = round(m["dau"][0] / _DAU_VAO), round(m["dau"][1] / _DAU_VAO)
        for cx in (kx - 1, kx, kx + 1):
            for cy in (ky - 1, ky, ky + 1):
                ra.setdefault((cx, cy), []).append((m["dau"], m["vao"]))
    return ra


# ---------------------------------------------------------------- nhan noi
def _nhan_noi(chu, doan, luoi, mui_cut):
    """{chi so mui ten: (chu ngay truoc dau mui, [doan xuat phat o nhan cung ten])}.

    mui_cut = [(chi so, (dau, huong))] cac mui ten phia truoc khong co net. Mui ten
    chi vao chu la diem cuoi tren trang: ten tin hieu ra ngoai, hoac nhan noi - cung
    nhan dat o cho khac, day bat dau ngay sau chu la doan tiep theo cua day. Nhan noi:
    "(A)" trong trang, hoac "AA224-2: X" (gui sang trang AA224-2) ghep voi "AA224-1: X"
    (nhan tu trang AA224-1) - cung ten, khac trang."""
    ngang = [c for c in chu if not c[5] and c[4].strip()]
    nguon = {}
    for c in ngang:
        khoa = _khoa_nhan(c[4].strip())
        i = _day_sau_chu(doan, luoi, c) if khoa else None
        if i is not None:
            nguon.setdefault(khoa[0], []).append((khoa[1], i))
    ra = {}
    for k, ((tx, ty), (dx, _)) in mui_cut:
        for c in ngang:
            mep = c[0] - tx if dx > 0 else tx - c[0] - c[6]
            if 0 <= mep <= _CHU_XA and abs(_giua(c) - ty) <= _CHU_LECH:
                ten = c[4].strip()
                ra[k] = (ten, _nguon_ghep(nguon, _khoa_nhan(ten)))
                break
    return ra


def _khoa_nhan(ten):
    """(khoa ghep, trang) cua nhan noi, None neu la chu thuong.
    "(A)" -> ("(A)", None); "AA224-2: X" -> ("X", "AA224-2")."""
    if _NHAN_NOI.fullmatch(ten):
        return ten, None
    m = _NHAN_TRANG.fullmatch(ten)
    return (m.group(2).strip(), m.group(1)) if m else None


def _nguon_ghep(nguon, khoa):
    """Doan xuat phat o cac nhan ghep duoc voi nhan dich khoa: "(A)" voi "(A)"; nhan
    trang voi nhan trang cung ten nhung ghi trang khac."""
    if khoa is None:
        return []
    ten, trang = khoa
    return [i for tr, i in nguon.get(ten, [])
            if (tr is None) == (trang is None) and (tr is None or tr != trang)]


def _giua(c):
    """Toa do y giua dong chu (c[1] la duong chan chu, c[2] la co chu)."""
    return c[1] - c[2] * 0.35


def _day_sau_chu(doan, luoi, c):
    """Doan co mut ngay ben phai chu c (nhan noi phia nguon), gan giua dong chu nhat."""
    x, y = c[0] + c[6], _giua(c)
    tot = None
    for i in _gan(doan, luoi, x + _CHU_XA / 2, y, _CHU_XA):
        for mx, my in ((doan[i][0], doan[i][1]), (doan[i][2], doan[i][3])):
            lech = abs(my - y)
            if -0.5 <= mx - x <= _CHU_XA and lech <= _CHU_LECH and (tot is None or lech < tot[0]):
                tot = (lech, i)
    return None if tot is None else tot[1]


# ---------------------------------------------------------------- do duong
def duong_sang(bd, o):
    """Cac doan can to sang khi bam o neo o. Chan vao / nut OPS / o cai dat: di xuoi
    qua cac cong. Chan ra / o hien thi: di nguoc ve moi thu quyet dinh no."""
    dau = _nhom_duoi(bd, o["r"])
    nhom = _lan(bd, dau, o.get("kieu") in _XUOI)
    return [s for s, n in zip(bd["doan"], bd["nhom"]) if n in nhom]


def _nhom_duoi(bd, r):
    """Nhom cua vien o neo (e-lip chan, o hien thi...): net nam tron trong o va trai du
    nua be rong lan be cao cua o. Chi nam trong ma nho (mep e-lip chan ben canh cham vao
    dung sai) thi khong tinh."""
    x0, y0, x1, y1 = r[0] - _DAU_TOI, r[1] - _DAU_TOI, r[2] + _DAU_TOI, r[3] + _DAU_TOI
    khung = {}
    for s, n in zip(bd["doan"], bd["nhom"]):
        if x0 <= min(s[0], s[2]) and max(s[0], s[2]) <= x1                 and y0 <= min(s[1], s[3]) and max(s[1], s[3]) <= y1:
            k = khung.get(n, (s[0], s[1], s[0], s[1]))
            khung[n] = (min(k[0], s[0], s[2]), min(k[1], s[1], s[3]),
                        max(k[2], s[0], s[2]), max(k[3], s[1], s[3]))
    return {n for n, k in khung.items()
            if k[2] - k[0] >= (r[2] - r[0]) / 2 and k[3] - k[1] >= (r[3] - r[1]) / 2}


def _lan(bd, dau, xuoi):
    """Loang qua mui ten tu cac nhom 'dau'. Xuoi: day toi -> phia truoc; nguoc lai."""
    tu, sang = ("vao", "toi") if xuoi else ("toi", "vao")
    da = set(dau)
    hang = list(dau)
    while hang:
        n = hang.pop()
        for m in bd["mui"]:
            if n in m[tu]:
                moi = m[sang] - da
                da |= moi
                hang.extend(moi)
    return da
