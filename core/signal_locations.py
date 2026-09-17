# -*- coding: utf-8 -*-
"""Muc cuoi cua Explain: moi tin hieu nhac trong cau tra loi nam o CPU nao, loop nao,
sheet nao.

Cau tra loi lay tin hieu xuyen sheet va xuyen CPU, doc xong nguoi ta can biet tim chung
o dau tren ban ve. Muc nay do CODE dung tu CSDL chu khong nho AI viet: trong ngu canh AI
chi thay nhan '167-15', rat de bia ra so loop hay ten sheet.

Mot ten co the co mat o hang chuc sheet (MFT: 32 cho), nen phai chon dung cho cau tra
loi dang noi toi. Thu tu uu tien giong het cach vet truy trong ai_explain di:
  1. cho ma vet truy nguoc/xuoi trong ngu canh ghi ro cho CHINH ten nay;
  2. sheet vet da di qua ma co khoi sinh ra ten nay (tin hieu noi bo cua sheet do);
  3. moi sheet co khoi sinh ra ten nay - cung CPU truoc;
  4. khong dau sinh ra (tin hieu vao tu ngoai cac DB da nap) thi ghi noi dung no.
"""
from __future__ import annotations

import re
from collections import namedtuple

from . import cond_tree as CT
from . import dbreader as D
from . import signal_graph as SG

TOI_DA_CHO = 3        # so vi tri hien cho moi ten; con lai gop thanh '+N'
TOI_DA_TEN = 40       # so ten toi da trong bang
TOI_DA_XET = 60       # so sheet toi da xet 'co sinh ra khong' cho moi ten

# '    X  [field measurement: ...]  (produced on UCS / sheet 167-15):'
_LEN = re.compile(r"^\s*(\S.*?)\s{2}.*\(produced on (.+?) / sheet ([^)\s]+)\)")
# '  -> X   (CPU 1 / sheet 167-30)'  hoac  '  -> X (CPU 1 / sheet 167-30, as `n`)'
_XUONG = re.compile(r"^\s*-> (\S.*?)\s+\(CPU (\S+) / sheet ([^,)\s]+)")
_THOAT = re.compile(r"([\\`*_\[\]<>|])")
# chu dinh lien sau / truoc mot ten thi ten do chi la manh cua nhan dai hon:
# 'MWD' trong 'MWD>537MW', 'PULV A PAFL' trong 'PULV A PAFL CTRL'. Chu thuong sau mot
# dau cach la loi dan ('X follows Y'), khong phai phan cua ten.
_NOI_SAU = re.compile(r"[-A-Za-z0-9&/#+(<>%]|\.[A-Za-z0-9]| [A-Z0-9(]")
_NOI_TRUOC = re.compile(r"(?:[-A-Za-z0-9&/#+()<>%.]|[A-Z0-9)] )$")

Vet = namedtuple("Vet", "theo_ten da_qua")   # {TEN: [(cpu, nhan)]}, [(cpu, nhan)]
Cho = namedtuple("Cho", "cac_cho them chi_dung")

_CHU = {
    "vi": {"tieu_de": "TÍN HIỆU NẰM Ở ĐÂU",
           "loi_dan": "Tra thẳng từ cơ sở dữ liệu dự án, không do AI viết. Mỗi tín hiệu "
                      "ghi sheet có khối sinh ra nó; tín hiệu không có khối sinh ra trong "
                      "các DB đã nạp thì ghi nơi dùng.",
           "cot": ("Tín hiệu", "CPU", "Loop", "Sheet"),
           "chi_dung": "nơi dùng",
           "them_cho": "+%d nơi khác",
           "them_ten": "Còn %d tín hiệu khác không liệt kê."},
    "en": {"tieu_de": "WHERE EACH SIGNAL LIVES",
           "loi_dan": "Looked up directly in the project database, not written by the AI. "
                      "Each signal shows the sheet whose block produces it; a signal with no "
                      "producing block in the loaded databases shows where it is used.",
           "cot": ("Signal", "CPU", "Loop", "Sheet"),
           "chi_dung": "used here",
           "them_cho": "+%d more",
           "them_ten": "%d more signals not listed."},
}
_TRANG = {}           # db -> ({sheet: loopno}, {loopno: ten loop})


def doc_vet(ctx):
    """Nhung cho vet truy trong ngu canh da ghi ra, giu thu tu xuat hien.
    cpu la TEN CPU o dong truy nguoc, SO CPU o dong truy xuoi."""
    theo_ten, da_qua = {}, []
    for dong in (ctx or "").splitlines():
        m = _LEN.match(dong) or _XUONG.match(dong)
        if not m:
            continue
        cho = (m.group(2).strip(), m.group(3).strip())
        ds = theo_ten.setdefault(m.group(1).strip().upper(), [])
        if cho not in ds:
            ds.append(cho)
        if cho not in da_qua:
            da_qua.append(cho)
    return Vet(theo_ten, da_qua)


def chi_la_manh(ten, ctx):
    """True neu ten co trong ngu canh nhung LAN NAO cung dinh lien chu truoc/sau.
    Khong co mat lan nao thi False: khong co gi de noi no la manh."""
    thay = False
    for m in re.finditer(re.escape(ten), ctx, re.I):
        thay = True
        if not (_NOI_TRUOC.search(ctx[max(0, m.start() - 2):m.start()])
                or _NOI_SAU.match(ctx, m.end())):
            return False
    return thay


def bo_manh(ten_list, ctx):
    """Bo ten ma ngu canh chi chua nhu MOT MANH cua nhan dai hon.

    AI dien giai 'MWD>537MW(75%TMCR)' thanh 'MWD > 537 MW', va chu MWD lai trung ten mot
    tin hieu co that o BMS_A; ghi vi tri cua no vao bang la chi sai cho. Ten hoan toan
    khong co trong ngu canh thi van giu: do la ten AI tra them bang cong cu get_source."""
    return [t for t in ten_list if not chi_la_manh(t, ctx or "")]


def _nhan(p, sid):
    """Cac cach vet truy co the goi sheet nay: (ten CPU | so CPU | 'CPUn', nhan sheet)."""
    R = SG._dbc(p)
    lbl = R["num"].get(sid) or str(sid)
    ten = {R.get("cpuname") or "", str(R.get("cpuno")), "CPU%s" % R.get("cpuno")}
    return {(t, lbl) for t in ten if t}


def _thu_hang(p, sid, cho_list):
    """Vi tri dau tien cua sheet nay trong cho_list, None neu khong co."""
    nhan = _nhan(p, sid)
    for i, cho in enumerate(cho_list):
        if cho in nhan:
            return i
    return None


def _ung_vien(ten, dbs):
    """[(thu tu db, db, sheet, net)] moi cho co ten nay, bo trung (db, sheet)."""
    ra, thay = [], set()
    for i, p in enumerate(dbs):
        try:
            ds = SG._dbc(p)["name2"].get(ten.upper(), [])
        except Exception:
            continue
        for sid, net in ds:
            if (p, sid) not in thay:
                thay.add((p, sid))
                ra.append((i, p, sid, net))
    return ra


def _sinh_ra(p, sid, net):
    try:
        return bool(CT._producers(p, sid).get(net))
    except Exception:
        return False


def _cat(ds, chi_dung=False):
    return Cho(ds[:TOI_DA_CHO], max(0, len(ds) - TOI_DA_CHO), chi_dung)


def tim_cho(ten, dbs, goc=(), vet=None):
    """Cac (db, sheet) nen ghi cho ten nay, theo thu tu uu tien o dau file."""
    vet = vet or Vet({}, [])
    uv = _ung_vien(ten, dbs)
    if not uv:
        return Cho([], 0, False)
    rieng = vet.theo_ten.get(ten.upper(), [])
    theo_vet = sorted((h, p, sid) for h, p, sid in
                      ((_thu_hang(p, sid, rieng), p, sid) for _i, p, sid, _n in uv)
                      if h is not None)
    if theo_vet:
        return _cat([(p, sid) for _h, p, sid in theo_vet])
    goc = set(goc)

    def hang(x):
        i, p, sid, _n = x
        h = -1 if (p, sid) in goc else _thu_hang(p, sid, vet.da_qua)
        return (h is None, h if h is not None else 0, i, SG._dbc(p)["num"].get(sid) or "")

    uv.sort(key=hang)
    sinh = [x for x in uv[:TOI_DA_XET] if _sinh_ra(x[1], x[2], x[3])]
    qua = [x for x in sinh if not hang(x)[0]]
    if qua:
        return _cat([(p, sid) for _i, p, sid, _n in qua])
    if sinh:
        return _cat([(p, sid) for _i, p, sid, _n in sinh])
    return _cat([(p, sid) for _i, p, sid, _n in uv], chi_dung=True)


def _trang(p):
    """({sheet: so loop}, {so loop: ten loop}) cua mot DB, doc mot lan."""
    if p in _TRANG:
        return _TRANG[p]
    loops, ten = {}, {}
    con = None
    try:
        con = D.connect(p)
        loops = {sid: D._clean(l) for sid, l in
                 con.execute("SELECT ID,LOOPNO FROM CAD_DATA")}
        ten = {D._clean(l): D._clean(n) for l, n in
               con.execute("SELECT LOOPNO,LOOPNAME FROM CAD_LOOP")}
    except Exception:
        pass
    finally:
        if con is not None:
            con.close()
    _TRANG[p] = (loops, ten)
    return _TRANG[p]


def mo_ta_cho(p, sid):
    """(CPU, Loop, Sheet) da thanh chu: 'UCS (CPU 1)', '167 PULV A PAFL CTRL', ..."""
    R = SG._dbc(p)
    cpu = R.get("cpuname") or ""
    if R.get("cpuno") is not None:
        cpu = ("%s (CPU %s)" % (cpu, R["cpuno"])).strip()
    loops, ten_loop = _trang(p)
    lno = loops.get(sid, "")
    so = lno.zfill(3) if lno.isdigit() else lno      # cung kieu voi nhan sheet '074-09'
    loop = ("%s %s" % (so, ten_loop.get(lno, ""))).strip()
    sheet = ("%s %s" % (R["num"].get(sid) or sid, R["sheetname"].get(sid) or "")).strip()
    return cpu, loop, sheet


def _o(s):
    """Thoat ky tu markdown de ten nhu 'DEVN<3degC' hay 'BMS_A' hien dung nguyen van."""
    return _THOAT.sub(r"\\\1", str(s))


def _dong_bang(ten, cho, chu):
    """Cac dong bang markdown cho mot ten. Ten chi ghi o dong dau cho de doc."""
    ra = []
    for i, (p, sid) in enumerate(cho.cac_cho):
        cpu, loop, sheet = mo_ta_cho(p, sid)
        if cho.chi_dung:
            sheet = "%s (%s)" % (sheet, chu["chi_dung"])
        o = [ten if i == 0 else "", cpu, loop, sheet]
        ra.append("| %s |" % " | ".join(_o(x) for x in o))
    if cho.them:
        ra.append("|  |  |  | %s |" % _o(chu["them_cho"] % cho.them))
    return ra


def muc_vi_tri(ten_list, dbs, goc=(), ctx="", lang="en", so=5):
    """Chuoi markdown '## (so) ...' kem bang vi tri; '' neu khong ten nao tra ra cho."""
    chu = _CHU.get(lang, _CHU["en"])
    vet = doc_vet(ctx)
    ten_list = bo_manh(ten_list, ctx)
    dong = []
    for ten in ten_list[:TOI_DA_TEN]:
        dong += _dong_bang(ten, tim_cho(ten, dbs, goc, vet), chu)
    if not dong:
        return ""
    cot = chu["cot"]
    ra = ["", "", "## (%d) %s" % (so, chu["tieu_de"]), "", chu["loi_dan"], "",
          "| %s |" % " | ".join(cot), "|%s" % ("---|" * len(cot))] + dong
    if len(ten_list) > TOI_DA_TEN:
        ra += ["", chu["them_ten"] % (len(ten_list) - TOI_DA_TEN)]
    return "\n".join(ra) + "\n"
