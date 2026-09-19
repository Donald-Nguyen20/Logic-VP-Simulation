# -*- coding: utf-8 -*-
"""Ban ve GOC cua hang trong so tay, tach thanh net + chu de ve lai y nguyen.

O "So do so tay" cua cua so Help khong ve lai theo y minh nua: no ve chinh ban ve vector
cua hang (vd AA143 cua MOV2-NSH, trang P-35 so tay TAG Macro Instructions), dung tung
toa do, roi to mau gia tri len cac e-lip / o hien thi da biet.

VI SAO PHAI TACH TRUOC: ban .exe loai han fitz, QtPdf va QtSvg (xem lenh PyInstaller
trong main.py), nen luc chay chi doc duoc JSON. Buoc tach chay tren may co PyMuPDF +
file PDF, ghi ra core/book_drawings/<ma>.json; '--add-data core;core' mang file do vao
ban dong goi. Tao san truoc khi dong goi:   python -m core.manual_drawing

book_drawings/ NAM TRONG .gitignore: ban ve la tai lieu cua hang, repo lai cong khai.

Hai cai bay da gap khi tach:
  - get_drawings() tra toa do DA doi he nhung be rong net CHUA doi: net ghi 10.0 ma
    that ra ~0.53pt (CTM thu nho ~0.053). Be rong that lay tu get_svg_image().
  - Duong ngang/doc co khung bao dien tich 0, Rect.intersects() tra False -> loc bang
    so sanh toa do, khong dung intersects() (mat sach day noi neu dung).

Toa do giu nguyen don vi pt cua trang PDF, chi doi goc ve goc tren-trai cua khung ban
ve. Net, chu va o neo cung mot he nen o to mau khop tung pt voi hinh.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics

from core import manual_index as MI
from core.book_diagram import khung
from core.help_i18n import tr

PHIEN_BAN = 1
_THU_MUC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "book_drawings")
_NHO = {}

_LECH = 0.02            # hai dau mut cach nhau duoi muc nay coi la mot diem (pt)
_TIA_XA = 40.0          # tia do o bao quanh mot chu: xa hon nua la khong co o
_BUOC_CONG = 8          # so doan chia mot duong cong bezier (ban ve hien chua co)


# ---------------------------------------------------------------- nap / cache
def load(code):
    """(ban_ve, "") hoac (None, ly_do). Da gan san danh sach o neo 'neo'.

    ban_ve = {"khung":[w,h], "net":[...], "chu":[...], "neo":[...], "thieu":[...],
              "spec": noi dung core/book_layouts/<ma>.json}"""
    code = (code or "").upper()
    if code not in _NHO:
        _NHO[code] = _nap(code)
    return _NHO[code]


def _nap(code):
    spec = khung(code)
    if spec is None or "neo" not in spec:
        return None, tr("No vendor book drawing has been mapped for this macro yet.")
    ve = _doc_cache(code)
    if ve is None:
        ve, why = _tach_va_luu(code, spec)
        if ve is None:
            return None, why
    neo, thieu = tim_neo(ve, spec["neo"])
    return dict(ve, neo=neo, thieu=thieu, spec=spec), ""


def duong_cache(code):
    return os.path.join(_THU_MUC, "%s.json" % code.upper())


def _doc_cache(code):
    """Ban ve da tach, hoac None neu chua co / hong / khac phien ban (thi tach lai)."""
    p = duong_cache(code)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            ve = json.load(f)
    except (OSError, ValueError):
        return None
    return ve if isinstance(ve, dict) and ve.get("phien_ban") == PHIEN_BAN else None


def _tach_va_luu(code, spec):
    try:
        import fitz  # noqa: F401  - chi co tren may phat trien
    except ImportError:
        return None, tr("The vendor drawing has not been extracted on this machine yet. "
                        "Run 'python -m core.manual_drawing' where PyMuPDF and the vendor "
                        "manual are available.")
    tai_lieu = spec.get("tai_lieu", "tag")
    pdf = MI.pdf_path(tai_lieu)
    if not pdf:
        return None, (tr("The vendor manual '%s' was not found on this PC, so its drawing "
                         "cannot be redrawn.") % MI.DOCS.get(tai_lieu, tai_lieu))
    try:
        ve = tach(pdf, int(spec["trang"]))
    except (RuntimeError, ValueError, IndexError, KeyError, OSError) as e:
        return None, tr("Could not read the drawing from the vendor manual: %s") % e
    ghi_cache(code, ve)
    return ve, ""


def ghi_cache(code, ve):
    """Ghi ban ve da tach. Loi ghi (thu muc chi doc...) khong chan viec ve lan nay."""
    try:
        os.makedirs(_THU_MUC, exist_ok=True)
        with open(duong_cache(code), "w", encoding="utf-8") as f:
            json.dump(ve, f, ensure_ascii=False, separators=(",", ":"))
    except OSError:
        return False
    return True


# ---------------------------------------------------------------- tach tu PDF
def tach(pdf, trang):
    """Tach khung ban ve tren trang 'trang' (dem tu 0) thanh net + chu."""
    import fitz
    with fitz.open(pdf) as doc:
        pg = doc[trang]
        drawings = pg.get_drawings()
        k = tim_khung(drawings)
        if k is None:
            raise ValueError("no drawing frame on page %d" % (trang + 1))
        rong = be_rong_that(pg.get_svg_image())
        net = _lay_net(drawings, k, rong)
        chu = _lay_chu(pg.get_text("dict", clip=fitz.Rect(*k)), k)
    return {"phien_ban": PHIEN_BAN, "trang": trang,
            "khung": [round(k[2] - k[0], 2), round(k[3] - k[1], 2)],
            "net": net, "chu": chu}


def tim_khung(drawings):
    """Vung ban ve = HOP cua moi khung lon nam ngang tren trang (rong > 300, rong > cao
    > 120pt). MOV2-NSH co 1 khung (AA143); CB, D-SOV... ve 2 khung chong nhau (AA101B1 +
    AA101B2) - lay ca hai, giu nguyen khoang cach giua chung nhu tren giay.

    -> (x0, y0, x1, y1) hoac None. Khung nho hon (o ma ban ve, o hien thi) bi loai
    boi nguong kich thuoc; khung le trang ca to thi dung, khong nam ngang."""
    ds = [(r.x0, r.y0, r.x1, r.y1) for x in drawings for it in x["items"]
          if it[0] == "re" for r in (it[1],)
          if r.width > 300 and r.width > r.height > 120]
    if not ds:
        return None
    return (min(k[0] for k in ds), min(k[1] for k in ds),
            max(k[2] for k in ds), max(k[3] for k in ds))


_RE_PATH = re.compile(r"<path\b[^>]*>")
_RE_W = re.compile(r'stroke-width="([-\d.eE]+)"')
_RE_M = re.compile(r'transform="matrix\(([^)]*)\)"')


def be_rong_that(svg):
    """{be_rong_ghi: be_rong_that_pt} doc tu SVG cua trang.

    SVG ghi stroke-width chua doi kem transform cua tung net; be rong that =
    stroke-width x sqrt(|ad - bc|). Lay trung vi cho moi muc be rong ghi."""
    mau = {}
    for the in _RE_PATH.findall(svg):
        w = _RE_W.search(the)
        if not w:
            continue
        ghi = float(w.group(1))
        k = 1.0
        m = _RE_M.search(the)
        if m:
            so = [float(v) for v in re.split(r"[\s,]+", m.group(1).strip())[:4]]
            if len(so) == 4:
                k = math.sqrt(abs(so[0] * so[3] - so[1] * so[2]))
        mau.setdefault(round(ghi, 3), []).append(ghi * k)
    return {g: statistics.median(v) for g, v in mau.items()}


def _trong_khung(r, k):
    """So toa do, KHONG dung Rect.intersects: duong thang co dien tich 0."""
    return r.x1 >= k[0] - 1 and r.x0 <= k[2] + 1 and r.y1 >= k[1] - 1 and r.y0 <= k[3] + 1


def _mau(c):
    if not c:
        return None
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v * 255))) for v in c[:3])


def _lay_net(drawings, k, rong):
    """Moi net ve -> {"s": mau net|None, "f": mau to|None, "w": be rong that, "c": dau,
    "d": [[kin, x0, y0, x1, y1, ...], ...]}; toa do tinh tu goc khung."""
    ra = []
    for x in drawings:
        if not _trong_khung(x["rect"], k):
            continue
        d = _chuoi_hoa(x["items"], k[0], k[1])
        if not d:
            continue
        if x.get("closePath"):
            d[-1][0] = 1
        loai = x.get("type") or ""
        w = x.get("width") or 0.0
        ra.append({"s": _mau(x.get("color")) if "s" in loai else None,
                   "f": _mau(x.get("fill")) if "f" in loai else None,
                   "w": round(rong.get(round(w, 3), w), 3),
                   "c": (x.get("lineCap") or (0,))[0],
                   "d": d})
    return ra


def _chuoi_hoa(items, ox, oy):
    """Noi cac doan thang lien mut thanh duong gap; hinh chu nhat / tu giac thanh duong
    kin. Moi duong: [kin, x0, y0, x1, y1, ...]."""
    ds, cur = [], None
    for it in items:
        loai = it[0]
        if loai in ("l", "c"):
            diem = [it[1], it[2]] if loai == "l" else _chia_cong(*it[1:5])
            if cur is not None and _trung(cur, diem[0], ox, oy):
                diem = diem[1:]
            else:
                cur = [0]
                ds.append(cur)
            for p in diem:
                cur += [round(p.x - ox, 2), round(p.y - oy, 2)]
        elif loai in ("re", "qu"):
            q = it[1].quad if loai == "re" else it[1]
            ds.append([1] + [round(v, 2) for p in (q.ul, q.ur, q.lr, q.ll)
                             for v in (p.x - ox, p.y - oy)])
            cur = None
    for d in ds:
        if d[0] == 0 and len(d) >= 9 and abs(d[1] - d[-2]) < _LECH and abs(d[2] - d[-1]) < _LECH:
            d[0] = 1
    return ds


def _trung(cur, p, ox, oy):
    return abs(cur[-2] - (p.x - ox)) < _LECH and abs(cur[-1] - (p.y - oy)) < _LECH


def _chia_cong(a, c1, c2, b):
    """Bezier bac 3 -> _BUOC_CONG+1 diem (ban ve hien tai chua co, de phong trang khac)."""
    ra = []
    for i in range(_BUOC_CONG + 1):
        t = i / _BUOC_CONG
        u = 1 - t
        x = u ** 3 * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t ** 3 * b.x
        y = u ** 3 * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t ** 3 * b.y
        ra.append(type(a)(x, y))
    return ra


def _lay_chu(td, k):
    """Moi cum chu -> [x, y (duong chan chu), co, font, chu, goc, dai, mau].

    'dai' la be dai that tren giay theo huong chu: luc ve keo gian font thay the cho
    khop dung be dai nay, khong thi chu Arial thay MS-PGothic se tran ra ngoai o."""
    ra = []
    for b in td.get("blocks", []):
        for ln in b.get("lines", []):
            dx, dy = ln["dir"]
            goc = round(math.degrees(math.atan2(dy, dx)))
            for s in ln["spans"]:
                if not s["text"].strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                dai = (x1 - x0) if goc in (0, 180) else (y1 - y0)
                ra.append([round(s["origin"][0] - k[0], 2), round(s["origin"][1] - k[1], 2),
                           round(s["size"], 2), s["font"], s["text"], goc, round(dai, 2),
                           "#%06X" % (s.get("color") or 0)])
    return ra


# ---------------------------------------------------------------- o neo
def tim_neo(ve, spec_neo):
    """Tim o tren ban ve cho moi dong [nguon, kieu, nhan] cua file book_layouts.

    -> ([{"nguon","kieu","nhan","r":[x0,y0,x1,y1],"hinh":"e"|"r"}], [dong khong tim ra])
    Kieu: vao (e-lip ngoai cung ben trai), ra (e-lip ngoai cung ben phai), ops (nut
    trong khung "OPS Operation"), ht (o hien thi co o 'S'/'A' dung truoc), hop_sau (o
    chua chu dung ngay sau nhan, vd "Soft SW" -> o "0")."""
    chu = [_hop_chu(c) for c in ve.get("chu", [])]
    doan = _doan_thang(ve.get("net", []))
    neo, thieu = [], []
    for dong in spec_neo:
        nguon, kieu, nhan = dong[0], dong[1], dong[2]
        r = _o_cho(kieu, nhan, chu, doan)
        if r is None:
            thieu.append(list(dong))
            continue
        neo.append({"nguon": nguon, "kieu": kieu, "nhan": nhan, "r": r,
                    "hinh": "e" if kieu in ("vao", "ra") else "r"})
    return neo, thieu


def _hop_chu(c):
    """Cum chu -> (chu da cat trang, x0, y0, x1, y1) theo khung bao tren giay."""
    x, y, co, _f, t, goc, dai = c[:7]
    if goc in (0, 180):
        return (t.strip(), x, y - co * 0.86, x + dai, y + co * 0.14)
    return (t.strip(), x - co * 0.86, y - dai, x + co * 0.14, y)


def _tam(h):
    return ((h[1] + h[3]) / 2, (h[2] + h[4]) / 2)


def _o_cho(kieu, nhan, chu, doan):
    khop = [h for h in chu if h[0] == nhan]
    if not khop:
        return None
    if kieu == "vao":
        return _o_quanh(_tam(min(khop, key=lambda h: h[1])), doan)
    if kieu == "ra":
        return _o_quanh(_tam(max(khop, key=lambda h: h[1])), doan)
    if kieu == "ops":
        return _o_ops(khop, chu, doan)
    if kieu == "ht":
        return _o_hien_thi(khop, chu, doan)
    if kieu == "hop_sau":
        sau = [_ke_phai(h, chu) for h in khop]
        sau = [h for h in sau if h is not None]
        return _o_quanh(_tam(sau[0]), doan) if sau else None
    return None


def _o_ops(khop, chu, doan):
    """Nut trong khung 'OPS Operation': chu cung ten gan nhan doc cua khung nhat."""
    moc = [h for h in chu if h[0] == "OPS Operation"]
    if not moc:
        return None
    mx, my = _tam(moc[0])
    h = min(khop, key=lambda h: math.dist(_tam(h), (mx, my)))
    return _o_quanh(_tam(h), doan) if math.dist(_tam(h), (mx, my)) < _TIA_XA else None


def _o_hien_thi(khop, chu, doan):
    """O hien thi 'S| nhan' (hoac 'A| nhan'): o = o chua 'S' GOP o chua nhan."""
    for h in khop:
        tr_ = _ke_trai(h, chu)
        if tr_ is None or tr_[0] not in ("S", "A"):
            continue
        a = _o_quanh(_tam(tr_), doan)
        b = _o_quanh(_tam(h), doan)
        if a and b:
            return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
    return None


def _ke_trai(h, chu):
    """Cum chu dung ngay ben trai, cung dong chan chu, cach khong qua 15pt."""
    ung = [c for c in chu if c is not h and abs(c[4] - h[4]) < 1.0 and 0 <= h[1] - c[3] < 15]
    return max(ung, key=lambda c: c[3]) if ung else None


def _ke_phai(h, chu):
    ung = [c for c in chu if c is not h and abs(c[4] - h[4]) < 1.0 and 0 <= c[1] - h[3] < 15]
    return min(ung, key=lambda c: c[1]) if ung else None


def _doan_thang(net):
    """Tat ca doan thang cua net ve (ke ca canh dong kin) -> [(x0,y0,x1,y1)]."""
    ra = []
    for n in net:
        if not n.get("s"):
            continue
        for d in n["d"]:
            p = list(zip(d[1::2], d[2::2]))
            if d[0] and len(p) > 2:
                p.append(p[0])
            ra += [(a[0], a[1], b[0], b[1]) for a, b in zip(p, p[1:])]
    return ra


def _o_quanh(p, doan):
    """O nho nhat bao quanh diem p: ban tia 4 huong, lay net gan nhat moi huong.

    -> [x0, y0, x1, y1] hoac None neu mot huong khong cham net nao trong _TIA_XA.
    Dung cho ca e-lip (duong gap nhieu doan), o chu nhat va o ghep tu 4 doan thang."""
    x, y = p
    gan = [s for s in doan if min(s[0], s[2]) - _TIA_XA < x < max(s[0], s[2]) + _TIA_XA
           and min(s[1], s[3]) - _TIA_XA < y < max(s[1], s[3]) + _TIA_XA]
    trai = phai = tren = duoi = None
    for x0, y0, x1, y1 in gan:
        if y0 != y1 and min(y0, y1) <= y <= max(y0, y1):
            xc = x0 + (x1 - x0) * (y - y0) / (y1 - y0)
            if xc < x and (trai is None or xc > trai):
                trai = xc
            if xc > x and (phai is None or xc < phai):
                phai = xc
        if x0 != x1 and min(x0, x1) <= x <= max(x0, x1):
            yc = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            if yc < y and (tren is None or yc > tren):
                tren = yc
            if yc > y and (duoi is None or yc < duoi):
                duoi = yc
    if None in (trai, phai, tren, duoi):
        return None
    return [round(trai, 2), round(tren, 2), round(phai, 2), round(duoi, 2)]


# ---------------------------------------------------------------- dung truoc
def tao_san(codes=None):
    """Tach truoc moi ma khoi co file book_layouts. -> {ma: "" hoac ly do}."""
    if codes is None:
        neo = os.path.join(os.path.dirname(_THU_MUC), "book_layouts")
        codes = sorted(f[:-5] for f in os.listdir(neo) if f.endswith(".json"))
    ket = {}
    for c in codes:
        _NHO.pop(c.upper(), None)
        p = duong_cache(c)
        if os.path.isfile(p):
            os.remove(p)
        ve, why = load(c)
        ket[c] = why if ve is None else ("thieu neo: %s" % ve["thieu"] if ve["thieu"] else "")
    return ket


if __name__ == "__main__":
    for ma, loi in tao_san().items():
        print("%s: %s" % (ma, loi or "OK -> %s" % duong_cache(ma)))
